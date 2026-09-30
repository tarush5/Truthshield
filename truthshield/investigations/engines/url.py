"""
URL intelligence engine.

For each link: the feature vector (`url_features`), the 1.x structural rules
(`fraud.detectors.url.inspect_url`), lookalike-domain checks that 1.x lacked,
and -- when enabled and online -- a sandboxed fetch of the page itself.

The fetch goes through the SSRF guard (every redirect hop re-validated, byte
cap, strict timeouts), never executes scripts, and only reads the HTML. What
it cannot establish -- domain age, certificates, reputation feeds -- is
listed as uncertainty rather than silently skipped.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List
from urllib.parse import urljoin, urlparse

from truthshield.fraud.contract import Severity
from truthshield.fraud.detectors.url import (
    CHEAP_TLDS, HARVEST_PATHS, WATCHED_BRANDS, _registrable, inspect_url,
)
from truthshield.investigations.engines.base import Engine
from truthshield.investigations.types import (
    EngineKind, EngineResult, Family, InvestigationContext, InvestigationType,
    ModelPredictionRecord, Provenance, Signal,
)
from truthshield.investigations.url_features import extract_features

logger = logging.getLogger(__name__)

MAX_URLS = 5
FETCH_TIMEOUT = (3.0, 6.0)
FETCH_MAX_BYTES = 2 * 1024 * 1024

ALWAYS_UNCHECKED = [
    "Domain age and registration details were not checked (no WHOIS provider configured).",
    "The domain was not checked against a reputation or threat-intelligence feed "
    "(no provider configured), so the reputation family is not assessed.",
    "TLS certificate details were not inspected.",
]


class UrlEngine(Engine):
    name = "url"
    version = "1.0.0"
    kind = EngineKind.HEURISTIC
    describes = "URL structure, lookalike domains, feature vector and sandboxed page inspection"

    def applies_to(self, ctx: InvestigationContext) -> bool:
        return ctx.type is InvestigationType.URL or bool(ctx.urls)

    def _signal(self, **kwargs) -> Signal:
        return Signal(engine=self.name, engine_version=self.version,
                      family=Family.URL, provenance=Provenance.HEURISTIC, **kwargs)

    def _run(self, ctx: InvestigationContext, result: EngineResult) -> None:
        from truthshield.settings import get_settings

        settings = get_settings()
        urls = ctx.urls or ([ctx.content.strip()] if ctx.type is InvestigationType.URL else [])
        urls = urls[:MAX_URLS]

        fetch_allowed = settings.URL_FETCH_ENABLED and settings.network_allowed and ctx.allow_page_fetch
        seen_codes = set()
        reports: List[dict] = []

        for url in urls:
            features = extract_features(url)
            if features is None:
                result.limitations.append(f"Could not parse '{url[:80]}' as a web address.")
                continue

            signals: List[Signal] = []

            # 1.x structural rules.
            for indicator in inspect_url(url):
                signals.append(self._signal(
                    code=indicator.code, title=indicator.title, severity=indicator.severity,
                    explanation=indicator.explanation, evidence=indicator.evidence,
                    weight=indicator.weight, confidence=0.65,
                ))
            codes = {s.code for s in signals}

            signals.extend(self._lookalike(features, codes))

            page = None
            fetch = {"status": "skipped", "reason": "Page retrieval is disabled or the system is offline."}
            if fetch_allowed:
                page, fetch = self._fetch(url, settings.URL_CACHE_TTL_SECONDS)
                if page:
                    signals.extend(self._page_signals(features.registrable, page))

            result.predictions.append(ModelPredictionRecord(
                model_name="url-structure-rules", model_version=self.version,
                model_kind=EngineKind.HEURISTIC, task="url_risk_indicators",
                input_sha256=hashlib.sha256(url.encode("utf-8")).hexdigest(),
                prediction={"indicators": [s.code for s in signals], "features": features.values},
                confidence=None,
            ))

            for signal in signals:
                if signal.code not in seen_codes:
                    seen_codes.add(signal.code)
                    result.signals.append(signal)

            reports.append({
                **features.as_dict(),
                "signals": [s.code for s in signals],
                "page": page,
                "fetch": fetch,
            })

        result.artifacts["urls"] = reports
        result.features["urls_examined"] = len(reports)
        result.limitations.extend(ALWAYS_UNCHECKED)
        if not fetch_allowed:
            reason = (
                "this is a demo sample with an invented domain"
                if not ctx.allow_page_fetch else "offline mode or page retrieval disabled"
            )
            result.limitations.append(
                f"The linked page was not retrieved ({reason}), so its content and forms "
                "were not examined."
            )

    # ── Lookalike domains ─────────────────────────────────────

    def _lookalike(self, features, codes: set) -> List[Signal]:
        out: List[Signal] = []
        brand = features.brand
        values = features.values

        if brand.closest and 0.8 <= brand.similarity < 1.0 and not brand.exact_token:
            out.append(self._signal(
                code="typosquat_domain", title=f"Lookalike of '{brand.closest}'",
                severity=Severity.HIGH,
                explanation=(
                    f"The registered name '{features.registrable}' is one or two characters "
                    f"away from '{brand.closest}'. Typosquatted domains are registered to catch "
                    "readers who do not notice the difference."
                ),
                evidence=f"{features.registrable} ≈ {brand.closest} (similarity {brand.similarity:.2f})",
                confidence=0.7,
            ))

        if brand.exact_token and not brand.label_is_brand and "brand_outside_domain" not in codes:
            risky_context = features.tld in CHEAP_TLDS or values["suspicious_keyword_score"] > 0
            out.append(self._signal(
                code="brand_in_unofficial_domain",
                title="Domain mismatch",
                severity=Severity.MEDIUM if risky_context else Severity.LOW,
                explanation=(
                    f"'{brand.exact_token}' is part of the domain '{features.registrable}', but "
                    "this is not that organisation's own domain name. Anyone can register a "
                    "name that contains a brand."
                ),
                evidence=features.registrable,
                confidence=0.6 if risky_context else 0.45,
            ))

        if values["entropy"] >= 4.0 and values["domain_length"] >= 20:
            out.append(self._signal(
                code="random_looking_domain", title="Random-looking domain",
                severity=Severity.LOW,
                explanation="The host name has the character spread of generated names used by throwaway infrastructure.",
                evidence=f"{features.host} (entropy {values['entropy']:.2f} bits/char)",
                confidence=0.45,
            ))

        if values["encoded_character_count"] >= 3:
            out.append(self._signal(
                code="encoded_characters", title="Encoded characters in the address",
                severity=Severity.LOW,
                explanation="Percent-encoding hides what an address says from a quick read.",
                evidence=f"{int(values['encoded_character_count'])} encoded sequences",
                confidence=0.45,
            ))
        return out

    # ── Page retrieval ────────────────────────────────────────

    def _fetch(self, url: str, ttl: int):
        from truthshield.infra.cache import get_cache
        from truthshield.security.url_guard import BlockedURLError, safe_get

        target = url if "://" in url else f"http://{url}"
        key = "urlpage:" + hashlib.sha256(target.encode("utf-8")).hexdigest()
        cache = get_cache()
        cached = cache.get(key)
        if cached:
            return cached.get("page"), {**cached.get("fetch", {}), "cached": True}

        hops: List[str] = []
        try:
            response = safe_get(
                target,
                headers={"User-Agent": "TruthShield-URL-Inspector/2.0 (+no-js)"},
                timeout=FETCH_TIMEOUT,
                max_bytes=FETCH_MAX_BYTES,
                history=hops,
            )
        except BlockedURLError as exc:
            fetch = {"status": "blocked", "reason": str(exc)}
            return None, fetch
        except Exception as exc:
            return None, {"status": "failed", "reason": f"{type(exc).__name__}"}

        content_type = response.headers.get("Content-Type", "")
        page: Dict = {
            "final_url": hops[-1] if hops else target,
            "redirect_chain": hops,
            "status_code": response.status_code,
            "content_type": content_type[:80],
        }
        if "html" in content_type.lower():
            page.update(analyze_html(response.text[:FETCH_MAX_BYTES], page["final_url"]))
        fetch = {"status": "fetched", "reason": None}

        cache.set(key, {"page": page, "fetch": fetch}, ttl=ttl)
        return page, fetch

    def _page_signals(self, registrable: str, page: dict) -> List[Signal]:
        out: List[Signal] = []
        final_host = (urlparse(page.get("final_url") or "").hostname or "").lower()
        final_reg = _registrable(final_host) if final_host else registrable

        chain_domains = {
            _registrable((urlparse(u).hostname or "").lower())
            for u in page.get("redirect_chain", []) if urlparse(u).hostname
        }
        if len(chain_domains) > 1:
            out.append(self._signal(
                code="cross_domain_redirect", title="Redirects to another domain",
                severity=Severity.MEDIUM,
                explanation="The link forwards through different domains before landing, which hides the real destination.",
                evidence=" → ".join(page["redirect_chain"][:4]),
                confidence=0.6,
            ))

        for form in page.get("forms", []):
            if not form.get("has_password"):
                continue
            action_host = (urlparse(form.get("action") or "").hostname or "").lower()
            if action_host and _registrable(action_host) != final_reg:
                out.append(self._signal(
                    code="credential_form_offsite", title="Password form posts to another domain",
                    severity=Severity.HIGH,
                    explanation=(
                        "The page asks for a password but sends it to a different domain than "
                        "the one shown — the defining behaviour of a credential-harvesting page."
                    ),
                    evidence=f"form action → {action_host}",
                    confidence=0.8,
                ))
                break
        if page.get("password_fields") and (page.get("final_url") or "").startswith("http://"):
            out.append(self._signal(
                code="insecure_password_form", title="Password field without encryption",
                severity=Severity.HIGH,
                explanation="A password typed here would travel unencrypted.",
                evidence=page.get("final_url"),
                confidence=0.8,
            ))

        text = f"{page.get('title') or ''} {page.get('description') or ''}".lower()
        for brand in WATCHED_BRANDS:
            if len(brand) < 4 or brand == "gov":
                continue
            if brand in text and brand not in final_reg:
                out.append(self._signal(
                    code="brand_mismatch_page", title=f"Page presents itself as '{brand}'",
                    severity=Severity.HIGH if page.get("password_fields") else Severity.MEDIUM,
                    explanation=(
                        f"The page title or description names '{brand}', but it is served from "
                        f"'{final_reg}'. Impersonation pages copy the branding, not the domain."
                    ),
                    evidence=(page.get("title") or "")[:120],
                    confidence=0.65,
                ))
                break
        return out


def analyze_html(html: str, base_url: str) -> dict:
    """Static read of a page. Nothing is executed; scripts are only counted."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_host = (urlparse(base_url).hostname or "").lower()

    title = (soup.title.string or "").strip() if soup.title and soup.title.string else None
    meta = soup.find("meta", attrs={"name": "description"})
    description = (meta.get("content") or "").strip()[:300] if meta else None

    forms = []
    for form in soup.find_all("form")[:10]:
        inputs = form.find_all("input")
        forms.append({
            "action": urljoin(base_url, form.get("action") or base_url),
            "method": (form.get("method") or "get").lower(),
            "inputs": len(inputs),
            "has_password": any((i.get("type") or "").lower() == "password" for i in inputs),
        })

    scripts = [s.get("src") for s in soup.find_all("script") if s.get("src")]
    external_scripts = sorted({
        (urlparse(urljoin(base_url, s)).hostname or "").lower()
        for s in scripts
    } - {base_host, ""})

    links = [a.get("href") for a in soup.find_all("a") if a.get("href")]
    external_links = [
        h for h in links
        if (urlparse(urljoin(base_url, h)).hostname or base_host).lower() != base_host
    ]

    return {
        "title": title[:200] if title else None,
        "description": description,
        "forms": forms,
        "password_fields": sum(1 for f in forms if f["has_password"]),
        "script_count": len(soup.find_all("script")),
        "external_script_hosts": external_scripts[:20],
        "link_count": len(links),
        "external_link_ratio": round(len(external_links) / len(links), 2) if links else 0.0,
        "iframes": len(soup.find_all("iframe")),
        "harvest_vocabulary": sorted({w for w in HARVEST_PATHS if w in (title or "").lower()}),
    }
