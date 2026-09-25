"""
Scam categories in a message.

The existing `detectors/fraud.py` answers "does this writing use the
techniques of a scam" -- urgency, false authority, manufactured secrecy.
That is a register question, and it is deliberately category-blind.

This answers the next question: *which* scam. The distinction matters
because the safety advice diverges completely. "Your parcel is held pending
a customs fee" and "your account will be blocked unless you complete KYC"
are both urgent impersonations, and the right response to one is to ignore
it while the right response to the other is to call the bank on the number
printed on the card.

Code-switched text is handled as a first-class case rather than as an
afterthought. A substantial share of real scam traffic in India is Hindi or
Hinglish in Latin script -- "aapka KYC expire ho gaya hai, turant link par
click karo" -- and an English-only pattern set scores that at zero while a
human reads it instantly.

Scored through the shared contract, so a category here combines with a URL
finding from the same message rather than competing with it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from truthshield.fraud.classify import Classification, InputKind
from truthshield.fraud.contract import (
    FraudCategory, FraudFinding, Indicator, Severity, score_from_indicators,
)
from truthshield.fraud.registry import FraudDetector, register


@dataclass(frozen=True)
class Pattern:
    """One scam category and how it announces itself."""

    category: FraudCategory
    title: str
    severity: Severity
    explanation: str
    action: str
    patterns: Tuple[str, ...]


# Written against how these messages are actually worded, including the
# Latin-script Hindi that carries a large share of them.
PATTERNS: Tuple[Pattern, ...] = (
    Pattern(
        FraudCategory.BANK_IMPERSONATION, "Bank impersonation", Severity.HIGH,
        "The message claims to be your bank and pressures you to act on a link. "
        "Banks do not ask customers to restore an account through a message link.",
        "Do not use the link. Call your bank on the number printed on your card "
        "or in its official app.",
        (
            r"\b(?:kyc)\b.{0,40}\b(?:expir|updat|pending|complet|suspend)",
            r"\b(?:account|a/c|acct)\b.{0,30}\b(?:block|suspend|freez|deactivat|clos)",
            r"\bnet\s*banking\b.{0,30}\b(?:block|suspend|expir)",
            r"\bpan\s*card\b.{0,30}\b(?:updat|link|expir)",
            r"kyc.{0,30}(?:expire|ho gaya|karo|kijiye|update)",
            r"(?:khata|account).{0,20}band ho",
            r"\bdebit\s*card\b.{0,30}\b(?:block|expir|deactivat)",
        ),
    ),
    Pattern(
        FraudCategory.PAYMENT_SCAM, "Payment or OTP request", Severity.HIGH,
        "The message asks for a one-time code, or asks you to approve a payment "
        "request. A code is what authorises a transaction — anyone asking for it "
        "is asking to move your money.",
        "Never share an OTP or approve a request you did not start. No genuine "
        "organisation will ask for one.",
        (
            r"\b(?:otp|one[\s-]?time\s*(?:password|code)|verification\s*code)\b.{0,40}"
            r"\b(?:share|send|tell|provide|forward|batao|bhejo|do)\b",
            r"\b(?:share|send|tell|provide|forward)\b.{0,30}\b(?:otp|pin|cvv)\b",
            r"\bcollect\s*request\b",
            r"\bapprove\b.{0,25}\b(?:request|payment|debit)\b",
            r"\bupi\s*pin\b.{0,30}\b(?:enter|share|daal)",
            r"\bpay\s*now\b.{0,30}\b(?:receive|claim|get)\b",
        ),
    ),
    Pattern(
        FraudCategory.DELIVERY_SCAM, "Delivery or customs fee", Severity.HIGH,
        "A parcel is claimed to be held pending a small fee. The fee is the scam; "
        "the card details entered to pay it are the target.",
        "Do not pay. Track the parcel through the courier's own site or app using "
        "the reference from your original order.",
        (
            r"\b(?:parcel|package|shipment|consignment|courier)\b.{0,50}"
            r"\b(?:held|hold|pending|customs|duty|fee|charge|undeliver|address)",
            r"\b(?:customs|import)\s*(?:duty|fee|charge|clearance)\b",
            r"\b(?:delivery|shipping)\s*(?:fee|charge|attempt failed)\b",
            r"\b(?:reschedule|confirm)\b.{0,25}\bdelivery\b",
        ),
    ),
    Pattern(
        FraudCategory.LOTTERY_PRIZE, "Prize or lottery win", Severity.HIGH,
        "An unexpected win that requires a fee, a form or personal details to "
        "release. A genuine prize never requires a payment to collect.",
        "Ignore it. Never pay a fee or send documents to release a prize you did "
        "not enter for.",
        (
            r"\b(?:congratulations|congrats)\b.{0,60}\b(?:won|winner|selected|lucky)",
            r"\byou(?:'ve| have)?\s*(?:been\s*)?(?:won|win|selected)\b.{0,50}"
            r"\b(?:lottery|lakh|crore|prize|reward|gift|cash)",
            r"\blucky\s*(?:draw|winner)\b",
            r"\bclaim\b.{0,25}\b(?:prize|reward|amount|money)\b",
            r"\binaam\b|\blottery\s*jeet",
        ),
    ),
    Pattern(
        FraudCategory.JOB_SCAM, "Job or task offer", Severity.MEDIUM,
        "An unsolicited job or paid-task offer, typically promising daily earnings "
        "for trivial work. These lead to a registration fee or to money-laundering "
        "through your account.",
        "Do not pay any fee and do not let anyone route money through your account. "
        "A real employer never charges to hire you.",
        (
            r"\b(?:work from home|part[\s-]?time job|daily (?:income|earning|payout))\b",
            r"\bearn\b.{0,25}(?:rs\.?|inr|₹|\$)\s*\d[\d,]*.{0,20}\b(?:daily|per day|day)\b",
            r"\b(?:registration|security|training)\s*(?:fee|deposit|amount)\b",
            r"\b(?:like|rate|review)\b.{0,25}\b(?:task|video|product|hotel)\b.{0,25}\bearn",
            r"\bjob\s*offer\b.{0,40}\bno\s*(?:interview|experience)\b",
        ),
    ),
    Pattern(
        FraudCategory.LOAN_SCAM, "Loan or credit offer", Severity.MEDIUM,
        "A pre-approved loan requiring an upfront fee, or demanding extensive "
        "personal documents before any agreement. Legitimate lenders take their "
        "charges from the disbursed amount.",
        "Do not pay an advance fee and do not send identity documents. Check the "
        "lender is registered with your financial regulator first.",
        (
            r"\b(?:pre[\s-]?approved|instant)\s*(?:loan|credit|personal loan)\b",
            r"\bloan\b.{0,40}\b(?:no\s*documents?|without\s*documents?|same day|"
            r"within\s*\d+\s*(?:minute|hour))\b",
            r"\b(?:processing|advance|file)\s*(?:fee|charge)\b.{0,30}\bloan\b",
            r"\bloan\s*(?:approved|sanction)\b.{0,40}\bpay\b",
        ),
    ),
    Pattern(
        FraudCategory.INVESTMENT_SCAM, "Investment or trading offer", Severity.HIGH,
        "An investment promising guaranteed or outsized returns. Returns cannot be "
        "guaranteed, and the promise is the clearest marker of a scheme.",
        "Do not send money. Check the firm's registration with your market "
        "regulator before considering anything further.",
        (
            r"\bguaranteed\s*(?:return|profit|income)\b",
            r"\b(?:double|triple|2x|3x)\b.{0,25}\b(?:money|investment|capital)\b",
            r"\b(?:\d{2,4})\s*%\s*(?:return|profit|monthly|weekly|daily)\b",
            r"\b(?:risk[\s-]?free|no\s*risk)\b.{0,30}\b(?:invest|return|trading)\b",
            r"\b(?:trading|investment)\s*(?:tip|signal|group|expert)\b",
        ),
    ),
    Pattern(
        FraudCategory.CRYPTO_SCAM, "Cryptocurrency request", Severity.HIGH,
        "A request involving crypto payment, an airdrop, or a wallet phrase. Crypto "
        "transfers cannot be reversed, which is why scams ask for them.",
        "Never share a seed phrase or recovery words with anyone — they are the "
        "wallet. Do not send crypto to claim anything.",
        (
            r"\b(?:seed|recovery|mnemonic)\s*(?:phrase|words?)\b",
            r"\b(?:send|transfer|deposit)\b.{0,25}\b(?:btc|bitcoin|eth|usdt|crypto)\b",
            r"\bairdrop\b.{0,30}\b(?:claim|connect|wallet)\b",
            r"\bconnect\s*(?:your\s*)?wallet\b",
        ),
    ),
    Pattern(
        FraudCategory.TECH_SUPPORT, "Technical support impersonation", Severity.HIGH,
        "A claimed support agent reporting a problem and directing you to install "
        "software or grant remote access — which hands over the device.",
        "Do not install anything or grant remote access. Contact the company "
        "through its official site if you think there is a real issue.",
        (
            r"\b(?:anydesk|teamviewer|quick\s*support|remote\s*access)\b",
            r"\b(?:virus|malware|infected)\b.{0,40}\b(?:call|contact|support)\b",
            r"\b(?:microsoft|apple|google)\s*(?:support|technician|engineer)\b",
            r"\binstall\b.{0,30}\bapp\b.{0,30}\b(?:resolve|fix|verify|refund)\b",
        ),
    ),
    Pattern(
        FraudCategory.GOVERNMENT_IMPERSONATION, "Government or legal threat", Severity.HIGH,
        "A claimed official body threatening arrest, a fine or legal action unless "
        "you act immediately. Authorities do not demand payment by message.",
        "Do not pay or respond. Contact the agency directly through its published "
        "number if you are unsure.",
        (
            r"\b(?:police|court|arrest|warrant|legal action|summons)\b.{0,50}"
            r"\b(?:pay|fine|settle|immediately|penalty)\b",
            r"\b(?:income\s*tax|gst|irs|hmrc)\b.{0,40}\b(?:refund|notice|penalty|due)\b",
            r"\b(?:aadhaar|social security)\b.{0,35}\b(?:suspend|block|misuse|link)\b",
            r"\bdigital\s*arrest\b",
        ),
    ),
)

# Urgency is not a category on its own -- plenty of honest messages are
# urgent -- but combined with a category it sharpens the finding, because
# pressure is what stops someone checking.
URGENCY_RE = re.compile(
    r"\b(?:immediately|urgent(?:ly)?|within\s*\d+\s*(?:hour|hr|minute|min)|"
    r"today\s*itself|right\s*now|last\s*chance|final\s*(?:notice|warning)|"
    r"turant|abhi|jaldi|fauran)\b",
    re.IGNORECASE,
)

CODE_SWITCH_RE = re.compile(
    r"\b(?:aapka|aapke|apna|karo|kijiye|kare|kar\s*lo|ho\s*gaya|hai|nahi|"
    r"turant|abhi|jaldi|paisa|rupaye|khata|band|link\s*par|click\s*karo)\b",
    re.IGNORECASE,
)


class MessageScamDetector(FraudDetector):
    """Which scam a message is, not merely that it reads like one."""

    name = "message_scam"
    describes = "Scam category in an SMS, chat or short message"
    handles = (InputKind.SMS, InputKind.TEXT, InputKind.EMAIL_MESSAGE)

    MIN_WORDS = 5

    def applies_to(self, text: str, classification: Classification) -> bool:
        return bool(text) and len(text.split()) >= self.MIN_WORDS

    def _run(self, text: str, classification: Classification) -> Optional[FraudFinding]:
        lowered = text.lower()

        matched: List[Tuple[Pattern, str]] = []
        for pattern in PATTERNS:
            for expression in pattern.patterns:
                found = re.search(expression, lowered, re.IGNORECASE | re.DOTALL)
                if found:
                    matched.append((pattern, found.group(0)[:110].strip()))
                    break

        if not matched:
            return None

        indicators = [
            Indicator(
                code=f"scam_{p.category.value.lower()}",
                title=p.title,
                severity=p.severity,
                explanation=p.explanation,
                evidence=evidence,
            )
            for p, evidence in matched
        ]

        urgency = URGENCY_RE.search(text)
        if urgency:
            indicators.append(Indicator(
                code="urgency_pressure", title="Time pressure", severity=Severity.MEDIUM,
                explanation=(
                    "The message pushes for an immediate response. Pressure is "
                    "applied to stop you checking with anyone first."
                ),
                evidence=urgency.group(0),
            ))

        # A link inside a categorised scam message is materially worse than a
        # link on its own: the message supplies the pretext for following it.
        urls = classification.entities.get("urls") or []
        if urls:
            indicators.append(Indicator(
                code="actionable_link", title="Link to act on", severity=Severity.MEDIUM,
                explanation=(
                    "The message pairs its story with a link, which is how the "
                    "pretext gets turned into a credential or a payment."
                ),
                evidence=urls[0][:110],
            ))

        code_switched = len(CODE_SWITCH_RE.findall(text)) >= 2
        if code_switched:
            indicators.append(Indicator(
                code="code_switched", title="Mixed-language phrasing", severity=Severity.INFO,
                explanation=(
                    "Written in mixed Hindi and English, which is ordinary in "
                    "genuine messages too — noted only so the language is not "
                    "mistaken for a signal either way."
                ),
                evidence=", ".join(CODE_SWITCH_RE.findall(text)[:4]),
            ))

        lead = matched[0][0]
        score = score_from_indicators(indicators)

        return FraudFinding(
            detector=self.name,
            category=lead.category,
            risk_score=score,
            confidence=min(0.80, 0.42 + 0.13 * len(matched)),
            summary=(
                f"Reads as {lead.title.lower()}"
                + (f", with {len(matched) - 1} other scam pattern"
                   f"{'' if len(matched) == 2 else 's'}" if len(matched) > 1 else "")
                + "."
            ),
            indicators=indicators,
            recommended_action=lead.action,
            limitations=[
                "Judged from wording alone: the sender, any link and any attachment "
                "were not independently verified.",
                "Wording overlaps between genuine notifications and scams — treat "
                "this as a reason to check, not as proof.",
            ],
            methods=["scam-category-rules"],
            extra={"categories": [p.category.value for p, _ in matched]},
        )


register(MessageScamDetector())
