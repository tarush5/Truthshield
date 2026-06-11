"""
TruthShield — Claim Extractor
Extract verifiable claims from text using spaCy NER + dependency parsing.
Supports English, Hindi, Tamil via multilingual spaCy models.
"""

import logging
import re
from typing import List

from backend.models.schemas import Claim

logger = logging.getLogger(__name__)


class ClaimExtractor:
    """Extract verifiable factual claims from text."""

    # ── Class-level model cache (singleton per process) ──────
    _shared_nlp = None
    _shared_nlp_loaded = False

    def __init__(self):
        self._nlp = None
        self._nlp_loaded = False

    def _load_nlp(self, lang: str = "en"):
        """Lazy-load spaCy model (cached at class level)."""
        if self._nlp_loaded:
            return
        # Use class-level cache so model loads once per process
        if ClaimExtractor._shared_nlp_loaded:
            self._nlp = ClaimExtractor._shared_nlp
            self._nlp_loaded = True
            return
        try:
            import spacy

            # Use multilingual model for all languages
            try:
                ClaimExtractor._shared_nlp = spacy.load("xx_ent_wiki_sm")
            except OSError:
                try:
                    ClaimExtractor._shared_nlp = spacy.load("en_core_web_sm")
                except OSError:
                    logger.warning("No spaCy model found. Using rule-based extraction.")
                    ClaimExtractor._shared_nlp = None

            ClaimExtractor._shared_nlp_loaded = True
            self._nlp = ClaimExtractor._shared_nlp
            self._nlp_loaded = True
        except ImportError:
            logger.warning("spaCy not available. Using rule-based extraction.")
            ClaimExtractor._shared_nlp_loaded = True
            self._nlp_loaded = True

    def extract(self, text: str, lang: str = "en") -> List[Claim]:
        """
        Extract verifiable claims from text.

        Args:
            text: Input text
            lang: Language code (en/hi/ta)

        Returns:
            List of Claim objects with extracted entities and metadata
        """
        self._load_nlp(lang)

        if self._nlp is not None:
            claims = self._spacy_extract(text)
        else:
            claims = self._rule_based_extract(text)

        # CRITICAL: If no claims were extracted, treat the entire input as a single claim.
        # This ensures every submission gets fact-checked.
        if not claims and text and len(text.strip()) >= 10:
            clean_text = text.strip()
            # Truncate very long texts
            if len(clean_text) > 500:
                clean_text = clean_text[:500]

            # Try to extract key entities from the text
            # Match PascalCase ("Delhi", "Donald Trump") and ALL-CAPS acronyms ("NASA", "WHO")
            pascal_entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", clean_text)
            allcaps_entities = re.findall(r"\b[A-Z]{2,}\b", clean_text)
            # Filter out common all-caps noise
            noise_words = {"BREAKING", "JUST", "IN", "SHARE", "NOW", "THE", "AND", "OR", "NOT", "FOR", "THIS", "IS", "IT", "AT", "TO", "IF", "OF"}
            allcaps_entities = [e for e in allcaps_entities if e not in noise_words]

            all_entities = allcaps_entities + pascal_entities
            entity = all_entities[0] if all_entities else None

            claims.append(Claim(
                text=clean_text,
                entity=entity,
                date=None,
                location=None,
            ))
            logger.info("No structured claims found; treating entire input as a single claim.")

        return claims

    def _spacy_extract(self, text: str) -> List[Claim]:
        """Extract claims using spaCy NER and dependency parsing."""
        doc = self._nlp(text[:5000])  # Limit text length
        claims = []
        seen_claims = set()

        # Extract sentences containing named entities
        for sent in doc.sents:
            entities = [ent for ent in doc.ents if ent.start >= sent.start and ent.end <= sent.end]

            if not entities:
                continue

            claim_text = sent.text.strip()

            # Skip very short or very long sentences
            if len(claim_text) < 15 or len(claim_text) > 500:
                continue

            # Skip questions and exclamations (not claims)
            if claim_text.endswith("?"):
                continue

            # Deduplicate
            if claim_text.lower() in seen_claims:
                continue
            seen_claims.add(claim_text.lower())

            # Extract relevant entities
            entity_text = ", ".join(set(ent.text for ent in entities[:3]))
            date_ents = [ent.text for ent in entities if ent.label_ in ("DATE", "TIME")]
            loc_ents = [ent.text for ent in entities if ent.label_ in ("GPE", "LOC", "FAC")]

            claims.append(
                Claim(
                    text=claim_text,
                    entity=entity_text or None,
                    date=date_ents[0] if date_ents else None,
                    location=loc_ents[0] if loc_ents else None,
                )
            )

        logger.info(f"Extracted {len(claims)} claims from text ({len(text)} chars)")
        return claims[:10]  # Limit to top 10 claims

    def _rule_based_extract(self, text: str) -> List[Claim]:
        """Fallback rule-based claim extraction."""
        claims = []
        seen = set()

        # Split into sentences
        sentences = re.split(r"[।.!]\s+", text)

        # Claim indicators — patterns that suggest verifiable statements
        claim_patterns = [
            r"\b\d+\s*(%|percent|crore|lakh|million|billion)\b",
            r"\b(government|minister|official|authority|court)\b",
            r"\b(announced|declared|stated|reported|confirmed|revealed)\b",
            r"\b(study|research|report|survey|data)\s+(shows?|finds?|reveals?|indicates?)\b",
            r"\b(according to|as per|sources say)\b",
            r"\b(सरकार|मंत्री|रिपोर्ट|अध्ययन|आंकड़े)\b",  # Hindi
            r"\b(அரசு|அமைச்சர்|அறிக்கை|ஆய்வு)\b",  # Tamil
            # Added broader patterns for general factual claims
            r"\b(is|are|was|were|has|have|will|can|could|should)\b",
            r"\b(never|always|every|all|none|no one)\b",
            r"\b(true|false|fake|real|hoax|myth|fact)\b",
            r"\b(causes?|prevents?|cures?|kills?|destroys?)\b",
            r"\b(proves?|shows?|confirms?|denies?)\b",
        ]

        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10 or len(sent) > 500:
                continue
            if sent.endswith("?"):
                continue

            # Check if sentence matches claim patterns
            is_claim = any(
                re.search(pattern, sent, re.IGNORECASE) for pattern in claim_patterns
            )

            if is_claim and sent.lower() not in seen:
                seen.add(sent.lower())

                # Basic entity extraction using regex
                numbers = re.findall(r"\b\d[\d,.]*\b", sent)
                entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", sent)

                claims.append(
                    Claim(
                        text=sent,
                        entity=entities[0] if entities else None,
                        date=None,
                        location=None,
                    )
                )

        logger.info(f"Rule-based extraction: {len(claims)} claims")
        return claims[:10]
