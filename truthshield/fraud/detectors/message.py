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
from typing import List, Optional, Tuple

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
    code: str = ""

    @property
    def indicator_code(self) -> str:
        return self.code or f"scam_{self.category.value.lower()}"


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
            r"\b(?:e-?)?kyc\b.{0,40}\b(?:expir|pending|suspend|incomplete|block|not\s*(?:been\s*)?(?:updated|completed))",
            r"\b(?:update|complete|verify|renew)\s*(?:your\s*)?(?:e-?)?kyc\b",
            r"\bincomplete\s*(?:e-?)?kyc\b",
            r"\b(?:account|a/c|acct)\b.{0,30}\b(?:block|suspend|freez|deactivat|clos)",
            r"\bnet\s*banking\b.{0,30}\b(?:block|suspend|expir)",
            r"\bpan\s*card\b.{0,30}\b(?:updat|link|expir)",
            r"kyc.{0,30}(?:expire|ho gaya|karo|kijiye|kare|update\s*kar)",
            r"(?:khata|account).{0,20}band ho",
            r"\bdebit\s*card\b.{0,30}\b(?:block|expir|deactivat)",
            r"(?:खाता|अकाउंट|account).{0,40}(?:बंद|ब्लॉक|निलंबित)",
            r"(?:केवाईसी|kyc).{0,30}अपडेट\s*कर",
            r"வங்கி\s*கணக்கு.{0,60}(?:முடக்க|நிறுத்த|மூட)",
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
            r"\b(?:tell|give|read|share)\s*(?:me|us)\b.{0,25}\b(?:code|otp|pin)\b",
            r"\bto\s*(?:get|receive)\b.{0,60}\b(?:scan|qr\s*code|upi\s*pin|enter\s*(?:your\s*)?pin)",
            r"\bscan\b.{0,30}\bqr\b.{0,40}\bpin\b",
            r"\bapprove\b.{0,25}\b(?:request|payment|debit)\b",
            r"\bupi\s*pin\b.{0,30}\b(?:enter|share|daal)",
            r"\bpay\s*now\b.{0,30}\b(?:receive|claim|get)\b",
            r"\b\d\s*[-\s]?digit\s*(?:code|otp|number)\b.{0,80}\b(?:forward|send|share|tell|batao|bhejo)",
            r"\b(?:accidentally|by\s*mistake|galti\s*se)\b.{0,50}\b(?:code|otp)\b",
            r"\b(?:card\s*(?:number|details|no)|cvv|expiry\s*date)\b.{0,60}\b(?:cvv|expiry|pin|otp)",
            r"\b(?:enter|share|type)\b.{0,20}\b(?:upi\s*)?pin\b.{0,40}\b(?:receive|get|credit|add)",
            r"\baccept\b.{0,25}\b(?:payment|collect|money)\s*request\b",
            r"\b(?:verification\s*)?code\b.{0,60}\b(?:read|tell|give)\s*(?:it|them)?\s*(?:out\s*)?to\s*me\b",
            r"\b(?:scan|send|pay)\b.{0,40}\bqr\s*code\b.{0,60}\b(?:receive|verify|get|refund)",
        ),
    ),
    Pattern(
        FraudCategory.DELIVERY_SCAM, "Delivery or customs fee", Severity.HIGH,
        "A parcel is claimed to be held pending a small fee. The fee is the scam; "
        "the card details entered to pay it are the target.",
        "Do not pay. Track the parcel through the courier's own site or app using "
        "the reference from your original order.",
        (
            r"\b(?:parcel|package|shipment|consignment|courier)\b.{0,80}"
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
            r"\byou\s*(?:are|have\s*been|'ve\s*been)\s*(?:selected|chosen)\b.{0,40}\b(?:winner|prize|reward|gift)",
            r"\b(?:winner|won)\b.{0,40}\b(?:iphone|car|bike|gift|voucher|laptop)",
            r"\bgiveaway\b.{0,60}\bclaim",
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
            r"\bloan\b.{0,40}\b(?:is\s*)?(?:approved|sanctioned)\b.{0,80}\b(?:pay|fee|charge)",
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
            r"\b\d{1,4}\s*%\s*(?:returns?|profits?|monthly|weekly|daily|interest)",
            r"\bguaranteed\b.{0,20}\b(?:returns?|profits?|income|allotment|listing)",
            r"\b\d+\s*x\s*(?:returns?|gains?|profits?|listing\s*gains?)",
            r"\b(?:stock|share\s*market|trading|investment)\s*(?:tips?|signals?|groups?|experts?)",
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
            # Fake renewal: an invented charge, and a number to call to "cancel" it.
            r"\b(?:subscription|membership|plan)\b.{0,40}\brenewed\b.{0,160}\b(?:call|contact)\b",
            r"\b(?:did\s*not|didn'?t)\s*(?:authori[sz]e|make|place|request)\b.{0,80}\b(?:call|contact)\b",
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
            r"\b(?:income\s*tax|gst|irs|hmrc|itr)\b.{0,60}\b(?:refund|notice|penalty|due)\b.{0,80}"
            r"\b(?:click|submit|update|verify|claim|link|details|pay)",
            r"(?:आयकर|इनकम\s*टैक्स).{0,80}(?:क्लिक|अपडेट|लिंक)",
            r"\b(?:aadhaar|social security)\b.{0,35}\b(?:suspend|block|misuse|link)",
            r"\bdigital\s*arrest\b",
            r"\bfir\b.{0,40}\b(?:registered|filed|lodged)\b",
            r"\b(?:arrest\s*)?warrant\b.{0,30}\b(?:issued|will\s*be)",
            r"\b(?:number|sim|mobile\s*number)\b.{0,30}\bwill\s*be\s*(?:blocked|deactivated|suspended|disconnected)",
            r"\b(?:illegal|drugs|narcotics|contraband)\b.{0,60}\b(?:parcel|package|seized|customs)",
            r"\bseized\b.{0,40}\b(?:customs|police|cbi|ncb)",
            r"\b(?:parcel|package|courier)\b.{0,80}\b(?:drugs|narcotics|mdma|passports|contraband)",
            r"\bnarcotics\s*(?:officer|department|bureau)",
            r"\bmoney\s*laundering\b",
            r"\b(?:cbi|ncb|cyber\s*crime|crime\s*branch)\s*(?:officer|department|police|cell)",
            r"\bsim\b.{0,40}\b(?:deactivat|block|suspend|disconnect)",
            r"\btrai\b.{0,60}\b(?:block|deactivat|disconnect|suspend|guideline)",
        ),
    ),
    Pattern(
        FraudCategory.JOB_SCAM, "Paid-task job offer", Severity.HIGH,
        "Money promised for trivial online tasks (liking videos, rating products) or a "
        "recruiter reached only through a messaging handle. These schemes pay small "
        "amounts at first and then demand deposits.",
        "Do not pay any deposit or fee, and do not join task groups. A real employer "
        "never charges to hire you.",
        (
            r"\bearn\b.{0,30}\d[\d,]*(?:\s*-\s*\d[\d,]*)?\s*(?:rs\.?|inr|₹|\$|rupees)?\s*"
            r"(?:daily|per\s*day|a\s*day|weekly|per\s*week)",
            r"\b(?:liking|like|rating|rate|reviewing|review)\b.{0,30}\b(?:youtube|videos?|products?|hotels?|"
            r"posts?|tasks?)\b.{0,60}\b(?:earn|salary|income|paid)",
            r"\b(?:hr|recruiter|recruitment|hiring)\b.{0,40}\b(?:telegram|whatsapp)\b",
            r"\b(?:salary|income)\b.{0,30}\d[\d,]*\s*(?:weekly|daily|per\s*day)",
        ),
        code="scam_paid_task_job",
    ),
    Pattern(
        FraudCategory.ADVANCE_FEE, "Fee to release money", Severity.HIGH,
        "A fee must be paid before a prize, loan, refund, parcel or inheritance is "
        "released. Genuine payouts are never conditional on an upfront payment.",
        "Do not pay. Contact the organisation named through details you find yourself.",
        (
            r"\b(?:processing|clearance|release|insurance|activation|registration|handling|"
            r"transfer|verification|file|delivery)\s*(?:fees?|charges?|amount)\b.{0,60}"
            r"(?:rs\.?|inr|₹|\$|\d|pay|today|first|to\s*(?:get|receive|release))",
            r"\bto\s*(?:release|receive|get|claim|activate)\b.{0,50}\bpay\b",
            r"\b(?:refundable\s*)?security\s*deposit\b",
            r"\bpay\b.{0,40}\b(?:fees?|charges?|tax)\b.{0,40}\b(?:receive|release|claim|get|deliver)",
            r"\b(?:inheritance|unclaimed\s*(?:funds?|estate|money|deposits?)|next\s*of\s*kin)\b",
            r"\bbeneficiary\b.{0,40}\b(?:funds?|estate|million|transfer)",
        ),
    ),
    Pattern(
        FraudCategory.UTILITY_SCAM, "Disconnection threat", Severity.HIGH,
        "Electricity, gas or phone service is said to be cut off tonight unless you "
        "call a number or pay now. Providers send notices on bills and in their apps, "
        "not from a mobile number with a same-day deadline.",
        "Do not call the number given. Check your account in the provider's official "
        "app or on the number printed on your bill.",
        (
            r"\b(?:electricity|power|bijli|light|gas)\b.{0,60}\b(?:disconnect|cut|kaat|katega|kat\s*jayegi|"
            r"band\s*ho|will\s*be\s*stopped)",
            r"\bbill\b.{0,40}\bnot\s*(?:been\s*)?updat",
            r"\bbill\s*update\s*nahi",
            r"\belectricity\s*(?:officer|department\s*officer)",
            r"बिजली.{0,60}(?:काट|बंद)",
        ),
    ),
    Pattern(
        FraudCategory.SOCIAL_ENGINEERING, "Impersonating someone you know", Severity.HIGH,
        "A family member, friend or manager writing from a new number or in a rush, "
        "asking for money or gift cards. The urgency and the new channel are what "
        "stop you checking.",
        "Call the person on the number you already have for them before sending anything.",
        (
            r"\b(?:new\s*number|changed\s*my\s*number|lost\s*my\s*phone|dropped\s*my\s*phone|"
            r"phone\s*(?:broke|is\s*broken|got\s*damaged))\b.{0,160}\b(?:transfer|send|pay|money|bill)",
            r"\b(?:gift\s*cards?|google\s*play\s*(?:gift\s*)?cards?|itunes\s*cards?|"
            r"amazon\s*(?:gift\s*)?vouchers?)\b.{0,80}\b(?:codes?|send|buy|scratch)",
            r"\b(?:i\s*am|i'm)\s*(?:in\s*a\s*meeting|travell?ing|busy)\b.{0,80}\b(?:buy|transfer|pay|send)",
        ),
        code="scam_impersonation_known_contact",
    ),
    Pattern(
        FraudCategory.SOCIAL_ENGINEERING, "Request for secrecy", Severity.MEDIUM,
        "The sender asks you not to call, not to tell anyone, or to keep the request "
        "confidential. Secrecy cuts you off from the one check that would expose a scam.",
        "Tell someone you trust about the request before acting on it.",
        (
            r"\b(?:don'?t|do\s*not|can'?t|cannot)\s*(?:call|talk|tell\s*any(?:one|body))\b",
            r"\b(?:strictly\s*)?confidential\b",
            r"\bkeep\s*(?:this|it)\s*(?:secret|between\s*us|confidential)",
        ),
        code="secrecy_request",
    ),
    Pattern(
        FraudCategory.ROMANCE_SCAM, "Affection paired with a payment", Severity.MEDIUM,
        "Terms of endearment alongside a parcel, gift or fee. A gift that needs you to "
        "pay to receive it is a standard romance-scam script.",
        "Do not pay to receive a gift. Talk it through with someone you trust first.",
        (
            r"\b(?:my\s*love|sweetheart|darling|honey|my\s*dear)\b.{0,160}\b(?:customs|clearance|gift\s*box|"
            r"parcel|fee|transfer)",
        ),
    ),
    Pattern(
        FraudCategory.PHISHING, "Billing or account pretext", Severity.MEDIUM,
        "A failed payment or a held account is used as the reason to \"update\" card "
        "or sign-in details through a link.",
        "Open the service's own app or type its address yourself to check your billing.",
        (
            r"\b(?:payment|billing|card)\b.{0,40}\b(?:declined|failed|unsuccessful)\b.{0,100}"
            r"\b(?:update|verify|confirm)",
            r"\b(?:membership|subscription|account)\b.{0,20}\b(?:on\s*hold|suspended|paused)",
            r"\bmailbox\b.{0,40}\b(?:full|exceeded|limit)",
        ),
        code="scam_billing_pretext",
    ),
)

# Urgency is not a category on its own -- plenty of honest messages are
# urgent -- but combined with a category it sharpens the finding, because
# pressure is what stops someone checking.
URGENCY_RE = re.compile(
    r"\b(?:immediately|urgent(?:ly)?|(?:within|in)\s*\d+\s*(?:hours?|hrs?|minutes?|mins?)\b|"
    r"tonight|aaj\s*raat|expires?\s*today|ends\s*tonight|"
    r"today\s*itself|right\s*now|last\s*chance|final\s*(?:notice|warning)|"
    r"turant|abhi|jaldi|fauran)\b",
    re.IGNORECASE,
)

CODE_SWITCH_RE = re.compile(
    r"\b(?:aapka|aapke|apna|karo|kijiye|kare|kar\s*lo|ho\s*gaya|hai|nahi|"
    r"turant|abhi|jaldi|paisa|rupaye|khata|band|link\s*par|click\s*karo)\b",
    re.IGNORECASE,
)


# Genuine notices are full of the same words as scams, negated: "do not
# share this OTP with anyone", "never click links", "no processing fee".
# A pattern occurrence is skipped when it is negated, either just before the
# match or inside it ("your OTP -- do not share it").
_NEGATION_BEFORE = re.compile(r"(?:\b(?:do\s*not|don'?t|never|not\s*to|no|zero|without|kabhi\s*bhi)\s*\S*\s*)$")
_WEAK_NEGATION = re.compile(r"(?:no|zero|without)\b")
_FEE_RE = re.compile(r"\b(?:fees?|charges?|cost|deposit)\b")
_NEGATION_INSIDE = re.compile(r"\b(?:do\s*not|don'?t|never|not\s*to)\b")
# Awareness messages describe the scam: "beware of digital arrest scams".
_AWARENESS_BEFORE = re.compile(r"\b(?:beware\s*of|be\s*aware\s*of|alert\s*about|warn(?:s|ing)?\s*(?:about|of)|"
                               r"scams?\s*(?:like|such\s*as)|report)\b[^.!?]*$")
# A delivery OTP is meant to be shown to the courier at the door.
_ROUTINE_AFTER = re.compile(r"^.{0,40}\b(?:delivery\s*(?:agent|partner|executive|boy|person)|at\s*the\s*time\s*of\s*delivery)")
_SECRECY_CODES = ("don't", "do not", "can't", "cannot", "dont")


def _first_affirmative(expression: str, text: str) -> Optional[str]:
    """The first match of `expression` in `text` that is not negated, or None."""
    for found in re.finditer(expression, text, re.IGNORECASE | re.DOTALL):
        span = found.group(0)
        before = text[max(0, found.start() - 25):found.start()]
        # The secrecy pattern is itself a negation ("don't call"): judge it by
        # what comes before only.
        is_secrecy = span.lstrip().startswith(_SECRECY_CODES)
        negation = _NEGATION_BEFORE.search(before)
        if negation and (not _WEAK_NEGATION.match(negation.group(0).strip()) or _FEE_RE.search(span)):
            continue
        if _AWARENESS_BEFORE.search(text[max(0, found.start() - 60):found.start()]):
            continue
        if _ROUTINE_AFTER.search(text[found.end():found.end() + 60]):
            continue
        if not is_secrecy and _NEGATION_INSIDE.search(span):
            continue
        return span
    return None


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
                found = _first_affirmative(expression, lowered)
                if found:
                    matched.append((pattern, found[:110].strip()))
                    break

        if not matched:
            return None

        indicators = [
            Indicator(
                code=p.indicator_code,
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
