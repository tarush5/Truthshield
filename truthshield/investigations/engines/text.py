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

import re

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

TRANSACTIONAL_DOCUMENTS = {"invoice", "receipt", "bank_statement"}

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
        return ctx.type is not InvestigationType.URL and bool((ctx.text or ctx.content).strip())

    def _signal(self, **kwargs) -> Signal:
        return Signal(engine=self.name, engine_version=self.version, **kwargs)

    def _run(self, ctx: InvestigationContext, result: EngineResult) -> None:
        text = ctx.text or ctx.content

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
            # Only when the detection itself is sure and there is enough text:
            # a short English note misread as Dutch must not abstain.
            if language.confidence >= 0.9 and len(nlp.LETTER.findall(text)) >= 20:
                result.artifacts["coverage_gap"] = (
                    f"the text is in a language the checks do not cover ('{language.detected}')"
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
        # Invoices, receipts and statements are transactional: their lines are
        # amounts and parties, not public claims, and messaging-scam wording
        # ("GST ... amount due") is simply what they say. Their own consistency
        # checks live in the document engine.
        transactional = ctx.artifacts.get("document_type") in TRANSACTIONAL_DOCUMENTS
        if transactional:
            result.artifacts["claims"] = []
            result.limitations.append(
                "Transactional document: message-scam, persuasion and claim checks do not apply to "
                "invoice or statement lines; the document engine's consistency checks cover it."
            )
        else:
            result.artifacts["claims"] = self._claims(normalized, language.detected, result)

        # ── Intent ───────────────────────────────────────────
        intents = nlp.detect_intents(normalized)
        result.artifacts["intents"] = intents

        # ── Scam / phishing (1.x detectors) ──────────────────
        covered = set() if transactional else self._fraud_detectors(ctx, normalized, result)

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
        if not transactional:
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
    # Statements *about the recipient* ("you have won", "your account will be
    # blocked") are not public facts either: no source can confirm what one
    # stranger told another, so searching them only returns noise.
    MIN_CLAIM_WORDS = 5
    # Longer than this is a paragraph or a whole page, not one assertion.
    MAX_CLAIM_WORDS = 60

    # Explicit opinion markers only: "should", "best" and similar are too
    # common in checkable statements to exclude on.
    _OPINION = re.compile(r"^\s*(?:i|we)\s+(?:think|believe|feel|guess|reckon)\b|\bin\s+my\s+(?:opinion|view)\b"
                          r"|\bimo\b|\bpersonally\b", re.IGNORECASE)
    # "I read that ..." carries a third-party claim: check what was read.
    _REPORTED = re.compile(r"^\s*(?:i|we)\s+(?:read|heard|saw|was\s+told|were\s+told)\b", re.IGNORECASE)
    # A named thing after the first word: something public sources could cover.
    _NAMED = re.compile(r"(?<!^)\b(?:[A-Z][a-z]{2,}|[A-Z]{2,})\b")
    _CALENDAR = re.compile(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|"
                           r"April|May|June|July|August|September|October|November|December)$")
    # An instruction tells the reader to act. "The scheme requires a fee" states
    # a policy that sources can confirm or contradict; "Pay the fee at ..." does not.
    _IMPERATIVE = re.compile(
        r"^\s*(?:please\s+|kindly\s+)?(?:pay|send|transfer|deposit|click|tap|open|visit|call|share|enter|"
        r"update|verify|confirm|reply|scan|download|install|forward|submit|register|login|log\s+in|sign\s+in)\b"
        r"|\b(?:please|kindly)\s+\w+|\byou\s+(?:must|need\s+to|have\s+to|should)\s+\w+",
        re.IGNORECASE,
    )
    # Asking for a secret is never a statement of fact, whatever its grammar.
    SECRET_INTENTS = {"credential_request", "otp_request", "link_click"}
    _SECOND_PERSON = re.compile(r"\b(?:you|your|yours)\b", re.IGNORECASE)
    _PERSONAL_START = re.compile(r"^\s*(?:i|i'm|i've|my|me|we|we're|our|you|you're|your|aap\w*|mera|meri|"
                                 r"hum|hamara|hamari)\b", re.IGNORECASE)

    def _claim_type(self, claim, url_re) -> tuple:
        """(type, reason). Only FACTUAL sentences go to public fact-checking."""
        intents = {i["intent"] for i in nlp.detect_intents(claim.text)}
        if url_re.search(claim.text) or intents & self.SECRET_INTENTS or self._IMPERATIVE.search(claim.text):
            return "INSTRUCTION", "an instruction or a link, not a statement of fact"
        if self._OPINION.search(claim.text):
            return "OPINION", "marked as the writer's opinion"
        named = [m.group(0) for m in self._NAMED.finditer(claim.text.strip())
                 if not self._CALENDAR.match(m.group(0))]
        personal = self._PERSONAL_START.search(claim.text) or self._SECOND_PERSON.search(claim.text)
        if personal and not self._REPORTED.search(claim.text) and not named:
            return "PERSONAL", "about the writer or the reader, which public sources cannot confirm"
        words = len(nlp.WORD_RE.findall(claim.text))
        if words < self.MIN_CLAIM_WORDS or words > self.MAX_CLAIM_WORDS:
            # "It is 100% proven" has no subject to look up; searching it
            # matches any page containing the same words.
            return "UNVERIFIABLE", "too short to name what it is about, or too long to check as one claim"
        return "FACTUAL", None

    @staticmethod
    def _one_sentence_each(extracted) -> list:
        """
        Split multi-sentence claims. Without spaCy the extractor can return the
        whole input as one claim; typed as a unit, a factual sentence next to a
        link ("The scheme requires a fee. Pay at http://...") was skipped as an
        instruction and never checked.
        """
        from types import SimpleNamespace

        out = []
        for claim in extracted:
            parts = nlp.sentences(claim.text)
            if len(parts) <= 1:
                out.append(claim)
                continue
            out.extend(SimpleNamespace(text=part, entity=None, date=getattr(claim, "date", None),
                                       location=getattr(claim, "location", None)) for part in parts)
        return out

    def _claims(self, text: str, language: str, result: EngineResult) -> List[dict]:
        from truthshield.domain.verdict.claim_extractor import ClaimExtractor
        from truthshield.fraud.classify import URL_RE

        lang = language if language in nlp.SUPPORTED_LANGUAGES else "en"
        claims, excluded, screening = [], 0, []
        for claim in self._one_sentence_each(ClaimExtractor().extract(text, lang))[:10]:
            kind, reason = self._claim_type(claim, URL_RE)
            screening.append({"text": claim.text[:300], "type": kind, "fact_checked": kind == "FACTUAL",
                              "reason": reason})
            if kind != "FACTUAL":
                excluded += 1
                continue
            claims.append({
                "id": f"C{len(claims) + 1}",
                "text": claim.text,
                "type": "FACTUAL",
                "entity": getattr(claim, "entity", None),
                "date": getattr(claim, "date", None),
                "location": getattr(claim, "location", None),
            })
        result.artifacts["claims_excluded"] = excluded
        result.artifacts["claim_screening"] = screening
        if excluded:
            result.limitations.append(
                f"{excluded} sentence{'s were' if excluded != 1 else ' was'} not fact-checked: "
                "instructions, links, opinions, statements about the writer or the reader, and "
                "fragments without a subject cannot be verified against public sources."
            )
        return claims

    def _fraud_detectors(self, ctx: InvestigationContext, text: str, result: EngineResult) -> set:
        import truthshield.fraud  # noqa: F401  (registers the detector plugins)
        from truthshield.fraud.registry import registered
        from truthshield.fraud.classify import InputKind, classify

        classification = classify(text, hint=HINTS.get(ctx.type, ""))
        result.artifacts["input_kinds"] = classification.as_dict()["kinds"]
        if InputKind.EMAIL_MESSAGE in classification.kinds:
            # Reported whether or not anything failed: a pass, or the absence
            # of headers, is what the reader needs to weigh the rest.
            from truthshield.fraud import email_auth
            from truthshield.fraud.detectors.email import address_of, domain_of, parse_headers

            auth = email_auth.parse(text)
            from_domain = domain_of(address_of(parse_headers(text).get("from", "")))
            result.artifacts["email_authentication"] = (
                auth.as_dict(from_domain) if auth else {"checked": False}
            )

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
            # In an uploaded file, capitals are layout (headings), not emphasis.
            if item["signal"] == "shouting" and (item["strength"] < 0.5 or ctx.type.is_file):
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
