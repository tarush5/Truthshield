"""
TruthShield — Verdict Engine (v4 — Production Grade)

Priority order:
  1. Gemini 2.5 Flash with Google Search grounding (fastest, most accurate)
  2. Anthropic Claude (if Gemini unavailable)
  3. Enhanced TF-IDF + NLP fallback (no API key needed, much smarter than v3)

v4 improvements over v3:
  - Retry logic with exponential backoff for Gemini rate limits
  - N-gram matching (bigrams/trigrams) in TF-IDF
  - Negation-aware polarity detection
  - Source-weighted confidence calibration
  - Structured reasoning citing specific sources
"""

import json
import logging
import math
import re
import time
from collections import Counter
from typing import List, Optional

from backend.config import (
    CLAUDE_MAX_TOKENS, CLAUDE_MODEL,
    GEMINI_MODEL, GEMINI_MAX_TOKENS, GEMINI_FALLBACK_MODELS,
    get_settings,
)
from backend.models.schemas import Claim, ClaimVerdict, Evidence, Verdict

logger = logging.getLogger(__name__)

VERDICT_SYSTEM_PROMPT = """You are TruthShield, an expert fact-checking AI. Analyze the claim against provided evidence and determine its veracity.

Respond with ONLY valid JSON, no other text:
{
    "verdict": "TRUE" | "FALSE" | "MISLEADING" | "UNVERIFIED",
    "reasoning": "Clear 2-3 sentence explanation citing specific evidence sources",
    "confidence": 0.0 to 1.0,
    "stances": ["SUPPORTS" | "REFUTES" | "NEUTRAL" | "INSUFFICIENT" for each evidence item in order]
}

Rules:
- TRUE: Claim is substantially accurate and directly supported by the evidence.
- FALSE: Claim is demonstrably wrong or contradicted by the evidence.
- MISLEADING: Contains some truth but is deceptive or taken out of context.
- UNVERIFIED: Insufficient evidence to confirm or refute the claim.
- Be conservative — default to UNVERIFIED if evidence is weak or unrelated.
- Consider source credibility.
- Cite which sources support or refute the claim in your reasoning."""


class VerdictEngine:
    """Evaluate claims using Gemini Flash (primary), Claude (secondary), or Enhanced TF-IDF (fallback)."""

    def __init__(self):
        self._gemini_client = None
        self._claude_client = None
        self._gemini_checked = False
        self._claude_checked = False

    # ──────────────────────────────────────────────────────────
    # Claim alignment helpers (used by bypass gate + TF-IDF)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _get_content_words(text: str) -> set:
        """Tokenize and return content words (stopwords removed) for semantic comparison."""
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9\u0900-\u097F\u0B80-\u0BFF]{3,}\b", text)]
        stopwords = {
            "the", "and", "for", "that", "this", "with", "from", "was", "were", "been",
            "has", "have", "had", "are", "its", "their", "his", "her", "who", "whom",
            "which", "they", "she", "him", "them", "your", "our", "about", "there",
            "not", "but", "what", "when", "where", "how", "why", "will", "would", "shall",
            "should", "can", "could", "may", "might", "must", "other", "some", "such",
            "into", "than", "then", "these", "those", "upon", "did", "does", "done",
            "fact", "check", "claim", "reviewed", "rating", "false", "true",
            "video", "photo", "image", "photos", "videos", "images",
        }
        return set(w for w in words if w not in stopwords)

    @staticmethod
    def _negates_claim(claim_text: str, ev_text: str) -> bool:
        """True when the evidence negates the claim's own assertion.

        Scoped deliberately: a negation word anywhere in a document says
        nothing about the claim, but a negation immediately before one of the
        claim's distinctive terms ("...is NOT made of cheese") is a direct
        contradiction of it.
        """
        negations = {
            "not", "no", "never", "isnt", "arent", "wasnt", "werent", "dont",
            "doesnt", "didnt", "cannot", "cant", "wont", "nor", "false", "debunked",
        }
        claim_words = VerdictEngine._get_content_words(claim_text)
        if not claim_words:
            return False

        # Scalar-additive qualifiers. "Lung cancer is not ONLY about smoking"
        # asserts there are further causes; it does not deny that smoking is
        # one of them. Reading it as refutation flipped "smoking tobacco causes
        # lung cancer" to LIKELY FALSE on the benchmark — an article agreeing
        # with the claim was being counted as evidence against it.
        additive = {"only", "just", "merely", "solely", "alone", "exclusively", "purely"}

        tokens = [t.strip("'") for t in re.findall(r"[a-zA-Z']+", ev_text.lower())]
        for i, tok in enumerate(tokens):
            if tok not in claim_words:
                continue
            for j in range(max(0, i - 4), i):
                if tokens[j].replace("'", "") not in negations:
                    continue
                # Look just past the negation: "not only", "not just", "not the
                # only", "not always" hedge or add rather than contradict.
                tail = tokens[j + 1:j + 3]
                if any(t in additive for t in tail) or tail[:1] == ["always"]:
                    continue
                return True
        return False

    @staticmethod
    def _extract_reviewed_claim(ev_text: str) -> Optional[str]:
        """Extract the claim being reviewed from a fact-check snippet."""
        patterns = [
            r"claim reviewed:\s*(.+?)(?:\s*[\u2014\u2013\-]+\s*rating:)",
            r"claim reviewed:\s*([^.]{10,120})",
            r"fact check:\s*([^.]{10,120}?)(?:\s*claim|\s*$)",
        ]
        for pat in patterns:
            m = re.search(pat, ev_text, re.IGNORECASE)
            if m:
                result = m.group(1).strip()
                result = re.sub(r'\s*[\u2014\u2013\-]+\s*rating:.*$', '', result, flags=re.IGNORECASE)
                if len(result) > 10:
                    return result
        return None

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
        """Evaluate a single claim — tries Gemini → Claude → Enhanced TF-IDF."""
        # Add RAG enhancement
        if evidence:
            try:
                from backend.factcheck.rag_store import RAGStore
                rag = RAGStore()
                docs = [
                    {
                        "text": f"{ev.title} {ev.snippet}",
                        "title": ev.title,
                        "url": ev.url,
                        "source_score": ev.source_score,
                        "raw_ev": ev
                    }
                    for ev in evidence
                ]
                rag.add_documents(docs)
                # Keep most of the retrieved set. Cutting to 5 threw away the
                # bulk of the stance signal, so a single highly-similar but
                # contrarian article could outvote the rest and flip a verdict.
                retrieved_docs = rag.query(claim.text, top_k=10)
                evidence = [doc["raw_ev"] for doc in retrieved_docs]
                logger.info(f"RAG Store filtered evidence for claim: {len(evidence)} items retrieved.")
            except Exception as e:
                logger.warning(f"RAG retrieval skipped or failed: {e}")

        # Check if there is an exact/matching fact-check review in the evidence to bypass LLM
        # CRITICAL: We must verify the fact-check is about the SAME claim as the user's,
        # not just a topically-related article. E.g., a fact-check about a "viral video
        # of Chandrayaan-3" is NOT the same as a claim about "India landing on the Moon".
        if evidence:
            for ev in evidence:
                if ev.source_score >= 0.90:
                    text_to_check = (ev.title + " " + ev.snippet).lower()
                    rating_match = re.search(
                        r"(?:rating|verdict|claim reviewed.*?rating):\s*(true|false|misleading|pants on fire|mostly false|mostly true|half true|unverified|insufficient)",
                        text_to_check, re.IGNORECASE
                    )
                    if rating_match:
                        rating_str = rating_match.group(1).lower()

                        # ── Claim alignment gate ──
                        # Extract what claim the fact-check is actually reviewing
                        reviewed_claim = self._extract_reviewed_claim(text_to_check)
                        if reviewed_claim:
                            # Check content-word overlap between user claim and reviewed claim
                            user_words = self._get_content_words(claim.text)
                            reviewed_words = self._get_content_words(reviewed_claim)
                            if user_words and reviewed_words:
                                overlap = user_words & reviewed_words
                                overlap_ratio = len(overlap) / max(len(user_words), 1)
                                if overlap_ratio < 0.40:
                                    logger.info(
                                        f"Fact-check bypass SKIPPED: reviewed claim '{reviewed_claim[:80]}' "
                                        f"does not match user claim (overlap={overlap_ratio:.2f}). "
                                        f"Proceeding to LLM/TF-IDF evaluation."
                                    )
                                    continue  # Skip this evidence — it's about a different claim
                        else:
                            # No explicit "Claim Reviewed" found — do a simpler title check
                            # The title often starts with the fact-check org, then the claim
                            ev_title_words = self._get_content_words(ev.title)
                            user_words = self._get_content_words(claim.text)
                            if user_words and ev_title_words:
                                overlap = user_words & ev_title_words
                                overlap_ratio = len(overlap) / max(len(user_words), 1)
                                if overlap_ratio < 0.35:
                                    logger.info(
                                        f"Fact-check bypass SKIPPED: title '{ev.title[:80]}' "
                                        f"has low overlap with user claim ({overlap_ratio:.2f}). "
                                        f"Proceeding to LLM/TF-IDF evaluation."
                                    )
                                    continue

                        # Map rating to standard Verdict
                        if rating_str in ("true", "mostly true"):
                            mapped_verdict = Verdict.TRUE
                            ev.stance = "SUPPORTS"
                        elif rating_str in ("false", "pants on fire", "mostly false"):
                            mapped_verdict = Verdict.FALSE
                            ev.stance = "REFUTES"
                        elif rating_str in ("half true", "misleading"):
                            mapped_verdict = Verdict.MISLEADING
                            ev.stance = "REFUTES"
                        else:
                            mapped_verdict = Verdict.UNVERIFIED
                            ev.stance = "INSUFFICIENT"
                        
                        logger.info(f"Instant fact-check match found in evidence: {ev.title} (rating: {rating_str}) - Bypassing LLM")
                        return ClaimVerdict(
                            claim=claim,
                            verdict=mapped_verdict,
                            reasoning=f"Fact Check Match Found: The claim was directly reviewed by {ev.title.split(':')[0].replace(' RSS', '').replace(' Fact Check', '')} and rated as {rating_str.upper()}.",
                            confidence=0.98,
                            evidence=evidence,
                        )

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

        # 3. Enhanced TF-IDF fallback
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
    # Engine 1: Gemini Flash with Google Search grounding + retry
    # ──────────────────────────────────────────────────────────

    def _gemini_evaluate(
        self, client, claim: Claim, evidence: List[Evidence], is_crisis: bool,
    ) -> Optional[ClaimVerdict]:
        """Use Gemini with Google Search grounding for real-time web verification.
        
        KEY IMPROVEMENT: Enables the google_search tool so Gemini can verify claims
        against live web data, not just pre-retrieved snippets. This dramatically
        improves accuracy for current events and factual claims.
        """
        # Walk the model list once. Only the first model gets a single short
        # retry on rate-limit — a longer backoff here stalls the whole request,
        # and the next model is usually available immediately.
        models_to_try = GEMINI_FALLBACK_MODELS

        for model_idx, model_name in enumerate(models_to_try):
            max_attempts = 2 if model_idx == 0 else 1
            for attempt in range(max_attempts):
                try:
                    from google.genai import types

                    # Build evidence context — include more detail (500 chars per item)
                    ev_lines = []
                    for i, ev in enumerate(evidence[:8]):
                        stance_hint = f" [Stance: {ev.stance}]" if getattr(ev, 'stance', None) else ""
                        ev_lines.append(
                            f"[{i+1}] {ev.title} (Score: {ev.source_score:.2f}){stance_hint}\n"
                            f"    URL: {ev.url}\n"
                            f"    Content: {ev.snippet[:500]}"
                        )
                    evidence_block = "\n\n".join(ev_lines) if ev_lines else "No external evidence provided."

                    prompt = f"""You are TruthShield, an expert fact-checking AI. Your job is to determine whether the following claim is TRUE or FALSE based on evidence.

CLAIM TO VERIFY: "{claim.text}"
ENTITY: {claim.entity or 'N/A'}

RETRIEVED EVIDENCE:
{evidence_block}

INSTRUCTIONS:
1. FIRST, use your own knowledge and the Google Search tool to independently verify the claim.
2. THEN, cross-reference with the retrieved evidence above.
3. Check specific facts: dates, numbers, names, locations, event outcomes.
4. A claim is TRUE if the core assertion is factually accurate.
5. A claim is FALSE if the core assertion is demonstrably wrong.
6. A claim is MISLEADING if it contains some truth but is deceptive or misrepresents context.
7. Only use UNVERIFIED if you genuinely cannot find any information about this claim.
8. For each evidence item, determine if it SUPPORTS, REFUTES, or is NEUTRAL/INSUFFICIENT.

IMPORTANT:
- Do NOT default to UNVERIFIED. If you can find ANY information about this topic, make a determination.
- If the claim is about a well-known fact or recent event, verify it and give TRUE or FALSE.
- Be precise about numbers, dates, and specific details.

Return ONLY valid JSON:
{{"verdict": "TRUE"|"FALSE"|"MISLEADING"|"UNVERIFIED", "reasoning": "2-3 sentences citing specific evidence and facts", "confidence": 0.0-1.0, "stances": ["SUPPORTS"|"REFUTES"|"NEUTRAL"|"INSUFFICIENT" for each evidence item]}}"""

                    # Configure with Google Search grounding tool for real-time verification
                    try:
                        google_search_tool = types.Tool(
                            google_search=types.GoogleSearch()
                        )
                        config = types.GenerateContentConfig(
                            max_output_tokens=GEMINI_MAX_TOKENS,
                            temperature=0.05,  # Very low temperature for factual accuracy
                            tools=[google_search_tool],
                        )
                    except Exception:
                        # Fallback: no grounding tool (older SDK versions)
                        config = types.GenerateContentConfig(
                            max_output_tokens=GEMINI_MAX_TOKENS,
                            temperature=0.05,
                        )

                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )

                    text = response.text.strip()

                    # Check if Google Search grounding was used
                    grounding_used = False
                    try:
                        if hasattr(response, 'candidates') and response.candidates:
                            candidate = response.candidates[0]
                            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                                grounding_used = True
                                logger.info("Gemini used Google Search grounding for verification")
                    except Exception:
                        pass

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

                    confidence = float(result.get("confidence", 0.5))
                    
                    # Boost confidence when Google Search grounding was used
                    if grounding_used and confidence < 0.95:
                        confidence = min(0.95, confidence + 0.10)

                    logger.info(
                        f"Gemini verdict: {verdict_str} (conf={confidence:.2f}, "
                        f"grounded={'YES' if grounding_used else 'NO'}) "
                        f"[model={model_name}, attempt {attempt+1}]"
                    )

                    # Map stances
                    stances = result.get("stances", [])
                    for idx, ev in enumerate(evidence[:8]):
                        if idx < len(stances):
                            ev.stance = stances[idx].upper()

                    return ClaimVerdict(
                        claim=claim,
                        verdict=verdict,
                        reasoning=result.get("reasoning", ""),
                        confidence=confidence,
                        evidence=evidence,
                    )

                except json.JSONDecodeError as e:
                    logger.warning(f"Gemini JSON parse failed: {e}")
                    return None
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "503" in error_str or "UNAVAILABLE" in error_str:
                        if attempt + 1 < max_attempts:
                            logger.warning(f"Gemini {model_name} rate-limited, retrying once in 1s...")
                            time.sleep(1.0)
                            continue
                        logger.warning(f"Gemini {model_name} unavailable, trying next model...")
                        break
                    else:
                        logger.warning(f"Gemini evaluation failed: {e}")
                        return None

        logger.warning("All Gemini models unavailable, falling back to other engines.")
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

            # Map stances
            stances = result.get("stances", [])
            for idx, ev in enumerate(evidence):
                if idx < len(stances):
                    ev.stance = stances[idx].upper()

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
    # Engine 3: Enhanced TF-IDF + NLP Fallback (Production Grade)
    # ──────────────────────────────────────────────────────────

    def _tfidf_evaluate(self, claim: Claim, evidence: List[Evidence]) -> ClaimVerdict:
        """Enhanced offline TF-IDF + context-aware polarity analysis when no AI model is available.
        
        Key improvement over v3: distinguishes between fact-check articles that debunk
        the user's claim vs. articles that debunk a DIFFERENT/OPPOSITE claim.
        
        Example: User claims "Earth orbits the Sun". Evidence says "Fact check: Photos do not
        prove sun is close — FALSE". The article is debunking a DIFFERENT claim (that photos prove
        the sun is close), which actually SUPPORTS the user's claim.
        """
        if not evidence:
            return ClaimVerdict(
                claim=claim,
                verdict=Verdict.UNVERIFIED,
                reasoning="No evidence found from any source to verify or refute this claim.",
                confidence=0.2,
                evidence=[],
            )

        def get_words(text: str) -> List[str]:
            return [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)]

        def get_ngrams(words: List[str], n: int) -> List[str]:
            return [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]

        def get_all_terms(text: str) -> List[str]:
            words = get_words(text)
            bigrams = get_ngrams(words, 2)
            trigrams = get_ngrams(words, 3)
            return words + bigrams + trigrams

        def _get_content_words(text: str) -> set:
            return VerdictEngine._get_content_words(text)

        claim_terms = get_all_terms(claim.text) or ["unknown"]
        claim_words_set = set(get_words(claim.text))
        claim_content_words = _get_content_words(claim.text)
        corpus = [claim_terms]
        for ev in evidence:
            corpus.append(get_all_terms(ev.title + " " + ev.snippet))

        # IDF
        N = len(corpus)
        df = Counter()
        for doc in corpus:
            for term in set(doc):
                df[term] += 1
        idf = {w: math.log(N / (c + 0.1)) + 1.0 for w, c in df.items()}

        def tfidf_vec(terms):
            if not terms:
                return {}
            tf = Counter(terms)
            return {w: (c / len(terms)) * idf.get(w, 1.0) for w, c in tf.items()}

        def cosine(v1, v2):
            common = set(v1) & set(v2)
            num = sum(v1[x] * v2[x] for x in common)
            d1 = math.sqrt(sum(v ** 2 for v in v1.values()))
            d2 = math.sqrt(sum(v ** 2 for v in v2.values()))
            return num / (d1 * d2) if d1 * d2 else 0.0

        claim_vec = tfidf_vec(claim_terms)

        # ── Polarity keywords ──
        false_keywords = [
            "false", "fake", "hoax", "debunked", "misleading", "incorrect",
            "not true", "fabricated", "misinformation", "disinformation",
            "unproven", "rumor", "myth", "baseless", "conspiracy",
            "no evidence", "falsely claim", "without evidence", "pants on fire",
            "rated false", "mostly false", "no basis", "unfounded", "discredited",
            "contradicted", "refuted", "denied", "no proof", "inaccurate",
            "lacks evidence", "unsupported", "wrong", "untrue", "fictitious",
            "does not cure", "cannot prevent", "no scientific evidence",
        ]
        true_keywords = [
            "true", "correct", "verified", "confirmed", "accurate",
            "supported by", "successfully", "achieved", "accomplished",
            "became the first", "announced that", "according to official",
            "landed", "launched", "completed", "established",
            "reported by", "data shows", "studies show", "research shows",
            "mostly true", "rated true", "fact check confirms",
            "evidence supports", "scientists confirm", "officially announced",
            "historic achievement", "world record", "proven", "validated",
        ]

        negation_words = {"not", "no", "never", "neither", "nor", "none", "cannot",
                          "doesn't", "didn't", "wasn't", "weren't", "isn't", "aren't",
                          "don't", "won't", "wouldn't", "couldn't", "shouldn't", "hasn't",
                          "haven't", "hadn't"}

        # ── Context-aware helper: detect if a fact-check is about the SAME
        #    claim as the user's or about an OPPOSITE/DIFFERENT claim ──
        def _extract_reviewed_claim(ev_text: str) -> Optional[str]:
            return VerdictEngine._extract_reviewed_claim(ev_text)

        def _claims_are_aligned(user_claim: str, reviewed_claim: str) -> bool:
            """Determine if the fact-check reviewed claim is semantically aligned
            with the user's claim (same direction) or opposite.
            
            E.g., User: "Earth orbits the Sun" vs Reviewed: "Photos prove sun is close
            and orbiting Earth" → these are OPPOSITE claims (subject-object swap).
            """
            uc_content = _get_content_words(user_claim)
            rc_content = _get_content_words(reviewed_claim)
            
            # Stem/normalize by taking first 4 chars of each content word to handle singular/plural and verb inflections
            uc_stems = {w[:4] for w in uc_content}
            rc_stems = {w[:4] for w in rc_content}
            
            overlap = uc_stems & rc_stems
            if not overlap:
                return False
            
            # ── Check 1: Explicit negation/contradiction indicators ──
            uc_lower = " " + user_claim.lower() + " "
            rc_lower = " " + reviewed_claim.lower() + " "
            contradiction_indicators = [
                "do not prove", "does not prove", "not prove", "disprove",
                "doesn't", "don't", "cannot", "won't", "isn't", "aren't",
                "no evidence", "debunked", "myth", "hoax", "fake",
            ]
            
            rc_has_negation = any(ind in rc_lower for ind in contradiction_indicators)
            uc_has_negation = any(ind in uc_lower for ind in contradiction_indicators)
            
            if rc_has_negation != uc_has_negation:
                return False
            
            # ── Check 2: "prove/proves/proving X" pattern — the claim being 
            # "proven" is typically misinformation that was debunked ──
            prove_match = re.search(r"(?:prove|proves|proving|show|shows)\s+(?:that\s+)?(.{10,100})", rc_lower)
            if prove_match:
                proven_assertion = prove_match.group(1)
                proven_content = _get_content_words(proven_assertion)
                proven_stems = {w[:4] for w in proven_content}
                if proven_stems & uc_stems:
                    proven_sim = len(proven_stems & uc_stems) / max(len(uc_stems), 1)
                    if proven_sim < 0.5:
                        return False
            
            # ── Check 3: Subject-object reversal detection ──
            # "Earth orbits the Sun" vs "Sun orbits the Earth" — same verb, swapped entities
            uc_verb_patterns = re.findall(r"(\w+)\s+(\w+)\s+(?:the\s+)?(\w+)", uc_lower)
            rc_verb_patterns = re.findall(r"(\w+)\s+(\w+)\s+(?:the\s+)?(\w+)", rc_lower)
            for uc_subj, uc_verb, uc_obj in uc_verb_patterns:
                for rc_subj, rc_verb, rc_obj in rc_verb_patterns:
                    # Same verb, swapped subject/object
                    if uc_verb == rc_verb and uc_subj == rc_obj and uc_obj == rc_subj:
                        return False
            
            # ── Check 4: Low word overlap → different claims ──
            overlap_ratio = len(overlap) / max(len(uc_stems), len(rc_stems), 1)
            if overlap_ratio < 0.25:
                return False
            
            return True

        signals = []
        max_sim = 0.0
        contra = 0.0
        support = 0.0
        relevant = 0
        source_names = {"support": [], "refute": []}

        user_claim_has_negation = any(w in get_words(claim.text.lower()) for w in negation_words)

        for ev in evidence:
            ev_text_raw = ev.title + " " + ev.snippet
            ev_text = " " + ev_text_raw.lower() + " "
            ev_terms = get_all_terms(ev_text_raw)
            if not ev_terms:
                continue

            sim = cosine(claim_vec, tfidf_vec(ev_terms))
            
            # Secondary relevance: raw keyword overlap ratio
            ev_words_set = set(get_words(ev_text_raw))
            keyword_overlap = len(claim_words_set & ev_words_set) / max(len(claim_words_set), 1)
            
            # Consider relevant if cosine >= 0.02 OR keyword overlap >= 30%
            if sim < 0.02 and keyword_overlap < 0.30:
                continue

            # Check content word overlap to filter out general background/topic-only noise
            ev_content_words = _get_content_words(ev_text_raw)
            overlap_words = claim_content_words & ev_content_words
            overlap_ratio = len(overlap_words) / max(len(claim_content_words), 1)
            
            # If claim has multiple content words, require at least 2 content words overlap and ratio >= 0.30
            # If it is a very short claim (<= 2 content words), require at least 1 content word overlap
            if len(claim_content_words) >= 3:
                if len(overlap_words) < 2 or overlap_ratio < 0.30:
                    logger.debug(f"Skipping background evidence '{ev.title[:30]}' due to low content word overlap ({len(overlap_words)} words, {overlap_ratio:.2f} ratio)")
                    continue
            else:
                if len(overlap_words) < 1:
                    logger.debug(f"Skipping background evidence '{ev.title[:30]}' due to 0 content word overlap")
                    continue

            # Quiz and homework pages restate a claim as an exercise rather
            # than asserting it. Their "true or false" / "select the correct"
            # phrasing otherwise reads as a verdict and flips the stance.
            if re.search(
                r"\b(true or false|select the correct|which of the following|"
                r"choose the (correct|right)|answer[: ]|solved|homework|quiz)\b",
                ev_text, re.IGNORECASE,
            ):
                ev.stance = "INSUFFICIENT"
                continue

            relevant += 1
            max_sim = max(max_sim, sim)
            impact = sim * ev.source_score

            # ── Step 1: Determine raw polarity of the evidence ──
            raw_polarity = None  # None = neutral, "false" = debunking, "true" = confirming

            # Check for fact-check ratings (highest signal)
            rating_match = re.search(
                r"rating:\s*(true|false|misleading|pants on fire|mostly false|mostly true|half true|unproven)",
                ev_text, re.IGNORECASE
            )

            if rating_match:
                rating = rating_match.group(1).lower()
                if rating in ("false", "pants on fire", "mostly false"):
                    raw_polarity = "false"
                elif rating in ("true", "mostly true"):
                    raw_polarity = "true"
                elif rating in ("half true", "misleading"):
                    raw_polarity = "misleading"
            else:
                # Keyword-based polarity with negation awareness
                has_false = False
                has_true = False

                for kw in false_keywords:
                    if kw in ev_text:
                        kw_pos = ev_text.find(kw)
                        preceding = ev_text[max(0, kw_pos - 20):kw_pos].split()
                        if preceding and preceding[-1] in negation_words:
                            has_true = True
                        else:
                            has_false = True

                for kw in true_keywords:
                    if kw in ev_text:
                        kw_pos = ev_text.find(kw)
                        preceding = ev_text[max(0, kw_pos - 20):kw_pos].split()
                        if preceding and preceding[-1] in negation_words:
                            has_false = True
                        else:
                            has_true = True

                if has_false and not has_true:
                    raw_polarity = "false"
                elif has_true and not has_false:
                    raw_polarity = "true"
                elif has_false and has_true:
                    raw_polarity = "mixed"

            # ── Step 2: Determine stance from measured polarity ──
            # Polarity already applies negation-aware keyword matching. Any
            # negation must be tied to the claim's own assertion — a blanket
            # "contains a negation word" test mislabels ordinary prose as
            # refutation (a physics page stating water boils at 100C is not
            # refuting the claim that it does).
            negates = self._negates_claim(claim.text, ev_text_raw)
            is_refuting_positive = raw_polarity in ("false", "misleading") or negates
            
            source_label = ev.title[:60]
            
            if user_claim_has_negation:
                if is_refuting_positive:
                    ev.stance = "SUPPORTS"
                    support += impact * 1.5
                    signals.append(f"Supported by '{source_label}'")
                    source_names["support"].append(source_label)
                else:
                    ev.stance = "REFUTES"
                    contra += impact * 2.5
                    signals.append(f"Refuted by '{source_label}'")
                    source_names["refute"].append(source_label)
            else:
                if is_refuting_positive:
                    ev.stance = "REFUTES"
                    contra += impact * 2.5
                    signals.append(f"Refuted by '{source_label}'")
                    source_names["refute"].append(source_label)
                elif raw_polarity == "true" or (sim >= 0.15 and ev.source_score >= 0.50):
                    ev.stance = "SUPPORTS"
                    support += impact * 1.5
                    signals.append(f"Supported by '{source_label}'")
                    source_names["support"].append(source_label)
                elif raw_polarity == "mixed":
                    ev.stance = "NEUTRAL"
                    contra += impact * 0.8
                    support += impact * 0.5
                    signals.append(f"Mixed signals from '{source_label}'")
                elif sim >= 0.05 and ev.source_score >= 0.60 and overlap_ratio >= 0.50:
                    # Implicit support: a credible source discussing the claim
                    # factually without debunking language. This requires strong
                    # content-word overlap — sharing only a topic is not support.
                    # ("Moon" appearing on a NASA page does not corroborate
                    # "the Moon is made of cheese".)
                    ev_domain = getattr(ev, 'url', '') or ''
                    is_knowledge_source = any(d in ev_domain for d in [
                        'wikipedia.org', '.edu', '.gov', 'britannica.com', 'nasa.gov',
                        'who.int', 'un.org', 'nature.com', 'sciencedirect.com',
                    ])
                    if is_knowledge_source or (sim >= 0.10 and ev.source_score >= 0.70):
                        ev.stance = "SUPPORTS"
                        support += impact * 1.0
                        signals.append(f"Implicitly supported by '{source_label}'")
                        source_names["support"].append(source_label)
                    else:
                        ev.stance = "NEUTRAL"
                        support += impact * 0.3
                else:
                    ev.stance = "INSUFFICIENT"

        # ── Decision ──
        parts = []
        if relevant == 0:
            verdict, confidence = Verdict.UNVERIFIED, 0.25
            parts.append("No relevant evidence found that addresses this specific claim.")
        elif max(contra, support) <= 0.02:
            verdict, confidence = Verdict.UNVERIFIED, min(0.50, 0.3 + max_sim * 0.2)
            parts.append("Evidence overlaps with the claim topic but lacks explicit stance signals to confirm or deny it.")
        elif contra > support * 1.2:
            verdict = Verdict.FALSE
            ratio = contra / max(support, 0.01)
            confidence = min(0.95, 0.45 + min(0.50, contra * 0.4))
            parts.append(f"Multiple credible sources refute this claim (refutation strength: {ratio:.1f}x).")
        elif support > contra * 1.2:
            verdict = Verdict.TRUE
            ratio = support / max(contra, 0.01)
            confidence = min(0.92, 0.45 + min(0.47, support * 0.35))
            parts.append(f"Credible sources corroborate this claim (support strength: {ratio:.1f}x).")
        elif abs(contra - support) < max(contra, support) * 0.3:
            verdict = Verdict.MISLEADING
            confidence = min(0.65, 0.35 + max_sim * 0.3)
            parts.append("Evidence contains both supporting and refuting signals, suggesting the claim may be misleading or out of context.")
        else:
            verdict = Verdict.UNVERIFIED
            confidence = min(0.50, 0.3 + max_sim * 0.2)
            parts.append("Ambiguous evidence signals. Cannot determine veracity with confidence.")

        # Add source citations to reasoning
        if source_names["refute"]:
            refute_list = "; ".join(source_names["refute"][:3])
            parts.append(f"Refuting sources: {refute_list}.")
        if source_names["support"]:
            support_list = "; ".join(source_names["support"][:3])
            parts.append(f"Supporting sources: {support_list}.")

        parts.append(f"Analysis based on {relevant} relevant evidence items from {len(evidence)} retrieved.")

        return ClaimVerdict(
            claim=claim,
            verdict=verdict,
            reasoning=" ".join(parts),
            confidence=round(confidence, 3),
            evidence=evidence,
        )

    def _fallback_evaluate(self, claim: Claim, evidence: List[Evidence]) -> ClaimVerdict:
        """Alias for _tfidf_evaluate to maintain backward compatibility with test suites."""
        return self._tfidf_evaluate(claim, evidence)
