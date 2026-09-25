"""
Finding and masking personal data in a submission.

This matters more here than in most places, because of what people paste.
Someone reporting a scam pastes the scam *and everything around it* -- their
own card number from the message above, the OTP they nearly sent, the
account number the bank quoted back at them. The submission is frequently a
richer source of their personal data than anything they would knowingly
upload.

So masking runs before anything is logged, stored, echoed to a report, or
sent to an external service. The detectors still see the original text,
because the analysis needs it; nothing downstream of the analysis does.

Masking is one-way and partial. A card number becomes `**** **** **** 4412`
rather than a token: the last four are what lets a person recognise which
card it was, which is the entire value of showing it at all, and the rest
is unrecoverable rather than encrypted. There is no unmask path by design.

Known limitations, stated rather than discovered:
  * Names and addresses are not detected. That needs NER, and a
    half-working name detector that misses two in three is worse than an
    honest gap, because it invites reliance.
  * Recall on free-form text is imperfect. Anything here is defence in
    depth, not a guarantee, and the UI is written to say so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class PiiRule:
    kind: str
    label: str
    pattern: re.Pattern
    #: How many trailing characters to keep, for recognisability.
    keep_tail: int = 0
    #: Why this is sensitive, shown when the UI explains a redaction.
    reason: str = ""


def _luhn(digits: str) -> bool:
    """
    Whether a digit string passes the Luhn check.

    Used so a 16-digit order reference is not masked as a card number. The
    check is what separates "looks like a card" from "is formatted like a
    card", and a false redaction destroys the reference the user needed.
    """
    total, parity = 0, len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


# Ordered: earlier rules win a contested span, so a card number is masked as
# a card rather than caught by the looser long-number rule.
RULES: Tuple[PiiRule, ...] = (
    PiiRule(
        "card", "Payment card number",
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        keep_tail=4,
        reason="A card number is enough to attempt a payment.",
    ),
    PiiRule(
        "otp", "One-time code",
        re.compile(
            r"\b(?:otp|code|pin)\b[^\d\n]{0,20}(\d{4,8})\b|"
            r"\b(\d{4,8})\b(?=[^\n]{0,24}\b(?:is your|otp|one[\s-]?time)\b)",
            re.IGNORECASE,
        ),
        reason="A one-time code authorises a transaction. It should never be shared.",
    ),
    PiiRule(
        "aadhaar", "Aadhaar number",
        re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b"),
        keep_tail=4,
        reason="A national identity number enables impersonation.",
    ),
    PiiRule(
        "pan", "PAN",
        re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
        keep_tail=2,
        reason="A tax identifier enables impersonation.",
    ),
    PiiRule(
        "ifsc", "Bank branch code",
        re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
        keep_tail=3,
        reason="Identifies the account's branch.",
    ),
    PiiRule(
        "email", "Email address",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        reason="A personal address invites further targeting.",
    ),
    # An account number must be introduced as one, and then it wins the span.
    #
    # A bare run of digits is ambiguous. Matching 9-18 digits unqualified
    # masked a 10-digit phone number as a bank account, and masked a
    # 16-digit order reference as one too -- destroying the reference the
    # user came in with. Requiring a cue fixes that; ordering it above the
    # phone rule then keeps "transfer to account 5010…" labelled as an
    # account rather than as a long phone number. Both are masked either
    # way, but the label is shown to the reader and should be right.
    PiiRule(
        "account", "Bank account number",
        re.compile(
            r"\b(?:a/?c|acct|account|iban|beneficiary|transfer\s+to|credited\s+to)\b"
            r"[^\d\n]{0,24}(\d{9,18})\b",
            re.IGNORECASE,
        ),
        keep_tail=4,
        reason="An account number can be used to direct or trace payments.",
    ),
    PiiRule(
        "phone", "Phone number",
        re.compile(r"(?<![\w.])(?:\+?\d{1,3}[\s-]?)?(?:\d[\s-]?){9,13}\d(?![\w.])"),
        keep_tail=4,
        reason="A personal number invites further targeting.",
    ),
    PiiRule(
        "crypto_seed", "Wallet recovery phrase",
        re.compile(r"\b(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}\b"),
        reason="A recovery phrase *is* the wallet. Anyone holding it holds the funds.",
    ),
)


@dataclass
class Redaction:
    kind: str
    label: str
    reason: str
    preview: str          # what replaced it, safe to display
    count: int = 1


def _mask(value: str, keep_tail: int) -> str:
    """Replace a value with a shape that is recognisable but not usable."""
    digits_only = re.sub(r"\D", "", value)

    if keep_tail and len(digits_only) > keep_tail:
        return f"{'*' * max(4, len(digits_only) - keep_tail)}{digits_only[-keep_tail:]}"
    if "@" in value:
        name, _, domain = value.partition("@")
        head = name[0] if name else ""
        return f"{head}{'*' * max(3, len(name) - 1)}@{domain}"
    return "*" * max(6, min(len(value), 12))


def _is_plausible(kind: str, raw: str) -> bool:
    """Filter the matches that would be false redactions."""
    digits = re.sub(r"\D", "", raw)

    if kind == "card":
        # Length *and* Luhn. Without Luhn, order numbers and tracking
        # references get masked and the user loses the reference they came
        # in with.
        return 13 <= len(digits) <= 19 and _luhn(digits)
    if kind == "account":
        return 9 <= len(digits) <= 18
    if kind == "phone":
        return 10 <= len(digits) <= 15
    if kind == "crypto_seed":
        # A seed phrase is a specific length. Ordinary prose of the same
        # word count would otherwise be redacted wholesale.
        return len(raw.split()) in (12, 15, 18, 21, 24)
    return True


def scan(text: str) -> List[Redaction]:
    """What personal data is present, without altering the text."""
    _, found = redact(text)
    return found


def redact(text: str) -> Tuple[str, List[Redaction]]:
    """
    Mask personal data, and report what was masked.

    Returns the safe text plus a description of each redaction, so the UI
    can tell the reader what was removed and why rather than silently
    altering what they submitted.
    """
    if not text:
        return text, []

    spans: List[Tuple[int, int, PiiRule, str]] = []

    for rule in RULES:
        for match in rule.pattern.finditer(text):
            # Some rules capture the sensitive part in a group -- the digits
            # of an OTP, not the word "OTP" before it.
            group_index = next(
                (i for i in range(1, (match.re.groups or 0) + 1) if match.group(i)),
                0,
            )
            start, end = match.span(group_index)
            raw = match.group(group_index)

            if not raw or not _is_plausible(rule.kind, raw):
                continue
            # First rule to claim a span keeps it.
            if any(start < e and s < end for s, e, _, _ in spans):
                continue
            spans.append((start, end, rule, raw))

    if not spans:
        return text, []

    spans.sort(key=lambda s: s[0])

    out: List[str] = []
    cursor = 0
    tally: Dict[str, Redaction] = {}

    for start, end, rule, raw in spans:
        out.append(text[cursor:start])
        masked = _mask(raw, rule.keep_tail)
        out.append(masked)
        cursor = end

        if rule.kind in tally:
            tally[rule.kind].count += 1
        else:
            tally[rule.kind] = Redaction(
                kind=rule.kind, label=rule.label, reason=rule.reason, preview=masked,
            )

    out.append(text[cursor:])
    return "".join(out), list(tally.values())


def summarise(redactions: List[Redaction]) -> List[dict]:
    """Redactions as JSON, for the API and the report."""
    return [
        {
            "kind": r.kind,
            "label": r.label,
            "reason": r.reason,
            "masked_as": r.preview,
            "occurrences": r.count,
        }
        for r in redactions
    ]
