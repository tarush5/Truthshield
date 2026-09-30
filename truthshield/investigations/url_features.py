"""
The URL feature vector.

Pure functions over the string. These are the model-ready features the spec
names (domain_length, entropy, digit_ratio, ...). In Phase 1 they are shown
to the analyst and stored with the investigation; a trained phishing
classifier consumes the same vector later, which is why the names and
definitions are fixed here rather than recomputed ad hoc elsewhere.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, Optional
from urllib.parse import parse_qsl, unquote, urlparse

from truthshield.fraud.detectors.url import HARVEST_PATHS, WATCHED_BRANDS, _registrable

SPECIAL_CHARS = set("@-_~%=&?!$*+,;")
ENCODED_RE = re.compile(r"%[0-9a-fA-F]{2}")

# Brand tokens too short or too generic to compare by edit distance: "gov"
# is one edit from half the internet.
SIMILARITY_EXCLUDED = {"gov", "ups", "irs", "upi", "sbi", "meta", "axis", "dhl"}


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    total = len(value)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def _similarity(a: str, b: str) -> float:
    try:
        import Levenshtein  # python-Levenshtein, in requirements.txt

        return Levenshtein.ratio(a, b)
    except Exception:
        return SequenceMatcher(None, a, b).ratio()


@dataclass(frozen=True)
class BrandMatch:
    similarity: float          # best fuzzy similarity to a watched brand, 0-1
    closest: Optional[str]
    exact_token: Optional[str]  # a watched brand appearing as a whole token
    label_is_brand: bool        # the owned label *is* the brand, e.g. paypal.com


def brand_similarity(registrable: str) -> BrandMatch:
    """
    How much the owned label looks like a watched brand.

    Compared on the label a registrant actually controls: for
    `secure.paypa1-login.com` that is `paypa1-login`, split on hyphens so
    `paypa1` is compared on its own. Exact tokens are checked against every
    brand; fuzzy similarity only against brands long and distinctive enough
    that one edit is meaningful.
    """
    label = registrable.split(".")[0].lower()
    parts = [p for p in re.split(r"[-_]", label) if p] or [label]

    exact = next((p for p in parts if p in WATCHED_BRANDS), None)

    best, closest = 0.0, None
    for brand in WATCHED_BRANDS:
        if brand in SIMILARITY_EXCLUDED or len(brand) < 4:
            continue
        for part in dict.fromkeys(parts + [label]):
            score = 1.0 if part == brand else _similarity(part, brand)
            if score > best:
                best, closest = score, brand

    return BrandMatch(
        similarity=round(best, 3),
        closest=closest if best >= 0.5 else None,
        exact_token=exact,
        label_is_brand=label in WATCHED_BRANDS,
    )


@dataclass(frozen=True)
class UrlFeatures:
    url: str
    host: str
    registrable: str
    tld: str
    values: Dict[str, float]
    brand: BrandMatch

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "host": self.host,
            "registrable_domain": self.registrable,
            "tld": self.tld,
            "closest_brand": self.brand.closest,
            "features": self.values,
        }


def extract_features(raw: str) -> Optional[UrlFeatures]:
    candidate = raw if "://" in raw else f"http://{raw}"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return None

    registrable = _registrable(host)
    labels = host.split(".")
    reg_labels = registrable.split(".")
    path = unquote(parsed.path or "")
    lowered = (path + "?" + unquote(parsed.query or "")).lower()

    keyword_hits = sum(1 for word in HARVEST_PATHS if word in lowered or word in host)
    brand = brand_similarity(registrable)

    values = {
        "url_length": len(candidate),
        "domain_length": len(host),
        "subdomain_count": max(0, len(labels) - len(reg_labels)),
        "path_depth": len([p for p in path.split("/") if p]),
        "special_character_count": sum(1 for c in candidate if c in SPECIAL_CHARS),
        "encoded_character_count": len(ENCODED_RE.findall(candidate)),
        "query_param_count": len(parse_qsl(parsed.query or "", keep_blank_values=True)),
        "digit_ratio": round(sum(c.isdigit() for c in host) / max(1, len(host)), 3),
        "entropy": round(shannon_entropy(host.replace(".", "")), 3),
        "https": 1 if parsed.scheme.lower() == "https" else 0,
        "suspicious_keyword_score": round(min(1.0, keyword_hits / 3), 3),
        "brand_similarity": brand.similarity,
    }
    return UrlFeatures(
        url=raw,
        host=host,
        registrable=registrable,
        tld=labels[-1] if len(labels) > 1 else "",
        values=values,
        brand=brand,
    )
