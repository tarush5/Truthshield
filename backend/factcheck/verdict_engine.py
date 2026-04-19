"""
TruthShield — Verdict Engine (v3 — Gemini Flash + TF-IDF Fallback)

Priority order:
  1. Gemini 2.0 Flash with Google Search grounding (fastest, most accurate)
  2. Anthropic Claude (if Gemini unavailable)
  3. TF-IDF cosine similarity fallback (no API key needed)
"""

import json
import logging
import math
import re
from collections import Counter
from typing import List, Optional

from backend.config import (
    CLAUDE_MAX_TOKENS, CLAUDE_MODEL,
    GEMINI_MODEL, GEMINI_MAX_TOKENS,
    get_settings,
)
from backend.models.schemas import Claim, ClaimVerdict, Evidence, Verdict

logger = logging.getLogger(__name__)

VERDICT_SYSTEM_PROMPT = """You are TruthShield, an expert fact-checking AI. Analyze the claim against provided evidence and determine its veracity.

Respond with ONLY valid JSON, no other text:
{
    "verdict": "TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED",
    "reasoning": "Clear 2-3 sentence explanation",
    "confidence": 0.0 to 1.0
}

Rules:
- TRUE: Claim is substantially accurate
- FALSE: Claim is demonstrably wrong
- MISLEADING: Contains some truth but deceptive
- UNVERIFIED: Insufficient evidence
- Be conservative — default to UNVERIFIED if evidence is weak
- Consider source credibility"""


class VerdictEngine:
    """Evaluate claims using Gemini Flash (primary), Claude (secondary), or TF-IDF (fallback)."""

    def __init__(self):
        self._gemini_client = None
        self._claude_client = None
        self._gemini_checked = False
        self._claude_checked = False

    # ──────────────────────────────────────────────────────────
    # Client initialization
    # ──────────────────────────────────────────────────────────

    def _get_gemini_client(self):
        """Lazy-initialize Google Gemini client."""
        if not self._gemini_checked:
            self._gemini_checked = True
            try:
                from google import genai
                settings = get_settings()
                key = settings.GEMINI_API_KEY
                if key and key != "your_gemini_api_key" and len(key) > 10:
                    self._gemini_client = genai.Client(api_key=key)
                    logger.info("Gemini client initialized (model: %s)", GEMINI_MODEL)
                else:
                    logger.info("No Gemini API key; will try Claude or TF-IDF fallback.")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")
        return self._gemini_client

    def _get_claude_client(self):
        """Lazy-initialize Anthropic client."""
        if not self._claude_checked:
            self._claude_checked = True
            try:
                import anthropic
                settings = get_settings()
                key = settings.ANTHROPIC_API_KEY
                if key and key != "your_anthropic_api_key" and len(key) > 10:
                    self._claude_client = anthropic.Anthropic(api_key=key)
                    logger.info("Claude client initialized.")
            except Exception as e:
                logger.warning(f"Claude init failed: {e}")
        return self._claude_client

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    def evaluate_claim(
        self, claim: Claim, evidence: List[Evidence], is_crisis: bool = False,
    ) -> ClaimVerdict:
        """Evaluate a single claim — tries Gemini → Claude → TF-IDF."""
        # 1. Try Gemini Flash (fastest — ~1-2s with built-in Google Search)
        gemini = self._get_gemini_client()
        if gemini:
            result = self._gemini_evaluate(gemini, claim, evidence, is_crisis)
            if result:
                return result

        # 2. Try Claude
        claude = self._get_claude_client()
        if claude:
            result = self._claude_evaluate(claude, claim, evidence, is_crisis)
            if result:
                return result

        # 3. TF-IDF fallback
        return self._tfidf_evaluate(claim, evidence)

    def evaluate_claims(
        self, claims: List[Claim], evidence_map: dict, is_crisis: bool = False,
    ) -> List[ClaimVerdict]:
        """Evaluate multiple claims."""
        return [
            self.evaluate_claim(c, evidence_map.get(c.text, []), is_crisis)
            for c in claims
        ]

    # ──────────────────────────────────────────────────────────
    # Engine 1: Gemini Flash with Google Search grounding
    # ──────────────────────────────────────────────────────────

    def _gemini_evaluate(
        self, client, claim: Claim, evidence: List[Evidence], is_crisis: bool,
    ) -> Optional[ClaimVerdict]:
        """Use Gemini 2.0 Flash with Google Search grounding for fast, accurate verdicts."""
        try:
            from google.genai import types

            # Build evidence context
            ev_lines = []
            for i, ev in enumerate(evidence[:5]):
                ev_lines.append(f"[{i+1}] {ev.title} ({ev.url})\n    {ev.snippet[:200]}")
            evidence_block = "\n".join(ev_lines) if ev_lines else "No external evidence provided."

            prompt = f"""Fact-check this claim using the evidence below AND your own knowledge from Google Search.

CLAIM: {claim.text}
ENTITY: {claim.entity or 'N/A'}

EVIDENCE:
{evidence_block}

CRISIS FLAG: {'YES' if is_crisis else 'NO'}

Return ONLY valid JSON:
{{"verdict": "TRUE"|"FALSE"|"MISLEADING"|"UNVERIFIED", "reasoning": "2-3 sentences", "confidence": 0.0-1.0}}"""

            # Use Google Search grounding for real-time fact checking
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    max_output_tokens=GEMINI_MAX_TOKENS,
                    temperature=0.1,
                ),
            )

            text = response.text.strip()

            # Extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            # Try to find JSON object in the response
            json_match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group(0)

            result = json.loads(text)

            verdict_str = result.get("verdict", "UNVERIFIED").upper()
            try:
                verdict = Verdict(verdict_str)
            except ValueError:
                verdict = Verdict.UNVERIFIED

            logger.info(f"Gemini verdict: {verdict_str} (conf={result.get('confidence', 0.5)})")

            return ClaimVerdict(
                claim=claim,
                verdict=verdict,
                reasoning=result.get("reasoning", ""),
                confidence=float(result.get("confidence", 0.5)),
                evidence=evidence,
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Gemini JSON parse failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"Gemini evaluation failed: {e}")
            return None

    # ──────────────────────────────────────────────────────────
    # Engine 2: Anthropic Claude
    # ──────────────────────────────────────────────────────────

    def _claude_evaluate(
        self, client, claim: Claim, evidence: List[Evidence], is_crisis: bool,
    ) -> Optional[ClaimVerdict]:
        """Use Claude for verdict generation."""
        try:
            evidence_text = "\n".join(
                f"[Source {i+1}] ({ev.url})\n  Title: {ev.title}\n  Snippet: {ev.snippet}\n  Source Score: {ev.source_score}"
                for i, ev in enumerate(evidence)
            )

            user_message = f"""CLAIM: {claim.text}
ENTITY: {claim.entity or 'N/A'}
DATE: {claim.date or 'N/A'}
LOCATION: {claim.location or 'N/A'}

EVIDENCE:
{evidence_text if evidence_text else 'No external evidence found.'}

CRISIS FLAG: {'YES' if is_crisis else 'NO'}

Analyze this claim and provide your verdict as JSON."""

            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                system=VERDICT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            text = response.content[0].text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)
            verdict_str = result.get("verdict", "UNVERIFIED").upper()
            try:
                verdict = Verdict(verdict_str)
            except ValueError:
                verdict = Verdict.UNVERIFIED

            return ClaimVerdict(
                claim=claim,
                verdict=verdict,
                reasoning=result.get("reasoning", ""),
                confidence=float(result.get("confidence", 0.5)),
                evidence=evidence,
            )

        except Exception as e:
            logger.warning(f"Claude evaluation failed: {e}")
            return None

    # ──────────────────────────────────────────────────────────
    # Engine 3: TF-IDF Cosine Similarity Fallback
    # ──────────────────────────────────────────────────────────

    def _tfidf_evaluate(self, claim: Claim, evidence: List[Evidence]) -> ClaimVerdict:
        """Offline TF-IDF + polarity analysis when no AI model is available."""
        if not evidence:
            return ClaimVerdict(
                claim=claim,
                verdict=Verdict.UNVERIFIED,
                reasoning="No evidence found to verify or refute this claim.",
                confidence=0.2,
                evidence=[],
            )

        def get_words(text: str) -> List[str]:
            return [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)]

        claim_words = get_words(claim.text) or ["unknown"]

        # Build corpus
        corpus = [claim_words]
        for ev in evidence:
            corpus.append(get_words(ev.title + " " + ev.snippet))

        # IDF
        N = len(corpus)
        df = Counter()
        for doc in corpus:
            for word in set(doc):
                df[word] += 1
        idf = {w: math.log(N / (c + 0.1)) + 1.0 for w, c in df.items()}

        def tfidf_vec(words):
            if not words:
                return {}
            tf = Counter(words)
            return {w: (c / len(words)) * idf.get(w, 1.0) for w, c in tf.items()}

        def cosine(v1, v2):
            common = set(v1) & set(v2)
            num = sum(v1[x] * v2[x] for x in common)
            d1 = math.sqrt(sum(v ** 2 for v in v1.values()))
            d2 = math.sqrt(sum(v ** 2 for v in v2.values()))
            return num / (d1 * d2) if d1 * d2 else 0.0

        claim_vec = tfidf_vec(claim_words)

        false_kw = [
            " false", " fake", " hoax", " debunked", " misleading", " incorrect",
            " not true", " fabricated", " misinformation", " disinformation",
            " unproven", " rumor", " myth", " baseless", " conspiracy",
            " no evidence", " falsely claim", " without evidence",
        ]
        true_kw = [
            " true", " correct", " verified", " confirmed", " accurate",
            " supported by", " successfully", " achieved", " accomplished",
            " became the first", " announced that", " according to official",
            " landed", " launched", " completed", " established",
            " reported by", " data shows", " studies show", " research shows",
        ]

        signals = []
        max_sim = 0.0
        contra = 0.0
        support = 0.0
        relevant = 0

        for ev in evidence:
            ev_text = (" " + ev.title + " " + ev.snippet).lower()
            ev_words = get_words(ev_text)
            if not ev_words:
                continue

            sim = cosine(claim_vec, tfidf_vec(ev_words))
            if sim < 0.05:
                continue

            relevant += 1
            max_sim = max(max_sim, sim)
            impact = sim * ev.source_score

            has_false = any(k in ev_text for k in false_kw)
            has_true = any(k in ev_text for k in true_kw)

            if has_false:
                contra += impact * 2.0
                signals.append(f"Refuted by '{ev.title[:50]}…'")
            elif has_true:
                support += impact * 1.2
                signals.append(f"Supported by '{ev.title[:50]}…'")
            elif sim >= 0.15 and ev.source_score >= 0.60:
                support += impact * 0.3

        # Decision
        parts = []
        if relevant == 0:
            verdict, confidence = Verdict.UNVERIFIED, 0.25
            parts.append("Insufficient contextual overlap between claim and evidence.")
        elif max(contra, support) <= 0.02:
            verdict, confidence = Verdict.UNVERIFIED, min(0.50, 0.3 + max_sim * 0.2)
            parts.append("Evidence is relevant but lacks explicit stance signals.")
        elif contra > support:
            verdict = Verdict.FALSE
            confidence = min(0.95, 0.4 + contra * 0.6)
            parts.append("Strong refutation detected in relevant evidence.")
        elif support > contra:
            verdict = Verdict.TRUE
            confidence = min(0.90, 0.4 + support * 0.5)
            parts.append("Positive signals matched across credible sources.")
        else:
            verdict = Verdict.MISLEADING
            confidence = min(0.60, 0.3 + max_sim * 0.5)
            parts.append("Mixed or ambiguous signals in evidence.")

        if signals:
            parts.append("Signals: " + "; ".join(dict.fromkeys(signals).keys())[:3])

        return ClaimVerdict(
            claim=claim,
            verdict=verdict,
            reasoning=" ".join(parts),
            confidence=round(confidence, 3),
            evidence=evidence,
        )
