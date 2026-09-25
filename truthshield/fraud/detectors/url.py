"""
Phishing signals visible in a URL itself.

Everything here is computed from the string. That is a deliberate scope:
domain age, certificate details and reputation feeds all require API keys
this deployment does not have, and a detector that silently skips its most
important checks while still returning a confident score is worse than one
that states its limits. So this reports what structure alone can support,
and says plainly in `limitations` what it could not check.

Structure alone is genuinely informative. The attacks it catches --
punycode homographs, brand names in a subdomain, credential-harvest paths
on a free host -- are the ones that survive contact with a careful reader,
because they are built to look right.

What it cannot do is clear a URL. A well-formed link to a newly registered
domain looks identical to a well-formed link to a bank, which is why the
ceiling on a clean result is "nothing structural found", never "safe".
"""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import unquote, urlparse

from truthshield.fraud.classify import Classification, InputKind
from truthshield.fraud.contract import (
    FraudCategory, FraudFinding, Indicator, Severity, score_from_indicators,
)
from truthshield.fraud.registry import FraudDetector, register

# Brands impersonated often enough to be worth naming. A brand token
# appearing anywhere but the registrable domain is the classic tell:
# `paypal.secure-login.tk` is not PayPal.
WATCHED_BRANDS = (
    "paypal", "apple", "microsoft", "google", "amazon", "netflix", "meta",
    "facebook", "instagram", "whatsapp", "linkedin", "dhl", "fedex", "ups",
    "usps", "hmrc", "irs", "gov", "sbi", "hdfc", "icici", "axis", "paytm",
    "phonepe", "gpay", "npci", "upi", "binance", "coinbase", "metamask",
)

# TLDs that are free or near-free to register, and correspondingly common in
# throwaway phishing infrastructure. Not damning on their own -- plenty of
# legitimate sites use them -- so this is a LOW indicator.
CHEAP_TLDS = frozenset({
    "tk", "ml", "ga", "cf", "gq", "xyz", "top", "buzz", "click", "link",
    "work", "loan", "zip", "mov", "rest", "country", "kim", "download",
})

SHORTENERS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy", "tiny.cc", "bl.ink",
})

# Paths that exist to collect something.
HARVEST_PATHS = (
    "login", "signin", "sign-in", "verify", "verification", "secure",
    "account", "update", "confirm", "password", "reset", "billing",
    "payment", "wallet", "unlock", "suspend", "kyc", "authorize",
)

# Free hosting and form builders. Legitimate uses exist; a *bank login page*
# on one does not.
FREE_HOSTS = (
    "000webhost", "weebly", "wixsite", "blogspot", "github.io", "glitch.me",
    "repl.co", "vercel.app", "netlify.app", "pages.dev", "firebaseapp.com",
    "forms.gle", "google.com/forms", "typeform.com", "jotform",
)

IP_HOST_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

# Latin letters with visually identical counterparts in other scripts. Their
# presence in a hostname is how `аpple.com` (Cyrillic а) is built.
CONFUSABLE_RE = re.compile(r"[Ѐ-ӿͰ-ϿԀ-ԯ]")


def _registrable(host: str) -> str:
    """
    The part a brand actually owns.

    Crude two-label heuristic, extended for the common compound suffixes.
    A full public-suffix list would be more correct and is a dependency this
    does not need: the failure mode is treating `example.co.uk` as `co.uk`,
    which the extension below covers for the suffixes that matter here.
    """
    parts = host.lower().split(".")
    if len(parts) < 2:
        return host.lower()
    if len(parts) >= 3 and parts[-2] in ("co", "com", "net", "org", "gov", "ac"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def inspect_url(raw: str) -> List[Indicator]:
    """Everything the string alone supports."""
    indicators: List[Indicator] = []

    candidate = raw if "://" in raw else f"http://{raw}"
    try:
        parsed = urlparse(candidate)
    except Exception:
        return [Indicator(
            code="unparseable_url", title="Malformed link", severity=Severity.MEDIUM,
            explanation="This link could not be parsed as a web address.",
            evidence=raw[:120],
        )]

    host = (parsed.hostname or "").lower()
    if not host:
        return indicators

    path = unquote(parsed.path or "").lower()
    query = unquote(parsed.query or "").lower()
    registrable = _registrable(host)
    labels = host.split(".")
    tld = labels[-1] if len(labels) > 1 else ""

    # ── Disguised hostname ────────────────────────────────────
    if host.startswith("xn--") or ".xn--" in host:
        indicators.append(Indicator(
            code="punycode_host", title="Disguised domain", severity=Severity.HIGH,
            explanation=(
                "The address uses punycode, which renders as letters from another "
                "alphabet that look identical to Latin ones. This is used to build "
                "a domain that is visually indistinguishable from a real brand."
            ),
            evidence=host,
        ))
    elif CONFUSABLE_RE.search(host):
        indicators.append(Indicator(
            code="mixed_script_host", title="Mixed-alphabet domain", severity=Severity.HIGH,
            explanation=(
                "The address mixes Latin characters with visually identical "
                "characters from another alphabet — a deliberate disguise."
            ),
            evidence=host,
        ))

    if IP_HOST_RE.match(host):
        indicators.append(Indicator(
            code="ip_host", title="Numeric address instead of a name", severity=Severity.HIGH,
            explanation=(
                "The link points at a raw IP address. Legitimate services use a "
                "domain name; a bare address avoids leaving a registration trail."
            ),
            evidence=host,
        ))

    # ── Brand impersonation ───────────────────────────────────
    stem = registrable.rsplit(".", 1)[0]
    for brand in WATCHED_BRANDS:
        if brand not in host:
            continue
        if brand in stem:
            break          # plausibly the real owner; not an indicator
        indicators.append(Indicator(
            code="brand_outside_domain", title="Brand name used in a subdomain",
            severity=Severity.HIGH,
            explanation=(
                f"'{brand}' appears in the address but the domain actually "
                f"registered is '{registrable}'. Only the part immediately before "
                "the suffix identifies the owner; everything to its left can be "
                "set to anything."
            ),
            evidence=host,
        ))
        break

    if host.count("-") >= 3:
        indicators.append(Indicator(
            code="hyphen_heavy", title="Unusual domain structure", severity=Severity.LOW,
            explanation="Long hyphenated domains are common in disposable phishing infrastructure.",
            evidence=host,
        ))

    if len(labels) >= 5:
        indicators.append(Indicator(
            code="deep_subdomains", title="Deeply nested subdomains", severity=Severity.MEDIUM,
            explanation=(
                "Many subdomain levels are used to push the real domain out of "
                "sight, especially on a phone where the address bar truncates."
            ),
            evidence=host,
        ))

    # ── Hosting and suffix ────────────────────────────────────
    if tld in CHEAP_TLDS:
        indicators.append(Indicator(
            code="cheap_tld", title="Free or throwaway domain suffix", severity=Severity.LOW,
            explanation=(
                f"'.{tld}' is free or near-free to register, so it is heavily used "
                "for short-lived phishing sites. Legitimate sites use it too."
            ),
            evidence=f".{tld}",
        ))

    if registrable in SHORTENERS:
        indicators.append(Indicator(
            code="shortener", title="Shortened link", severity=Severity.MEDIUM,
            explanation=(
                "A shortener hides the real destination until it is opened, so "
                "nothing about where this leads can be checked in advance."
            ),
            evidence=registrable,
        ))

    free_host = next((h for h in FREE_HOSTS if h in host or h in f"{host}{path}"), None)

    # ── What the page wants ───────────────────────────────────
    #
    # A sign-in path is only a signal when something about the *host* is
    # already wrong. On its own it is meaningless: every bank, mailbox and
    # shop has a login page, and scoring the path alone flagged
    # `hdfcbank.com/personal/netbanking/login` -- a real bank's real login
    # page -- as suspicious. A false positive there is worse than a missed
    # detection, because it trains the reader to dismiss the warning.
    host_is_suspect = any(
        i.code in (
            "punycode_host", "mixed_script_host", "ip_host",
            "brand_outside_domain", "deep_subdomains", "cheap_tld",
            "userinfo_in_url", "hyphen_heavy",
        )
        for i in indicators
    ) or bool(free_host)

    harvest = [p for p in HARVEST_PATHS if p in path or p in query]
    if harvest and host_is_suspect:
        severity = Severity.MEDIUM
        explanation = (
            "The address points at a sign-in, verification or payment page, on a "
            "domain that already looks wrong. That combination is how credentials "
            "and card details get taken."
        )
        if free_host:
            severity = Severity.HIGH
            explanation = (
                f"A sign-in or payment page hosted on '{free_host}', which is free "
                "hosting. No bank or payment provider puts a login page there."
            )
        indicators.append(Indicator(
            code="credential_path", title="Sign-in page on a questionable domain",
            severity=severity, explanation=explanation,
            evidence=", ".join(harvest[:4]),
        ))
    elif harvest:
        # Recorded, weighted at nothing. It is context for the reader and a
        # hook for a future detector with reputation data, not evidence.
        indicators.append(Indicator(
            code="credential_path_benign", title="Sign-in or payment page",
            severity=Severity.INFO,
            explanation=(
                "This is a sign-in or payment page. Nothing about the domain itself "
                "looks wrong, but only enter credentials if you arrived here by "
                "typing the address rather than following a link."
            ),
            evidence=", ".join(harvest[:4]),
        ))
    elif free_host:
        indicators.append(Indicator(
            code="free_hosting", title="Free hosting", severity=Severity.LOW,
            explanation=f"Hosted on '{free_host}', which anyone can publish to for nothing.",
            evidence=free_host,
        ))

    if "@" in (parsed.netloc or ""):
        indicators.append(Indicator(
            code="userinfo_in_url", title="Address contains an '@'", severity=Severity.HIGH,
            explanation=(
                "Everything before the '@' in a web address is ignored by the "
                "browser. It is used to put a trusted-looking name in front of "
                "the real destination."
            ),
            evidence=parsed.netloc,
        ))

    if parsed.scheme == "http" and harvest:
        indicators.append(Indicator(
            code="insecure_credential_page", title="Unencrypted sign-in page",
            severity=Severity.MEDIUM,
            explanation="A sign-in page served over plain HTTP sends anything typed into it in the clear.",
            evidence=f"{parsed.scheme}://{host}",
        ))

    return indicators


class UrlStructureDetector(FraudDetector):
    """Phishing signals in the shape of a link, with no network calls."""

    name = "url_structure"
    describes = "Phishing and impersonation signals in a link's structure"
    handles = (InputKind.URL,)

    # Stated on every finding. A reader who knows the checks that did *not*
    # run can weigh the result; one who does not will read a clean structural
    # result as a clean bill of health.
    UNCHECKED = [
        "Domain age and registration details were not checked (no WHOIS access).",
        "The domain was not checked against any reputation or phishing feed.",
        "The page itself was not fetched, so its content and forms are unexamined.",
        "Certificate details were not inspected.",
    ]

    def _run(self, text: str, classification: Classification) -> Optional[FraudFinding]:
        urls = classification.entities.get("urls") or []
        if not urls:
            return None

        indicators: List[Indicator] = []
        # Bounded: a message with forty links is a different problem, and
        # inspecting all of them buries the finding that matters.
        for url in urls[:5]:
            indicators.extend(inspect_url(url))

        # Deduplicated by code -- three links sharing one weakness is one
        # finding about the message, not three independent signals.
        seen, unique = set(), []
        for indicator in indicators:
            if indicator.code not in seen:
                seen.add(indicator.code)
                unique.append(indicator)

        score = score_from_indicators(unique)

        if not unique:
            return FraudFinding(
                detector=self.name,
                category=FraudCategory.NONE,
                risk_score=0.0,
                # Low deliberately: finding nothing structural is weak
                # evidence of safety, and a high confidence here would read
                # as clearance this detector cannot give.
                confidence=0.25,
                summary=(
                    f"Nothing suspicious in the structure of "
                    f"{'this link' if len(urls) == 1 else f'these {len(urls)} links'}."
                ),
                recommended_action=(
                    "Structure alone cannot confirm a link is safe. If it arrived "
                    "unexpectedly, reach the site by typing the address yourself "
                    "rather than following the link."
                ),
                limitations=self.UNCHECKED,
                methods=["url-structure-rules"],
                extra={"urls_examined": urls[:5]},
            )

        strong = [i for i in unique if i.severity is Severity.HIGH]
        category = FraudCategory.PHISHING if strong else FraudCategory.UNKNOWN

        return FraudFinding(
            detector=self.name,
            category=category,
            risk_score=score,
            # Capped below certainty: these are structural heuristics, and
            # the reputation data that would justify a higher number is
            # exactly what is missing.
            confidence=min(0.75, 0.35 + 0.12 * len(unique)),
            summary=(
                f"{len(unique)} structural warning sign"
                f"{'' if len(unique) == 1 else 's'} in "
                f"{'this link' if len(urls) == 1 else 'these links'}: "
                + ", ".join(i.title.lower() for i in unique[:3]) + "."
            ),
            indicators=unique,
            recommended_action=(
                "Do not sign in or enter payment details through this link. Open "
                "the organisation's site by typing its address yourself and check "
                "from there."
                if strong else
                "Treat this link with caution and verify where it leads before "
                "entering anything."
            ),
            limitations=self.UNCHECKED,
            methods=["url-structure-rules"],
            extra={"urls_examined": urls[:5]},
        )


register(UrlStructureDetector())
