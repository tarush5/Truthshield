"""
Text engine.

    raw text → language → normalisation → sentences → entities → claims →
    intent → scam / phishing signals → manipulation register → injection check

The scam and manipulation checks are the 1.x detectors, called through their
own interfaces rather than re-implemented: each carries fixes found by
running against real messages (Hinglish patterns, the single-signal cap that
stopped pushy marketing outscoring a scam). This engine's job is to put
their findings into the shared Signal vocabulary with provenance attached.
"""

from __future__ import annotations

from typing import List

from truthshield.fraud.contract import Severity
from truthshield.investigations import nlp
from truthshield.investigations.engines.base import Engine
from truthshield.investigations.types import (
    EngineKind, EngineResult, Family, InvestigationContext, InvestigationType,
    ModelPredictionRecord, Provenance, Signal,
)

# 1.x detectors this engine owns. The URL structure detector belongs to the
# URL engine, so a link is scored once, by the engine that understands it.
TEXT_DETECTORS = ("message_scam", "email_fraud")

HINTS = {
    InvestigationType.MESSAGE: "SMS",
    InvestigationType.EMAIL: "EMAIL_MESSAGE",
}


class TextEngine(Engine):
    name = "text"
    version = "1.0.0"
    kind = EngineKind.HEURISTIC
    describes = "Language, entities, claims, intent, scam and manipulation signals in text"

    def applies_to(self, ctx: InvestigationContext) -> bool:
        return ctx.type is not InvestigationType.URL and bool(ctx.content.strip())

    def _signal(self, **kwargs) -> Signal:
        return Signal(engine=self.name, engine_version=self.version, **kwargs)

    def _run(self, ctx: InvestigationContext, result: EngineResult) -> None:
        text = ctx.content

        # ── Language, normalisation, segmentation ────────────
        language = nlp.detect_language(text)
        normalized, hidden = nlp.normalize(text)
        ctx.normalized = normalized
        segments = nlp.sentences(normalized)

        result.artifacts["language"] = language.as_dict()
        result.artifacts["sentence_count"] = len(segments)
        if not language.supported:
            result.limitations.append(
                f"Detected language '{language.detected}' is outside the supported set "
                f"({', '.join(nlp.SUPPORTED_LANGUAGES)}); pattern checks are tuned for those "
                "languages and may miss signals here."
            )

        if hidden:
            result.signals.append(self._signal(
                code="hidden_characters", title="Hidden characters",
                family=Family.NLP, severity=Severity.LOW, provenance=Provenance.HEURISTIC,
                explanation=(
                    "The text contains invisible zero-width characters. They are used to "
                    "break up words so keyword filters miss them."
                ),
                evidence=f"{hidden} zero-width character{'s' if hidden != 1 else ''}",
                confidence=0.7,
            ))

        # ── Entities ─────────────────────────────────────────
        entities = nlp.extract_all_entities(normalized)
        extra, ner_available = nlp.spacy_entities(normalized)
        entities.update(extra)
        result.artifacts["entities"] = {k: v for k, v in entities.items() if v}
        ctx.urls = list(dict.fromkeys(ctx.urls + entities.get("urls", [])))
        if not ner_available:
            result.limitations.append(
                "Person and location names were not extracted: no spaCy NER model is "
                "installed. URLs, contacts, amounts, dates and known organisations were."
            )

        # ── Claims ───────────────────────────────────────────
        result.artifacts["claims"] = self._claims(normalized, language.detected, result)

        # ── Intent ───────────────────────────────────────────
        intents = nlp.detect_intents(normalized)
        result.artifacts["intents"] = intents

        # ── Scam / phishing (1.x detectors) ──────────────────
        covered = self._fraud_detectors(ctx, normalized, result)

        # ── Intent signals not already covered ───────────────
        intent_codes = {i["intent"]: i for i in intents}
        if "credential_request" in intent_codes and not any(c.startswith("scam_") for c in covered):
            hit = intent_codes["credential_request"]
            result.signals.append(self._signal(
                code="credential_request", title="Credential request",
                family=Family.NLP, severity=Severity.MEDIUM, provenance=Provenance.HEURISTIC,
                explanation="The text asks for sign-in details. Legitimate services do not collect these by message.",
                evidence=hit["evidence"], confidence=0.6,
            ))
        if "prize_claim" in intent_codes and "scam_lottery_prize" not in covered:
            hit = intent_codes["prize_claim"]
            result.signals.append(self._signal(
                code="reward_language", title="Suspicious reward language",
                family=Family.NLP, severity=Severity.MEDIUM if "link_click" in intent_codes else Severity.LOW,
                provenance=Provenance.HEURISTIC,
                explanation=(
                    "An unexpected prize or reward is the classic opening of an advance-fee or "
                    "phishing scam — the reward is the reason to click or pay."
                ),
                evidence=hit["evidence"], confidence=0.55,
            ))

        # ── Manipulation register (1.x) ──────────────────────
        self._manipulation(normalized, covered, result, ctx)

        # ── Prompt injection ─────────────────────────────────
        injections = nlp.detect_prompt_injection(normalized)
        if injections:
            result.artifacts["prompt_injection"] = injections
            result.signals.append(self._signal(
                code="prompt_injection_attempt", title="Instructions aimed at AI systems",
                family=Family.NLP, severity=Severity.INFO, provenance=Provenance.HEURISTIC,
                explanation=(
                    "The content contains text written to instruct an AI system. It was "
                    "treated as data and had no effect on this analysis; it is shown because "
                    "content that tries to steer automated reviewers is itself suspicious."
                ),
                evidence=injections[0], confidence=0.7,
            ))

    # ──────────────────────────────────────────────────────────

    # Sentences that ask the reader to *do* something are not factual claims:
    # "update your KYC at <link> and share the OTP" has no truth value to look
    # up, and sending it to web search costs seconds and returns noise.
    INSTRUCTION_INTENTS = {"credential_request", "otp_request", "payment_request", "link_click"}
    MIN_CLAIM_WORDS = 5

    def _claims(self, text: str, language: str, result: EngineResult) -> List[dict]:
        from truthshield.domain.verdict.claim_extractor import ClaimExtractor
        from truthshield.fraud.classify import URL_RE

        lang = language if language in nlp.SUPPORTED_LANGUAGES else "en"
        claims, excluded = [], 0
        for claim in ClaimExtractor().extract(text, lang)[:10]:
            intents = {i["intent"] for i in nlp.detect_intents(claim.text)}
            if URL_RE.search(claim.text) or intents & self.INSTRUCTION_INTENTS:
                excluded += 1
                continue
            # "It is 100% proven" has no subject to look up; searching it
            # matches any page containing the same words.
            if len(nlp.WORD_RE.findall(claim.text)) < self.MIN_CLAIM_WORDS:
                excluded += 1
                continue
            claims.append({
                "id": f"C{len(claims) + 1}",
                "text": claim.text,
                "entity": getattr(claim, "entity", None),
                "date": getattr(claim, "date", None),
                "location": getattr(claim, "location", None),
            })
        result.artifacts["claims_excluded"] = excluded
        if excluded:
            result.limitations.append(
                f"{excluded} sentence{'s were' if excluded != 1 else ' was'} not fact-checked: "
                "instructions, links and fragments without a subject have no truth value to "
                "verify against sources."
            )
        return claims

    def _fraud_detectors(self, ctx: InvestigationContext, text: str, result: EngineResult) -> set:
        import truthshield.fraud  # noqa: F401  (registers the detector plugins)
        from truthshield.fraud.registry import registered
        from truthshield.fraud.classify import classify

        classification = classify(text, hint=HINTS.get(ctx.type, ""))
        result.artifacts["input_kinds"] = classification.as_dict()["kinds"]

        covered = set()
        categories = []
        for detector in registered():
            if detector.name not in TEXT_DETECTORS or not detector.applies_to(text, classification):
                continue
            finding = detector.analyze(text, classification)
            if finding is None:
                continue

            result.predictions.append(ModelPredictionRecord(
                model_name=f"fraud.{detector.name}", model_version="1.0.0",
                model_kind=EngineKind.HEURISTIC, task="scam_category",
                input_sha256=ctx.input_sha256,
                prediction={
                    "category": finding.category.value,
                    "risk_score": finding.risk_score,
                    "indicators": [i.code for i in finding.indicators],
                },
                confidence=finding.confidence,
            ))
            if finding.category.value not in ("NONE", "UNKNOWN"):
                categories.append(finding.category.value)
            for limitation in finding.limitations:
                if limitation not in result.limitations:
                    result.limitations.append(limitation)

            for indicator in finding.indicators:
                if indicator.code in covered:
                    continue
                covered.add(indicator.code)
                result.signals.append(self._signal(
                    code=indicator.code, title=indicator.title,
                    family=Family.NLP, severity=indicator.severity,
                    provenance=Provenance.HEURISTIC,
                    explanation=indicator.explanation, evidence=indicator.evidence,
                    confidence=finding.confidence, weight=indicator.weight,
                ))

        result.artifacts["fraud_categories"] = categories
        return covered

    def _manipulation(self, text: str, covered: set, result: EngineResult, ctx) -> None:
        from truthshield.detectors.fraud import score_text

        score, fired = score_text(text)
        result.features["manipulation_score"] = score
        result.predictions.append(ModelPredictionRecord(
            model_name="deception-register", model_version="1.0.0",
            model_kind=EngineKind.HEURISTIC, task="manipulation_register",
            input_sha256=ctx.input_sha256,
            prediction={"score": score, "signals": [f["signal"] for f in fired]},
            confidence=None,
        ))

        for item in fired:
            # The scam detector's time-pressure indicator is the same observation.
            if item["signal"] == "urgency" and "urgency_pressure" in covered:
                continue
            strong = item["strength"] >= 1.0
            severity = Severity.MEDIUM if strong else Severity.LOW
            # Typographic emphasis alone ("See you then!") is ordinary writing;
            # only heavy shouting is worth a point.
            if item["signal"] == "shouting" and item["strength"] < 0.5:
                severity = Severity.INFO
            result.signals.append(self._signal(
                code=f"manipulation_{item['signal']}",
                title=item["label"],
                family=Family.NLP,
                severity=severity,
                provenance=Provenance.HEURISTIC,
                explanation=(
                    "A persuasion technique common in scams and misinformation. It is a "
                    "reason for caution rather than proof on its own."
                ),
                evidence=", ".join(item["matches"]) or None,
                confidence=0.5,
            ))
