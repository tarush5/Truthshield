"""
Text preprocessing for the investigation text engine.

Deterministic and dependency-light on purpose: everything here runs with the
base requirements, so the text engine never degrades just because the ML
extras are absent. Where a better tool exists (spaCy NER), the engine uses it
when installed and says so when it is not.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple

from truthshield.fraud.classify import extract_entities
from truthshield.fraud.detectors.url import WATCHED_BRANDS

SUPPORTED_LANGUAGES = ("en", "hi", "ta")

# ── Language ──────────────────────────────────────────────────

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
TAMIL = re.compile(r"[஀-௿]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
WORD_RE = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)


@dataclass(frozen=True)
class LanguageResult:
    detected: str
    confidence: float
    method: str
    script: str

    @property
    def supported(self) -> bool:
        return self.detected in SUPPORTED_LANGUAGES

    def as_dict(self) -> dict:
        return {
            "detected": self.detected,
            "confidence": round(self.confidence, 2),
            "method": self.method,
            "script": self.script,
            "supported": self.supported,
        }


def detect_language(text: str) -> LanguageResult:
    """
    Script first, statistics second.

    Hindi and Tamil have their own scripts, so their share of letters is a
    near-certain signal and needs no model. `langdetect` is used for Latin
    script, where it is good, and is seeded so the same text always gives the
    same answer -- an investigation has to be reproducible.
    """
    letters = LETTER.findall(text or "")
    if not letters:
        return LanguageResult("und", 0.0, "none", "none")

    total = len(letters)
    deva = len(DEVANAGARI.findall(text)) / total
    tamil = len(TAMIL.findall(text)) / total

    if deva >= 0.3:
        return LanguageResult("hi", min(1.0, 0.6 + deva * 0.4), "script", "devanagari")
    if tamil >= 0.3:
        return LanguageResult("ta", min(1.0, 0.6 + tamil * 0.4), "script", "tamil")

    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0
        best = detect_langs(text)[0]
        return LanguageResult(best.lang, float(best.prob), "langdetect", "latin")
    except Exception:
        return LanguageResult("en", 0.3, "fallback", "latin")


# ── Normalisation ─────────────────────────────────────────────

ZERO_WIDTH = re.compile(r"[​-‍⁠﻿­]")


def normalize(text: str) -> Tuple[str, int]:
    """
    NFKC, zero-width characters removed, whitespace collapsed.

    Returns the count of zero-width characters removed: they are invisible to
    a reader and exist in a message mainly to split words past keyword
    filters, so their presence is itself worth reporting.
    """
    hidden = len(ZERO_WIDTH.findall(text or ""))
    cleaned = ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text or ""))
    cleaned = re.sub(r"[ \t\f\v]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, hidden


SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")


def sentences(text: str) -> List[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text or "") if s and s.strip()]


# ── Entities ──────────────────────────────────────────────────

AMOUNT_RE = re.compile(
    r"(?:(?:₹|rs\.?|inr|usd|\$|€|£)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:lakh|lakhs|crore|crores|k|million|bn))?"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:rupees|rs|inr|usd|dollars|lakh|lakhs|crore|crores))",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}\s(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s\d{2,4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s\d{1,2},?\s\d{2,4}"
    r"|today|tomorrow|tonight|within\s\d+\s(?:hours?|hrs?|minutes?|mins?|days?))\b",
    re.IGNORECASE,
)

# Institutions impersonated often enough to name, beyond the URL brand list.
ORGANIZATIONS = (
    "RBI", "Reserve Bank", "SEBI", "Income Tax", "UIDAI", "Aadhaar", "EPFO",
    "TRAI", "Customs", "Police", "Cyber Cell", "CBI", "Supreme Court",
    "WHO", "UNICEF", "Ministry", "Government", "Amazon", "Flipkart",
)


def extract_all_entities(text: str) -> Dict[str, List[str]]:
    """Addressable entities (1.x extractor) plus amounts, dates and organisations."""
    entities = extract_entities(text)

    def unique(values):
        seen, out = set(), []
        for v in values:
            key = v.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(v.strip())
        return out

    entities["amounts"] = unique(m.group(0) for m in AMOUNT_RE.finditer(text))
    entities["dates"] = unique(m.group(0) for m in DATE_RE.finditer(text))

    lowered = text.lower()
    orgs = [o for o in ORGANIZATIONS if re.search(rf"\b{re.escape(o.lower())}\b", lowered)]
    brands = [
        b for b in WATCHED_BRANDS
        if len(b) > 3 and re.search(rf"\b{re.escape(b)}\b", lowered)
    ]
    entities["organizations"] = unique(orgs + [b.upper() if len(b) <= 4 else b.title() for b in brands])
    return entities


def spacy_entities(text: str) -> Tuple[Dict[str, List[str]], bool]:
    """People and places, when a spaCy model is installed. (entities, available)"""
    try:
        from truthshield.domain.verdict.claim_extractor import ClaimExtractor

        extractor = ClaimExtractor()
        extractor._load_nlp()
        nlp = extractor._nlp
        if nlp is None:
            return {}, False
        doc = nlp(text[:5000])
        people = sorted({e.text for e in doc.ents if e.label_ in ("PER", "PERSON")})
        places = sorted({e.text for e in doc.ents if e.label_ in ("LOC", "GPE")})
        return {"people": people, "locations": places}, True
    except Exception:
        return {}, False


# ── Intent ────────────────────────────────────────────────────

INTENTS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("credential_request", "Asks for login credentials",
     (r"\b(?:password|passcode|login details|user\s?name|credentials|net\s?banking id)\b",
      r"\b(?:sign|log)\s?in\b.{0,40}\b(?:verify|confirm|update)\b")),
    ("otp_request", "Asks for a one-time code",
     (r"\b(?:otp|one[\s-]?time\s(?:password|code)|verification code|pin|cvv)\b",)),
    ("payment_request", "Asks for a payment or transfer",
     (r"\b(?:pay|transfer|send|deposit)\b.{0,40}\b(?:fee|charge|amount|money|rs\.?|₹|inr|upi)\b",
      r"\b(?:processing|registration|customs|clearance|release)\s(?:fee|charge)\b")),
    ("prize_claim", "Announces a prize or reward",
     (r"\b(?:congratulations|you(?:'ve| have)? won|winner|lucky draw|lottery|reward|cashback|prize)\b",)),
    ("account_threat", "Threatens an account action",
     (r"\b(?:block|suspend|deactivat|freez|terminat|clos)\w*\b.{0,40}\b(?:account|card|sim|service|kyc)\b",
      r"\b(?:account|card|sim|kyc)\b.{0,40}\b(?:block|suspend|deactivat|freez|expir)\w*")),
    ("link_click", "Directs the reader to a link",
     (r"\b(?:click|tap|visit|open|follow)\b.{0,30}\b(?:link|here|below|url)\b",)),
)


def detect_intents(text: str) -> List[dict]:
    lowered = (text or "").lower()
    found = []
    for code, label, patterns in INTENTS:
        for pattern in patterns:
            match = re.search(pattern, lowered, re.IGNORECASE | re.DOTALL)
            if match:
                found.append({"intent": code, "label": label, "evidence": match.group(0)[:100]})
                break
    return found


# ── Prompt injection ─────────────────────────────────────────

INJECTION_PATTERNS = (
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above) (?:instructions|prompts?|rules)",
    r"disregard (?:all |any )?(?:the )?(?:previous|prior|above|your) (?:instructions|rules|guidelines)",
    r"(?:reveal|print|show|repeat) (?:your|the) (?:system|hidden) prompt",
    r"you are now (?:in )?(?:developer|dan|jailbreak|unrestricted) mode",
    r"(?:as an ai|to the ai|assistant:)\s.{0,40}(?:must|should) (?:classify|rate|mark) (?:this|it) as (?:safe|legitimate|benign)",
    r"<\s*/?\s*(?:system|instructions?)\s*>",
)


def detect_prompt_injection(text: str) -> List[str]:
    lowered = (text or "").lower()
    hits = []
    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, lowered, re.IGNORECASE | re.DOTALL)
        if match:
            hits.append(match.group(0)[:100])
    return hits
