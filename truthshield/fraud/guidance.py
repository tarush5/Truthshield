"""
"What should I do now?"

The part of a fraud tool that actually helps. A risk score tells someone
they have a problem; this tells them what to do about it, and the right
answer differs sharply by category -- ignoring a prize scam is correct,
while ignoring a bank-impersonation message is not, because if the message
was real there is something genuine to attend to.

Three rules the wording follows throughout:

**Never alarmist.** Someone reading this may have already sent money, and
panic produces worse decisions than the scam did. The tone is procedural.

**Never accusatory about a person.** For romance and job scams especially,
the finding is about a *pattern in the messages*, not a verdict on someone's
partner or recruiter. The guidance says "these patterns" rather than "this
person", because being wrong about that causes real harm.

**Always includes the already-happened case.** Most guidance assumes the
reader is deciding whether to act. Many are looking this up afterwards, and
"what if I already paid" is the question they actually came with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from truthshield.fraud.contract import FraudCategory


@dataclass(frozen=True)
class Guidance:
    headline: str
    do_now: List[str]
    do_not: List[str]
    if_already_acted: List[str]
    verify_how: str = ""

    def as_dict(self) -> dict:
        return {
            "headline": self.headline,
            "do_now": self.do_now,
            "do_not": self.do_not,
            "if_already_acted": self.if_already_acted,
            "verify_how": self.verify_how,
        }


_UNIVERSAL_AFTER = [
    "Write down what happened and when, while it is fresh.",
    "Keep the original message — do not delete it. It is evidence.",
]

GUIDANCE: Dict[FraudCategory, Guidance] = {
    FraudCategory.PHISHING: Guidance(
        headline="Do not sign in through this link.",
        do_now=[
            "Close the page without entering anything.",
            "If you need to check your account, type the address yourself or use the official app.",
        ],
        do_not=[
            "Do not enter a password, card number or one-time code.",
            "Do not reply to the message asking whether it is genuine — a scammer will say yes.",
        ],
        if_already_acted=[
            "Change the password for that account immediately, and anywhere you reused it.",
            "Turn on two-factor authentication if it is not already on.",
            "Contact the organisation through its official number and tell them what happened.",
            *_UNIVERSAL_AFTER,
        ],
        verify_how="Reach the organisation by typing its address yourself, never by following a link you were sent.",
    ),
    FraudCategory.BANK_IMPERSONATION: Guidance(
        headline="Contact your bank yourself — not through this message.",
        do_now=[
            "Call the number printed on your bank card or shown in its official app.",
            "Ask them directly whether anything actually needs your attention.",
        ],
        do_not=[
            "Do not use any phone number or link contained in the message.",
            "Do not share a one-time code, PIN or password. Your bank will never ask for one.",
        ],
        if_already_acted=[
            "Call your bank now and tell them exactly what you shared.",
            "Ask them to freeze the card or account if card or login details were given.",
            *_UNIVERSAL_AFTER,
        ],
        verify_how="Only the number on your physical card or in the official app is safe to trust.",
    ),
    FraudCategory.PAYMENT_SCAM: Guidance(
        headline="Do not approve the request or share the code.",
        do_now=[
            "Decline or ignore any payment request you did not start yourself.",
            "Check your account through the official app to see what is actually pending.",
        ],
        do_not=[
            "Never share a one-time code. Entering a PIN to *receive* money is not a thing — it only ever sends.",
            "Do not approve a 'collect request' to receive a refund.",
        ],
        if_already_acted=[
            "Report the transaction to your bank or payment provider immediately — speed matters most here.",
            "In India, report to the national cybercrime helpline on 1930.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.DELIVERY_SCAM: Guidance(
        headline="Check the parcel through the courier, not the message.",
        do_now=[
            "Open the courier's own app or site and track using the reference from your original order.",
            "If you are not expecting a delivery, simply ignore the message.",
        ],
        do_not=[
            "Do not pay a fee through a link. Genuine customs charges are not collected this way.",
            "Do not enter card details to release a parcel.",
        ],
        if_already_acted=[
            "Contact your card issuer and ask them to stop the payment and reissue the card.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.LOTTERY_PRIZE: Guidance(
        headline="Ignore it. A genuine prize never costs money to collect.",
        do_now=["Delete the message and block the sender."],
        do_not=[
            "Do not pay any fee, tax or charge to release a prize.",
            "Do not send identity documents or bank details.",
        ],
        if_already_acted=[
            "Contact your bank to try to stop or reverse the payment.",
            "Expect follow-up contact — people who pay once are contacted again, sometimes by someone offering to recover the money for a further fee.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.JOB_SCAM: Guidance(
        headline="A real employer never charges you to be hired.",
        do_now=[
            "Look up the company independently and contact it through its own published details.",
            "Check that the recruiter's email uses the company's real domain.",
        ],
        do_not=[
            "Do not pay a registration, training or security fee.",
            "Do not let anyone route money through your account — that is money laundering, and the account holder carries the consequences.",
            "Do not send identity documents before you have verified the employer.",
        ],
        if_already_acted=[
            "Stop any further payments and tell your bank.",
            "If you sent identity documents, watch for accounts opened in your name and consider a credit freeze.",
            *_UNIVERSAL_AFTER,
        ],
        verify_how="Find the company's number yourself and ask whether the role and the recruiter are real.",
    ),
    FraudCategory.LOAN_SCAM: Guidance(
        headline="Legitimate lenders take their fees from the loan, not before it.",
        do_now=[
            "Check whether the lender is registered with your financial regulator.",
            "Read what the app or lender asks permission to access before installing anything.",
        ],
        do_not=[
            "Do not pay an advance or processing fee to receive a loan.",
            "Do not grant an app access to your contacts or photos — that access is used for coercion later.",
        ],
        if_already_acted=[
            "Revoke the app's permissions and uninstall it.",
            "Report threats or harassment to the police; harassment over a loan is itself an offence in most places.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.INVESTMENT_SCAM: Guidance(
        headline="Guaranteed returns do not exist.",
        do_now=[
            "Check the firm's registration with your market regulator before anything else.",
            "Be especially careful if you were added to a group chat or approached out of the blue.",
        ],
        do_not=[
            "Do not send money to a platform you cannot independently verify.",
            "Do not be reassured by a small withdrawal working — allowing early withdrawals is how trust is built before the larger deposit.",
        ],
        if_already_acted=[
            "Stop sending money now, including any 'tax' or 'release fee' demanded to withdraw.",
            "Report it to your bank and to your financial regulator.",
            "Be wary of anyone offering to recover your funds for a fee — that is a common follow-up scam.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.CRYPTO_SCAM: Guidance(
        headline="Never share a recovery phrase. It is the wallet.",
        do_now=[
            "If you entered a seed phrase anywhere, move any remaining funds to a new wallet now.",
            "Disconnect the site from your wallet and revoke its token approvals.",
        ],
        do_not=[
            "Never type a seed or recovery phrase into any site, app or person. No legitimate support ever needs it.",
            "Do not send crypto to 'verify' a wallet or claim an airdrop.",
        ],
        if_already_acted=[
            "Crypto transfers cannot be reversed — securing what remains is the priority.",
            "Revoke approvals for the site, and treat the compromised wallet as permanently unsafe.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.TECH_SUPPORT: Guidance(
        headline="Do not install anything or grant remote access.",
        do_now=[
            "Hang up or close the window. Genuine support does not contact you first about a problem.",
            "If you are worried, contact the company through its official site.",
        ],
        do_not=[
            "Do not install remote-access software such as AnyDesk or TeamViewer at someone's request.",
            "Do not let anyone guide you through your banking app.",
        ],
        if_already_acted=[
            "Disconnect from the internet and uninstall any software they had you install.",
            "Change passwords from a different device, and contact your bank if banking was opened while they had access.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.GOVERNMENT_IMPERSONATION: Guidance(
        headline="No agency demands immediate payment by message or call.",
        do_now=[
            "Hang up and look up the agency's number independently if you want to check.",
            "Remember that real legal processes arrive in writing and allow time to respond.",
        ],
        do_not=[
            "Do not pay anything to avoid arrest, a fine or a penalty.",
            "Do not stay on a video call with anyone claiming to be police — pressure and isolation are the method.",
        ],
        if_already_acted=[
            "Report it to the police and to your bank immediately.",
            "In India, the cybercrime helpline is 1930.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.ROMANCE_SCAM: Guidance(
        headline="These patterns are worth pausing on — but they are about the messages, not a verdict on a person.",
        do_now=[
            "Take time before sending anything. Genuine attachment survives a delay; pressure does not.",
            "Try a reverse image search on any photos you were sent.",
            "Tell someone you trust what is happening and see how it sounds out loud.",
        ],
        do_not=[
            "Do not send money, gift cards or crypto to someone you have not met in person.",
            "Do not invest through someone you met online, however well the early returns look.",
        ],
        if_already_acted=[
            "Contact your bank — speed matters for any chance of recovery.",
            "This is common and it is not a failure of judgement; these approaches are deliberate and well practised.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.ECOMMERCE_SCAM: Guidance(
        headline="Pay in a way that can be reversed.",
        do_now=[
            "Use a card or the marketplace's own checkout, which carry buyer protection.",
            "Check how long the site has existed and whether its contact details are real.",
        ],
        do_not=[
            "Do not pay by bank transfer, UPI or crypto to a seller you do not know — those cannot be reversed.",
            "Do not move the conversation off the marketplace at a seller's request.",
        ],
        if_already_acted=[
            "Raise a dispute with your card issuer or the marketplace straight away.",
            *_UNIVERSAL_AFTER,
        ],
    ),
    FraudCategory.SOCIAL_ENGINEERING: Guidance(
        headline="Slow down. Pressure is the technique.",
        do_now=[
            "Stop and verify through a channel you chose, not one you were given.",
            "Tell someone else what is being asked of you before acting.",
        ],
        do_not=[
            "Do not act on urgency or secrecy. Both exist to stop you checking.",
            "Do not share codes, passwords or remote access, whoever is asking.",
        ],
        if_already_acted=[
            "Change any credentials you shared, from a different device.",
            "Contact the affected organisation through its official channel.",
            *_UNIVERSAL_AFTER,
        ],
    ),
}

# Used when a detector flags risk without settling a category. Deliberately
# generic and non-alarmist -- the alternative is guessing, and wrong advice
# is worse than cautious advice.
FALLBACK = Guidance(
    headline="Treat this as unverified until you have checked it independently.",
    do_now=[
        "Verify through a channel you found yourself, not one supplied in the message.",
        "Take your time. Anything genuine will still be there in an hour.",
    ],
    do_not=[
        "Do not send money, credentials or documents based on this message alone.",
        "Do not follow links or call numbers it provides.",
    ],
    if_already_acted=[
        "Contact your bank or the affected organisation through its official channel.",
        *_UNIVERSAL_AFTER,
    ],
)


def for_category(category: FraudCategory) -> Guidance:
    """Safety guidance for a category, always returning something usable."""
    return GUIDANCE.get(category, FALLBACK)


def catalogue() -> List[dict]:
    """Every category's guidance, for the standalone Safety Centre page."""
    return [
        {"category": category.value, **guidance.as_dict()}
        for category, guidance in GUIDANCE.items()
    ]
