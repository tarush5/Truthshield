"""
Stance detection by natural-language inference.

NLI maps onto this problem in principle. Given a premise (the evidence) and a
hypothesis (the claim):

    entailment     -> the evidence SUPPORTS the claim
    contradiction  -> the evidence REFUTES it
    neutral        -> it is on topic but takes no side

What the measurement actually showed
------------------------------------
Run against the frozen benchmark fixture, this model **did not improve a
single verdict**, and used without restraint it destroyed four:

    lexical path only            9 correct   0 wrong   3 abstaining
    + NLI, all labels, >= 0.90   5 correct   4 wrong   3 abstaining
    + NLI, refutation, >= 0.98   9 correct   0 wrong   3 abstaining

The failures are systematic, not noise, and they come from the premise being
a *headline* rather than a proposition:

* **Fact-check headlines carry a refutational form the model reads as a
  verdict.** "Full Fact: No, the NASA astronauts killed in the 1986
  Challenger disaster are not still alive" is scored a 0.99 contradiction of
  a flat-Earth claim -- and so is a PolitiFact headline about Medicaid in
  Maine, at 0.996. The model is matching the shape of a debunk, not its
  subject.

* **Question headlines read as agreement.** "Do We Really Use Only 10 Percent
  of Our Brain?" -- an article that refutes the claim -- is scored SUPPORTS.

* **It is not robust to the surrounding format.** "Your whole brain is always
  at work" is a 0.99 contradiction on its own and NEUTRAL at 0.99 once it
  arrives as "title. snippet", which is how the pipeline actually has it.

So it is wired in deliberately narrowly: **refutation only, above 0.98**, the
one configuration measured not to regress. It earns its place as a safety net
for the contradiction that shares no vocabulary with its claim, not as an
accuracy gain -- there is no evidence here that it is one. It resolves none
of the three abstentions; those are a retrieval-quality problem, and
filtering the evidence by embedding relevance did not fix them either
(9/0/3 unfiltered, 8/0/4 at a 0.40 floor).

Re-run `.lab/sweep.py` before widening any of this.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence

from truthshield.settings import get_settings

logger = logging.getLogger(__name__)

# Batched, this runs at ~18ms per pair on CPU. The base-size model is more
# accurate but ~340ms per pair, which at 15 evidence items per claim is the
# difference between a fifth of a second and five seconds.
DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-xsmall"

# Below this the answer is discarded. Set from the sweep in the module
# docstring, not from intuition: at 0.90 and 0.95 the fixture lost four
# verdicts, at 0.98 it lost none.
CONFIDENCE_FLOOR = 0.98

# Reading a long article body as a premise costs time and rarely changes the
# label — the lead sentences carry the position.
MAX_PREMISE_CHARS = 1000


class StanceLabel(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"      # model unavailable, or below the confidence floor


@dataclass(frozen=True)
class StancePrediction:
    label: StanceLabel
    confidence: float

    @property
    def usable(self) -> bool:
        return self.label is not StanceLabel.UNKNOWN


UNKNOWN = StancePrediction(StanceLabel.UNKNOWN, 0.0)

_TO_STANCE = {
    "entailment": StanceLabel.SUPPORTS,
    "contradiction": StanceLabel.REFUTES,
    "neutral": StanceLabel.NEUTRAL,
}


class StanceModel:
    """Lazily-loaded NLI cross-encoder. Safe to call when unavailable."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None
        self._tokenizer = None
        self._labels: List[str] = []
        self._error: Optional[str] = None
        self._attempted = False
        self._lock = threading.Lock()

    def _load(self) -> None:
        if self._attempted:
            return
        with self._lock:
            if self._attempted:
                return
            self._attempted = True

            if not get_settings().ENABLE_ML_DETECTORS:
                self._error = "ENABLE_ML_DETECTORS is false"
                return
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                cache = str(get_settings().MODEL_CACHE_DIR)
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, cache_dir=cache)
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    self.model_name, cache_dir=cache,
                )
                self._model.eval()

                # Label order differs between checkpoints, so it is read from
                # the config rather than assumed.
                config = self._model.config
                self._labels = [
                    config.id2label[i].lower() for i in range(config.num_labels)
                ]

                # Uncapped, torch spawns a thread per core and the resulting
                # contention makes small batches slower, not faster.
                torch.set_num_threads(min(4, torch.get_num_threads()))
                logger.info("Stance model ready: %s (%s)", self.model_name, self._labels)
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"
                logger.info(
                    "Stance model unavailable (%s). Stance falls back to the "
                    "lexical rules.", self._error,
                )

    @property
    def available(self) -> bool:
        self._load()
        return self._model is not None

    @property
    def error(self) -> Optional[str]:
        self._load()
        return self._error

    # ──────────────────────────────────────────────────────────

    def classify(
        self,
        claim: str,
        evidence_texts: Sequence[str],
        *,
        floor: float = CONFIDENCE_FLOOR,
    ) -> List[StancePrediction]:
        """
        Stance of each piece of evidence toward the claim.

        Always returns one prediction per input, UNKNOWN where the model could
        not run or was not confident enough — so the caller never has to
        reconcile a shorter list with its inputs.
        """
        if not evidence_texts:
            return []
        if not self.available:
            return [UNKNOWN] * len(evidence_texts)

        try:
            import torch

            premises = [t[:MAX_PREMISE_CHARS] for t in evidence_texts]
            hypotheses = [claim] * len(premises)

            with torch.inference_mode():
                batch = self._tokenizer(
                    premises, hypotheses,
                    padding=True, truncation=True, max_length=256,
                    return_tensors="pt",
                )
                probabilities = torch.softmax(self._model(**batch).logits, dim=-1)

            out: List[StancePrediction] = []
            for row in probabilities:
                index = int(row.argmax())
                confidence = float(row[index])
                label = _TO_STANCE.get(self._labels[index], StanceLabel.NEUTRAL)
                out.append(
                    StancePrediction(label, confidence)
                    if confidence >= floor else UNKNOWN
                )
            return out
        except Exception as exc:
            logger.warning("Stance classification failed: %s", exc)
            return [UNKNOWN] * len(evidence_texts)


_stance: Optional[StanceModel] = None
_stance_lock = threading.Lock()


def get_stance_model() -> StanceModel:
    """The process-wide stance model."""
    global _stance
    if _stance is None:
        with _stance_lock:
            if _stance is None:
                _stance = StanceModel()
    return _stance
