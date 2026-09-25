"""
Email fraud, from the parts of a message a reader can actually see.

Email carries structure that SMS does not, and the structure is where the
lie usually shows. A display name is free text the sender chooses; the
address beside it is not. A Reply-To can point somewhere the From never
mentions. Those mismatches are the mechanism behind business email
compromise and invoice fraud, and they are visible without any external
lookup.

Scope, stated because it bounds what the score means: this reads headers as
*pasted*, which means it cannot verify them. SPF, DKIM and DMARC results
live in headers a webmail client does not show by default, and without them
a forged From is indistinguishable from a real one. So the detector reports
what the visible structure supports and lists authentication as unchecked,
rather than implying a verdict it has no basis for.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from truthshield.fraud.classify import Classification, InputKind
from truthshield.fraud.contract import (
    FraudCategory, FraudFinding, Indicator, Severity, score_from_indicators,
)
from truthshield.fraud.detectors.url import inspect_url
from truthshield.fraud.registry import FraudDetector, register

HEADER_RE = re.compile(
    r"^\s*(from|to|cc|bcc|reply-?to|subject|date|return-?path)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
ADDRESS_RE = re.compile(r"<([^>]+)>|([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")

# Free mailbox providers. A personal address is unremarkable in personal
# mail and a strong signal in mail claiming to be from an institution.
FREE_PROVIDERS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "outlook.com",
    "hotmail.com", "live.com", "aol.com", "proton.me", "protonmail.com",
    "mail.com", "yandex.com", "rediffmail.com", "zoho.com", "gmx.com",
})

# Names that, when used in a display name, imply an institution.
INSTITUTIONAL_WORDS = (
    "bank", "hmrc", "irs", "revenue", "tax", "police", "court", "gov",
    "support", "helpdesk", "service desk", "security team", "it team",
    "payroll", "hr ", "human resources", "accounts payable", "billing",
    "paypal", "amazon", "microsoft", "apple", "google", "netflix",
)

# Business email compromise: the instruction that makes it pay.
BEC_PATTERNS: Tuple[Tuple[str, str, str], ...] = (
    (r"\b(?:bank|account)\s*(?:details|information)\s*(?:have|has)\s*changed\b",
     "Banking details changed",
     "The message states that payment details have changed. Substituting bank "
     "details on a genuine-looking invoice is the core of invoice fraud."),
    (r"\b(?:update|change|amend)\b[^.\n]{0,30}\b(?:bank|payment|account)\s*details\b",
     "Request to change payment details",
     "A request to redirect payments. This is how invoice fraud is executed, and "
     "it is worth a phone call to a known number every time."),
    (r"\b(?:urgent|immediate)\b[^.\n]{0,40}\b(?:transfer|payment|wire|remit)\b",
     "Urgent payment instruction",
     "Urgency attached to a payment instruction. Pressure exists to stop the "
     "recipient verifying through normal channels."),
    (r"\bare you (?:at your desk|available|there)\b",
     "Availability probe",
     "A short opening message that asks only whether you are available. This is "
     "the standard first step of CEO fraud, before any request is made."),
    (r"\b(?:i(?:'m| am) )?(?:in a meeting|travelling|unavailable)\b[^.\n]{0,40}"
     r"\b(?:cannot|can't|unable to)\s*(?:talk|call|speak)\b",
     "Pre-empting verification",
     "The sender explains in advance why they cannot be reached by phone, which "
     "removes the one check that would expose the impersonation."),
    (r"\b(?:gift\s*cards?|apple\s*cards?|steam\s*cards?)\b",
     "Gift card request",
     "Gift cards are untraceable and irreversible. No employer legitimately asks "
     "staff to buy them."),
    (r"\bkeep this (?:confidential|between us)\b|\bdo not (?:discuss|tell)\b",
     "Request for secrecy",
     "Secrecy prevents the recipient from checking with a colleague, which is "
     "usually all it would take to stop this."),
)

CREDENTIAL_PATTERNS: Tuple[Tuple[str, str, str], ...] = (
    (r"\b(?:verify|confirm|validate)\b[^.\n]{0,30}\b(?:account|identity|password|email)\b",
     "Verification request",
     "Asks you to verify an account through the message itself, which is how "
     "credentials are collected."),
    (r"\b(?:account|mailbox|password)\b[^.\n]{0,40}\b(?:suspend|expire|deactivat|clos|lock)",
     "Account-closure threat",
     "Threatens loss of access unless you act. The deadline is the pressure."),
    (r"\b(?:unusual|suspicious)\s*(?:sign[\s-]?in|login|activity)\b",
     "Security-alert pretext",
     "Imitates a security alert. The genuine version of this notification never "
     "requires you to sign in through the email."),
    (r"\bstorage\s*(?:is\s*)?(?:full|exceeded)\b|\bmailbox\s*quota\b",
     "Quota pretext",
     "A storage warning used as a pretext to capture a mailbox password."),
)


def parse_headers(text: str) -> Dict[str, str]:
    """Headers as pasted. Last value wins for a repeated key."""
    return {
        name.lower().replace("-", ""): value.strip()
        for name, value in HEADER_RE.findall(text)
    }


def address_of(value: str) -> str:
    """The address inside a `Display Name <addr@host>` value."""
    match = ADDRESS_RE.search(value or "")
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip().lower()


def display_name_of(value: str) -> str:
    return re.sub(r"<[^>]*>", "", value or "").strip().strip('"').strip()


def domain_of(address: str) -> str:
    return address.rpartition("@")[2].lower() if "@" in address else ""


class EmailFraudDetector(FraudDetector):
    """Phishing and business email compromise, from visible structure."""

    name = "email_fraud"
    describes = "Phishing, BEC and invoice fraud signals in an email"
    handles = (InputKind.EMAIL_MESSAGE,)

    UNCHECKED = [
        "SPF, DKIM and DMARC were not checked — those live in full headers, "
        "which most mail clients do not show. Without them a forged sender "
        "cannot be distinguished from a real one.",
        "The sending server and its reputation were not examined.",
        "Attachments were not scanned.",
    ]

    def _run(self, text: str, classification: Classification) -> Optional[FraudFinding]:
        headers = parse_headers(text)
        indicators: List[Indicator] = []

        from_raw = headers.get("from", "")
        from_address = address_of(from_raw)
        from_display = display_name_of(from_raw)
        from_domain = domain_of(from_address)

        reply_raw = headers.get("replyto", "")
        reply_address = address_of(reply_raw)
        reply_domain = domain_of(reply_address)

        # ── Reply-To divergence ───────────────────────────────
        # The single most reliable structural signal: the reply goes
        # somewhere the sender never showed you.
        if reply_domain and from_domain and reply_domain != from_domain:
            indicators.append(Indicator(
                code="replyto_mismatch", title="Replies go to a different domain",
                severity=Severity.HIGH,
                explanation=(
                    f"The message appears to come from '{from_domain}' but replies "
                    f"are directed to '{reply_domain}'. A reply lands with whoever "
                    "controls that second domain, not the apparent sender."
                ),
                evidence=f"From: {from_domain} → Reply-To: {reply_domain}",
            ))

        # ── Display-name spoofing ─────────────────────────────
        if from_display and from_domain:
            claimed = next(
                (w.strip() for w in INSTITUTIONAL_WORDS if w in from_display.lower()),
                None,
            )
            if claimed and from_domain in FREE_PROVIDERS:
                indicators.append(Indicator(
                    code="institution_on_free_mail", title="Institution name on a personal mailbox",
                    severity=Severity.HIGH,
                    explanation=(
                        f"The sender presents as '{from_display}' but writes from "
                        f"'{from_domain}', a free personal mail provider. Banks, tax "
                        "authorities and employers use their own domains."
                    ),
                    evidence=f"{from_display} <{from_address}>",
                ))
            elif claimed and claimed not in from_domain:
                indicators.append(Indicator(
                    code="display_name_mismatch", title="Sender name does not match the domain",
                    severity=Severity.MEDIUM,
                    explanation=(
                        f"The display name says '{from_display}' while the address is "
                        f"on '{from_domain}'. A display name is free text the sender "
                        "chooses; only the domain is meaningful."
                    ),
                    evidence=f"{from_display} <{from_address}>",
                ))

        # A display name that is itself an address is a deliberate disguise:
        # many clients show only the name, so the fake address is what shows.
        if "@" in from_display and from_address and from_display.lower() != from_address:
            indicators.append(Indicator(
                code="address_as_display_name", title="Fake address used as the sender name",
                severity=Severity.HIGH,
                explanation=(
                    "The sender's display name has been set to an email address that "
                    "is not the real one. Most mail apps show only the name, so this "
                    "is what you see instead of the true sender."
                ),
                evidence=f"shows '{from_display}', actually {from_address}",
            ))

        body = text
        for pattern, title, explanation in BEC_PATTERNS:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                indicators.append(Indicator(
                    code=f"bec_{title.lower().replace(' ', '_')}",
                    title=title, severity=Severity.HIGH,
                    explanation=explanation, evidence=match.group(0)[:110],
                ))

        for pattern, title, explanation in CREDENTIAL_PATTERNS:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                indicators.append(Indicator(
                    code=f"cred_{title.lower().replace(' ', '_').replace('-', '_')}",
                    title=title, severity=Severity.MEDIUM,
                    explanation=explanation, evidence=match.group(0)[:110],
                ))

        # ── Links in the body ─────────────────────────────────
        # Reusing the URL detector's inspection rather than reimplementing
        # it: a link is equally suspicious whichever medium carried it.
        for url in (classification.entities.get("urls") or [])[:3]:
            for indicator in inspect_url(url):
                if indicator.severity in (Severity.HIGH, Severity.MEDIUM):
                    indicators.append(indicator)

        seen, unique = set(), []
        for indicator in indicators:
            if indicator.code not in seen:
                seen.add(indicator.code)
                unique.append(indicator)

        if not unique:
            return None

        bec = any(i.code.startswith("bec_") for i in unique)
        credential = any(i.code.startswith("cred_") for i in unique)
        category = (
            FraudCategory.PHISHING if credential and not bec
            else FraudCategory.SOCIAL_ENGINEERING if bec
            else FraudCategory.PHISHING
        )

        score = score_from_indicators(unique)
        strong = [i for i in unique if i.severity is Severity.HIGH]

        return FraudFinding(
            detector=self.name,
            category=category,
            risk_score=score,
            confidence=min(0.75, 0.35 + 0.10 * len(unique)),
            summary=(
                f"{len(unique)} warning sign{'' if len(unique) == 1 else 's'} in this "
                f"email: " + ", ".join(i.title.lower() for i in unique[:3]) + "."
            ),
            indicators=unique,
            recommended_action=(
                "Do not reply, follow its links, or act on any payment instruction. "
                "Confirm with the sender using a number or address you already have — "
                "never one from this message."
                if strong else
                "Verify through a channel you already trust before acting on this."
            ),
            limitations=self.UNCHECKED,
            methods=["email-structure-rules", "url-structure-rules"],
            extra={
                "from": from_address or None,
                "reply_to": reply_address or None,
                "subject": headers.get("subject"),
            },
        )


register(EmailFraudDetector())
