"""
Explanation layer.

Deterministic: every sentence is assembled from the risk assessment and the
engine results, so each one can be traced to a signal, a source or a stated
limitation. No language model writes into the explanation in Phase 1; the
`llm` slot stays null and says why, rather than being filled with prose that
could not be traced back to anything.
"""

from __future__ import annotations

from typing import List, Sequence

from truthshield.fraud.contract import FraudCategory
from truthshield.fraud.guidance import for_category
from truthshield.investigations.risk import RiskAssessment
from truthshield.investigations.types import EngineResult

PHISHING_CODES = {
    "punycode_host", "mixed_script_host", "ip_host", "brand_outside_domain", "typosquat_domain",
    "brand_in_unofficial_domain", "credential_path", "userinfo_in_url", "insecure_credential_page",
    "credential_form_offsite", "insecure_password_form", "brand_mismatch_page", "credential_request",
}
PHISHING_CATEGORIES = {"PHISHING", "SMISHING", "BANK_IMPERSONATION", "GOVERNMENT_IMPERSONATION"}

MISINFORMATION_ACTIONS = {
    "headline": "Check the sources before sharing.",
    "do_now": [
        "Read the retrieved sources on the Evidence tab, starting with official and primary ones.",
        "Look for the claim on the website of the organisation it names.",
    ],
    "do_not": ["Do not forward it until it has been confirmed by a source you trust."],
    "if_already_acted": ["If you shared it, consider posting a correction with the source you found."],
    "verify_how": "Compare the claim with official statements and established fact-checkers.",
}

GENERAL_ACTIONS = {
    "headline": "No strong warning signs were found — stay cautious.",
    "do_now": [
        "If the content arrived unexpectedly, verify it through a channel you already trust.",
    ],
    "do_not": ["Do not share one-time codes, passwords or card details in reply to any message."],
    "if_already_acted": [],
    "verify_how": "Contact the organisation directly using details from its official website or app.",
}


def classify(assessment: RiskAssessment, engines: Sequence[EngineResult]) -> tuple:
    """(classification label, fraud category) for display and routing."""
    categories: List[str] = []
    for engine in engines:
        categories.extend(engine.artifacts.get("fraud_categories", []))

    codes = {c.code for c in assessment.contributions if c.points > 0}
    url_points = assessment.families.get("url").points if "url" in assessment.families else 0
    evidence_points = assessment.families.get("evidence").points if "evidence" in assessment.families else 0

    if assessment.score < 15:
        # Weak signals are still listed on the page, but a label saying
        # "potential manipulation" over an 11/100 would overstate them.
        return "no_significant_signals", FraudCategory.NONE
    if codes & PHISHING_CODES or set(categories) & PHISHING_CATEGORIES or url_points >= assessment.score * 0.4 > 0:
        lead = next((c for c in categories if c in PHISHING_CATEGORIES), "PHISHING")
        return "potential_phishing", FraudCategory(lead)
    if categories:
        return "potential_scam", FraudCategory(categories[0])
    if evidence_points > 0:
        return "potential_misinformation", FraudCategory.NONE
    if any(c.startswith("manipulation_") for c in codes):
        return "potential_manipulation", FraudCategory.NONE
    return "suspicious_content", FraudCategory.UNKNOWN


def summarise(assessment: RiskAssessment, classification: str) -> str:
    label = classification.replace("_", " ")
    top = [c for c in assessment.contributions if c.points > 0][:3]
    if not top:
        return (
            f"Risk {assessment.score}/100 ({assessment.level}). No risk signals were detected by the "
            "checks that ran. That is not confirmation that the content is safe — see what was not checked."
        )
    drivers = "; ".join(f"{c.title.lower()} (+{c.points})" for c in top)
    return (
        f"Risk {assessment.score}/100 ({assessment.level}, {assessment.confidence_band.lower().replace('_', ' ')} "
        f"confidence): {label}. Main drivers: {drivers}."
    )


def recommended_actions(classification: str, category: FraudCategory) -> dict:
    if classification == "potential_misinformation":
        return MISINFORMATION_ACTIONS
    if classification in ("no_significant_signals",):
        return GENERAL_ACTIONS
    return for_category(category).as_dict()


def explanation(assessment: RiskAssessment, classification: str) -> dict:
    return {
        "summary": summarise(assessment, classification),
        "top_signals": [
            {"code": c.code, "title": c.title, "points": c.points, "provenance": c.provenance}
            for c in assessment.contributions[:5] if c.points > 0
        ],
        "method": "Deterministic summary of the risk contributions; every statement maps to a listed signal.",
        "llm": None,
        "llm_status": "not_used",
        "llm_note": (
            "No language model was used to write or decide anything in this investigation. "
            "LLM-written interpretation arrives in a later phase and will be labelled as such."
        ),
    }


def uncertainties(engines: Sequence[EngineResult], assessment: RiskAssessment) -> List[str]:
    out: List[str] = []
    for engine in engines:
        for limitation in engine.limitations:
            if limitation not in out:
                out.append(limitation)
    unassessed = [f for f, s in assessment.families.items() if not s.assessed]
    if unassessed:
        out.append(
            "Signal families not assessed for this input: " + ", ".join(sorted(unassessed))
            + ". They contribute nothing to the score, which is not the same as being clean."
        )
    for note in assessment.notes:
        if note not in out:
            out.append(note)
    return out
