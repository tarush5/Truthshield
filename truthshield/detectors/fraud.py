"""
Deception signals in the text itself.

Every other detector here asks whether the *medium* was manipulated -- is
this image synthetic, was this voice cloned. This one asks a different
question: does the writing use the techniques of a scam, independently of
whether its claims turn out to be true?

That distinction is the whole point, and it is why this score is reported
separately rather than folded into the verdict. A true statement can be
written like a fraud, and a careful lie can be written like a news report.
Conflating "reads deceptive" with "is false" would produce exactly the
confident-and-wrong output this system is built to avoid, so the two are
kept apart and the report says which is which.

Nine signals, each scored independently and combined by weight. They were
chosen because each one is *observable in the text* -- no signal here
depends on knowing whether the claim is correct:

  urgency          Manufactured time pressure: act now, before it is too late
  authority        Unverifiable expertise: doctors agree, experts confirm
  suppression      The conspiracy frame: what they do not want you to know
  absolutes        No hedging at all, on a claim that would warrant it
  emotional        Outrage and fear vocabulary at unusual density
  shouting         Caps and punctuation used as volume
  vagueness        Statistics with no attributable source
  engagement_bait  Share before they delete this
  financial        Guaranteed returns, risk-free, act on this tip

The output is a score with the signals that produced it attached, so a
reader can disagree with the reasoning rather than only with the number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from truthshield.detectors.base import Detector
from truthshield.domain.types import (
    ContentPacket, DetectorResult, DetectorStatus,
)

# Below this there is not enough text for rate-based signals to mean
# anything: two emotive words in a six-word sentence is not a pattern.
MIN_WORDS = 12

# Above this, the combined score is called out in the report.
#
# Measured, not picked: on the calibration set in
# `.lab/fraud_calibration.py`, wire copy, encyclopedia prose, science
# reporting and product copy all score 0.000, while the scam, conspiracy and
# clickbait samples land between 0.678 and 0.919. Ordinary pushy marketing
# -- urgency and nothing else -- sits at 0.400 and is deliberately left
# unflagged, because commerce is not fraud.
FLAG_THRESHOLD = 0.45


@dataclass(frozen=True)
class Signal:
    """One deception marker, and how much it moves the score."""

    key: str
    label: str
    weight: float
    patterns: Tuple[str, ...]
    # How many hits saturate this signal. Rare tactics saturate on one
    # sighting; common vocabulary needs repetition before it means anything.
    saturate_at: int = 2


SIGNALS: Tuple[Signal, ...] = (
    Signal(
        "urgency", "Manufactured urgency", 0.9,
        (
            r"\bact (?:now|fast|immediately|today)\b",
            r"\bbefore it'?s too late\b",
            r"\b(?:limited|last) (?:time|chance|offer)\b",
            r"\bdon'?t (?:wait|delay|miss out)\b",
            r"\bhurry\b", r"\bexpires? (?:today|soon|in \d+)\b",
            r"\bonly \d+ (?:left|remaining|spots)\b",
        ),
    ),
    Signal(
        "authority", "Unverifiable authority", 0.8,
        (
            r"\b(?:doctors?|scientists?|experts?|researchers?)\s+(?:say|says|agree|confirm|warn|reveal)\b",
            r"\bstudies?\s+(?:show|prove|confirm)\b(?![^.]{0,60}\b(?:published|journal|university|doi)\b)",
            r"\b(?:top|leading|renowned)\s+(?:doctor|scientist|expert)\b",
            r"\bbig (?:pharma|tech|government)\b",
        ),
    ),
    Signal(
        "suppression", "Suppression narrative", 1.0,
        (
            r"\bthey don'?t want you to know\b",
            r"\b(?:mainstream )?media (?:won'?t|refuses? to|is hiding)\b",
            r"\b(?:being )?(?:censored|suppressed|silenced|covered up)\b",
            r"\bwake up\b", r"\bdo your own research\b",
            r"\bthe truth about\b",
            r"\bwhat (?:they|the government|doctors) (?:are hiding|won'?t tell)\b",
        ),
        saturate_at=1,
    ),
    Signal(
        "absolutes", "Unhedged absolutes", 0.5,
        (
            r"\b(?:100|1000)% (?:proven|guaranteed|effective|safe|certain)\b",
            r"\b(?:always|never|completely|totally|absolutely) (?:cures?|works?|fails?|safe|deadly)\b",
            r"\bmiracle (?:cure|drug|treatment|solution)\b",
            r"\bcures? (?:all|every|any)\b",
        ),
        saturate_at=1,
    ),
    Signal(
        "emotional", "Emotive intensifiers", 0.4,
        (
            r"\b(?:shocking|horrifying|terrifying|devastating|outrageous)\b",
            r"\b(?:disgusting|evil|corrupt|sinister|dangerous)\b",
            r"\b(?:unbelievable|insane|crazy|mind-?blowing)\b",
            r"\bwill (?:shock|horrify|terrify) you\b",
        ),
        saturate_at=3,
    ),
    Signal(
        "vagueness", "Unattributed statistics", 0.6,
        (
            r"\b\d{1,3}(?:\.\d+)?%\s+of\s+(?:people|doctors|americans|adults|patients)\b"
            r"(?![^.]{0,60}\b(?:according|survey|study|census|reported by)\b)",
            r"\b(?:studies|research|data)\s+(?:shows?|proves?)\b"
            r"(?![^.]{0,60}\b(?:published|journal|university|doi|et al)\b)",
            r"\b(?:millions|thousands|countless)\s+of\s+(?:people|victims|cases)\b",
        ),
    ),
    Signal(
        "engagement_bait", "Engagement bait", 0.7,
        (
            r"\bshare (?:this|before)\b", r"\bbefore (?:they|this) (?:delete|remove|take)\b",
            r"\btag (?:someone|a friend|everyone)\b",
            r"\bcopy and paste\b", r"\bgone viral\b",
            r"\byou won'?t believe\b",
        ),
        saturate_at=1,
    ),
    Signal(
        "financial", "Financial inducement", 0.9,
        (
            r"\bguaranteed (?:returns?|profits?|income)\b",
            r"\brisk[- ]free\b",
            r"\b(?:double|triple) your (?:money|investment)\b",
            r"\bget rich\b", r"\bpassive income\b",
            r"\b(?:crypto|forex|investment) (?:tip|secret|opportunity)\b",
            r"\bsend (?:bitcoin|btc|crypto|money)\b",
        ),
        saturate_at=1,
    ),
)


def _shouting_score(text: str) -> float:
    """
    Caps and punctuation used as volume.

    Measured as a rate, not a count: a single acronym in a short sentence
    would otherwise register the same as a sentence typed entirely in caps.
    Tokens of one or two characters are skipped so "US", "5G" and "I" do
    not read as shouting.
    """
    words = [w for w in re.findall(r"[A-Za-z]{3,}", text)]
    if len(words) < 8:
        return 0.0

    shouted = sum(1 for w in words if w.isupper())
    caps_rate = shouted / len(words)

    runs = len(re.findall(r"[!?]{2,}", text))
    exclamations = text.count("!")
    punct_rate = (runs * 2 + exclamations) / max(1, len(words) / 10)

    return min(1.0, caps_rate * 3.0 + min(0.6, punct_rate * 0.25))


def score_text(text: str) -> Tuple[float, List[Dict]]:
    """
    Deception score in [0, 1], and the signals behind it.

    The combination is a weighted mean over *fired* signals rather than over
    all of them. Dividing by the full weight table would mean a text can
    never score high unless it uses every tactic at once, which is not how
    any of this works -- one unambiguous suppression narrative is a strong
    signal on its own.
    """
    if not text or len(text.split()) < MIN_WORDS:
        return 0.0, []

    lowered = text.lower()
    fired: List[Dict] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for signal in SIGNALS:
        hits: List[str] = []
        for pattern in signal.patterns:
            for match in re.finditer(pattern, lowered, re.IGNORECASE):
                phrase = match.group(0).strip()
                if phrase and phrase not in hits:
                    hits.append(phrase)

        if not hits:
            continue

        strength = min(1.0, len(hits) / signal.saturate_at)
        weighted_sum += strength * signal.weight
        weight_total += signal.weight
        fired.append({
            "signal": signal.key,
            "label": signal.label,
            "strength": round(strength, 2),
            # Capped: the evidence for the signal, not a transcript.
            "matches": hits[:3],
        })

    shouting = _shouting_score(text)
    if shouting > 0.15:
        weighted_sum += shouting * 0.5
        weight_total += 0.5
        fired.append({
            "signal": "shouting",
            "label": "Capitalisation and punctuation as emphasis",
            "strength": round(shouting, 2),
            "matches": [],
        })

    if not fired:
        return 0.0, []

    base = weighted_sum / weight_total

    # Breadth is the confidence, not a bonus on top of it.
    #
    # The first version took a weighted mean over fired signals and added a
    # small breadth bonus, which let a single saturated signal reach the top
    # of the range: ordinary pushy marketing ("limited time, expires today,
    # thousands of customers") fired urgency alone and scored 0.85 -- above
    # the conspiracy sample. Commerce is not fraud, and a detector that says
    # so is worse than no detector.
    #
    # What actually distinguishes a scam is using several techniques at
    # once, so one signal is capped well below the flag threshold and only
    # three or more can reach the top.
    confidence = min(1.0, 0.40 + 0.30 * (len(fired) - 1))

    score = min(1.0, base * confidence)
    fired.sort(key=lambda f: -f["strength"])
    return round(score, 3), fired


class FraudSignalDetector(Detector):
    """
    Deceptive *writing*, scored separately from whether the claim is true.

    Reported on its own rather than folded into the verdict. A true claim
    can be written like a scam and a careful lie can be written like a wire
    report; treating the two as one number would manufacture exactly the
    confident-and-wrong output this system exists to avoid.
    """

    name = "fraud_signals"
    measures = "Use of deceptive persuasion techniques in the text"

    def applies_to(self, packet: ContentPacket) -> bool:
        return packet.has_text and len(packet.text.split()) >= MIN_WORDS

    def _run(self, packet: ContentPacket) -> DetectorResult:
        score, fired = score_text(packet.text)

        if not fired:
            return DetectorResult(
                name=self.name,
                status=DetectorStatus.OK,
                score=0.0,
                method="lexical-signals",
                detail="No deceptive persuasion patterns found.",
            )

        labels = ", ".join(f["label"].lower() for f in fired[:3])
        if score >= FLAG_THRESHOLD:
            detail = f"Reads as manipulative: {labels}."
        else:
            detail = f"Some persuasion markers: {labels}."

        return DetectorResult(
            name=self.name,
            status=DetectorStatus.OK,
            score=score,
            method="lexical-signals",
            # The signals, not just the number, so the reader can disagree
            # with the reasoning rather than only with the score.
            detail=f"{detail} (signals: {', '.join(f['signal'] for f in fired)})",
        )
