"""
Deciding what the user actually submitted.

The platform's promise is "paste anything and we work out what it is", so
this runs before any detector and decides which ones are worth running. It
is deliberately cheap and conservative: classification is a routing hint,
not a verdict, and a wrong guess costs a detector running needlessly rather
than a wrong answer.

Multi-label by design. An SMS containing a link is *both* a message and a
URL, and the interesting fraud usually lives in the relationship between
them -- the message manufactures urgency, the link harvests the credential.
Returning one label would throw that away, which is exactly the correlation
the platform is supposed to find.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set


class InputKind(str, Enum):
    TEXT = "TEXT"
    URL = "URL"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    EMAIL_MESSAGE = "EMAIL_MESSAGE"
    SMS = "SMS"
    PHONE = "PHONE"
    UPI_HANDLE = "UPI_HANDLE"
    CRYPTO_ADDRESS = "CRYPTO_ADDRESS"
    TRANSACTION = "TRANSACTION"


# ── Entity patterns ───────────────────────────────────────────
# Extraction feeds both routing and the evidence shown to the reader, so
# each pattern is written to capture the whole entity rather than enough of
# it to match.

URL_RE = re.compile(
    r"\b(?:https?://|www\.)[^\s<>\"'）)\]]+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)+/[^\s<>\"']*",
    re.IGNORECASE,
)
BARE_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}\b", re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Indian and international formats, tolerant of spaces, dashes and +country.
PHONE_RE = re.compile(r"(?<![\w.])(?:\+?\d{1,3}[\s-]?)?(?:\d[\s-]?){9,13}\d(?![\w.])")

# UPI handles: name@bank. Distinguished from email by the absence of a dot
# in the handle part, which is how NPCI handles are formed.
UPI_RE = re.compile(r"\b[A-Za-z0-9._-]{3,}@(?:ok[a-z]+|[a-z]{2,15})\b")

BTC_RE = re.compile(r"\b(?:bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
ETH_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")

# Message registers. Not fraud signals -- these only decide routing.
SMS_MARKERS = (
    "otp", "verification code", "one time password", "dear customer",
    "your account", "kyc", "click here", "reply stop", "sent from",
    "a/c", "acct", "txn", "upi", "debited", "credited", "rs.", "inr",
)
EMAIL_MARKERS = (
    "from:", "to:", "subject:", "reply-to:", "cc:", "bcc:",
    "dear sir", "dear madam", "unsubscribe", "sent from my",
    "best regards", "kind regards", "sincerely",
)

# Above this, it reads as an email body rather than a text message.
SMS_MAX_CHARS = 700


@dataclass
class Classification:
    """What the input appears to be, and what was pulled out of it."""

    kinds: Set[InputKind] = field(default_factory=set)
    entities: Dict[str, List[str]] = field(default_factory=dict)

    def has(self, kind: InputKind) -> bool:
        return kind in self.kinds

    @property
    def primary(self) -> InputKind:
        """
        The single best label, for display.

        Ordered by specificity: a transaction that mentions a URL is still a
        transaction, and calling it TEXT would be true and useless.
        """
        for kind in (
            InputKind.TRANSACTION, InputKind.EMAIL_MESSAGE, InputKind.SMS,
            InputKind.URL, InputKind.UPI_HANDLE, InputKind.CRYPTO_ADDRESS,
            InputKind.PHONE, InputKind.EMAIL_ADDRESS,
        ):
            if kind in self.kinds:
                return kind
        return InputKind.TEXT

    def as_dict(self) -> dict:
        return {
            "primary": self.primary.value,
            "kinds": sorted(k.value for k in self.kinds),
            "entities": {k: v for k, v in self.entities.items() if v},
        }


def _unique(values) -> List[str]:
    seen, out = set(), []
    for value in values:
        key = value.lower().strip().rstrip(".,;:)")
        if key and key not in seen:
            seen.add(key)
            out.append(value.strip().rstrip(".,;:)"))
    return out


def extract_entities(text: str) -> Dict[str, List[str]]:
    """Everything addressable in the text, for routing and for evidence."""
    emails = _unique(EMAIL_RE.findall(text))

    # UPI handles look like emails; an address already matched as email is
    # not re-reported as a handle.
    upi = [
        h for h in _unique(UPI_RE.findall(text))
        if h.lower() not in {e.lower() for e in emails} and "." not in h.split("@")[0]
    ]

    urls = _unique(URL_RE.findall(text))
    if not urls:
        # A bare domain with no scheme or path is still worth checking, but
        # only when it is not part of an address already captured.
        claimed = " ".join(emails + upi).lower()
        urls = [
            d for d in _unique(BARE_DOMAIN_RE.findall(text))
            if d.lower() not in claimed and "." in d
        ]

    phones = [
        p.strip() for p in PHONE_RE.findall(text)
        if 10 <= len(re.sub(r"\D", "", p)) <= 15
    ]

    return {
        "urls": urls,
        "emails": emails,
        "phones": _unique(phones),
        "upi_handles": upi,
        "crypto_addresses": _unique(BTC_RE.findall(text) + ETH_RE.findall(text)),
    }


def classify(text: str, *, hint: str = "") -> Classification:
    """
    What this input is.

    `hint` lets a caller that already knows -- a transaction form, a
    dedicated URL field -- skip the guessing rather than have heuristics
    second-guess a fact.
    """
    result = Classification()
    if not text or not text.strip():
        return result

    lowered = text.lower()
    result.entities = extract_entities(text)

    if hint:
        try:
            result.kinds.add(InputKind(hint.upper()))
        except ValueError:
            pass

    if result.entities["urls"]:
        result.kinds.add(InputKind.URL)
    if result.entities["emails"]:
        result.kinds.add(InputKind.EMAIL_ADDRESS)
    if result.entities["phones"]:
        result.kinds.add(InputKind.PHONE)
    if result.entities["upi_handles"]:
        result.kinds.add(InputKind.UPI_HANDLE)
    if result.entities["crypto_addresses"]:
        result.kinds.add(InputKind.CRYPTO_ADDRESS)

    email_hits = sum(1 for m in EMAIL_MARKERS if m in lowered)
    sms_hits = sum(1 for m in SMS_MARKERS if m in lowered)

    # Header lines are near-conclusive; the softer markers need corroboration
    # because "best regards" appears in plenty of things that are not email.
    if any(lowered.lstrip().startswith(h) for h in ("from:", "subject:", "to:")) or email_hits >= 2:
        result.kinds.add(InputKind.EMAIL_MESSAGE)
    elif sms_hits >= 1 and len(text) <= SMS_MAX_CHARS:
        result.kinds.add(InputKind.SMS)

    if not result.kinds:
        result.kinds.add(InputKind.TEXT)

    return result
