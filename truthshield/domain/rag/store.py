"""
A searchable memory of claims this system has already adjudicated.

Misinformation repeats. The same claim arrives reworded, repackaged and
reposted, and the expensive part of answering it -- retrieval, scoring,
reading sources -- has usually already been done. This is the index that
makes the second arrival cheap.

Two lookups, and the distinction matters:

  **Near-duplicate** (>= 0.92 cosine). The same claim in different words.
  "Vaccines cause autism" and "autism is caused by childhood vaccines" are
  one question, and a prior verdict answers both.

  **Related** (>= 0.55). Not the same claim, but adjudicated neighbours worth
  showing a reader -- prior context rather than a prior answer.

A near-duplicate is never served as the answer. It is surfaced *alongside* a
fresh analysis, because evidence moves: the honest thing to show a reader is
"we answered this on the 4th, and here is what we find today", not a cached
verdict with a stale date hidden behind it.

Degrades to token overlap when embeddings are unavailable, which is the
default configuration. Overlap is a poor semantic matcher but a decent
near-duplicate matcher, and near-duplicates are the case that pays.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

# The same claim, reworded. Deliberately strict: a false hit here tells a
# reader we have already answered a question they did not ask.
NEAR_DUPLICATE = 0.92

# Adjudicated neighbours. Low enough to be useful, high enough that a claim
# about vaccines does not pull in every medical claim in the corpus.
RELATED = 0.55

# Rebuilding scans the reports table and embeds every claim, so it does not
# happen per request. A minute is short enough that a reader who submits the
# same claim twice in one sitting sees the first one.
REFRESH_SECONDS = 60.0

# An upper bound on what is held in memory. At 384 dimensions this is roughly
# 15MB of vectors -- small, but it should be a decision rather than something
# that grows silently with the table.
MAX_ENTRIES = 10_000

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "a an the is are was were be been being do does did has have had of in on "
    "at to for from by with about as that this these those it its and or but "
    "if then than".split()
)


@dataclass(frozen=True)
class PriorClaim:
    """A claim this system has already ruled on."""

    report_id: str
    text: str
    verdict: str
    trust_score: int
    created_at: Optional[str] = None
    similarity: float = 0.0

    @property
    def is_near_duplicate(self) -> bool:
        return self.similarity >= NEAR_DUPLICATE

    def as_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "text": self.text,
            "verdict": self.verdict,
            "trust_score": self.trust_score,
            "created_at": self.created_at,
            "similarity": round(self.similarity, 4),
            "near_duplicate": self.is_near_duplicate,
        }


def _tokens(text: str) -> frozenset:
    return frozenset(w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    shared = len(a & b)
    return shared / (len(a) + len(b) - shared)


@dataclass
class _Entry:
    claim: PriorClaim
    tokens: frozenset = field(default_factory=frozenset)


class ClaimMemory:
    """
    Semantic index over adjudicated claims.

    Rebuilt from the database on a timer rather than written through on every
    analysis. The read path is what matters here, a minute of staleness is
    harmless, and a write-through index would have to be invalidated from
    Celery workers that do not share this process's memory.
    """

    def __init__(self, *, refresh_seconds: float = REFRESH_SECONDS):
        self._entries: List[_Entry] = []
        self._matrix = None
        self._built_at = 0.0
        self._refresh_seconds = refresh_seconds
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def semantic(self) -> bool:
        """Whether search runs on embeddings rather than token overlap."""
        return self._matrix is not None

    # ──────────────────────────────────────────────────────────

    def refresh(self, session, *, force: bool = False) -> int:
        """
        Rebuild from the reports table. Returns the number of claims indexed.

        Cheap to call: returns immediately unless the index has aged out.
        """
        if not force and (time.monotonic() - self._built_at) < self._refresh_seconds:
            return len(self._entries)

        with self._lock:
            if not force and (time.monotonic() - self._built_at) < self._refresh_seconds:
                return len(self._entries)
            try:
                entries = self._load(session)
            except Exception as exc:
                # A failed refresh keeps serving the previous index. This runs
                # on the analysis path, and a database hiccup here must not
                # take the analysis down with it.
                logger.warning("Claim memory refresh failed, serving stale index: %s", exc)
                self._built_at = time.monotonic()
                return len(self._entries)

            self._entries = entries
            self._matrix = self._embed(entries)
            self._built_at = time.monotonic()
            logger.info(
                "Claim memory: %d claims indexed (%s)",
                len(entries),
                "embeddings" if self._matrix is not None else "lexical",
            )
            return len(entries)

    def _load(self, session) -> List[_Entry]:
        from truthshield.infra.models import Report

        rows = (
            session.query(
                Report.id,
                Report.input_text,
                Report.verdict,
                Report.trust_score,
                Report.created_at,
            )
            .filter(Report.status == "complete")
            .filter(Report.input_text.isnot(None))
            # Newest first, so the cap keeps what is current rather than
            # whatever happened to be inserted first.
            .order_by(Report.created_at.desc())
            .limit(MAX_ENTRIES)
            .all()
        )

        out: List[_Entry] = []
        for report_id, text, verdict, trust, created in rows:
            text = (text or "").strip()
            if len(text) < 12:  # too short to match on meaningfully
                continue
            out.append(
                _Entry(
                    claim=PriorClaim(
                        report_id=report_id,
                        text=text[:500],
                        verdict=verdict,
                        trust_score=int(trust or 0),
                        created_at=created.isoformat() if created else None,
                    ),
                    tokens=_tokens(text),
                )
            )
        return out

    @staticmethod
    def _embed(entries: Sequence[_Entry]):
        if not entries:
            return None
        try:
            from truthshield.ml import get_embedder

            embedder = get_embedder()
            if not embedder.available:
                return None
            return embedder.encode([e.claim.text for e in entries])
        except Exception:
            logger.debug("Claim memory falling back to lexical matching", exc_info=True)
            return None

    # ──────────────────────────────────────────────────────────

    def search(self, claim: str, *, top_k: int = 5, floor: float = RELATED) -> List[PriorClaim]:
        """Prior adjudications resembling `claim`, most similar first."""
        if not claim or not self._entries:
            return []

        scores = self._semantic_scores(claim)
        if scores is None:
            query = _tokens(claim)
            scores = [_jaccard(query, e.tokens) for e in self._entries]

        ranked = sorted(
            ((score, entry) for score, entry in zip(scores, self._entries) if score >= floor),
            key=lambda pair: pair[0],
            reverse=True,
        )
        return [
            PriorClaim(**{**vars(entry.claim), "similarity": float(score)})
            for score, entry in ranked[:top_k]
        ]

    def _semantic_scores(self, claim: str):
        if self._matrix is None:
            return None
        try:
            from truthshield.ml import get_embedder

            vector = get_embedder().encode([claim])
            if vector is None:
                return None
            import numpy as np

            return np.dot(self._matrix, vector[0]).tolist()
        except Exception:
            logger.debug("Semantic search failed, falling back to lexical", exc_info=True)
            return None

    def near_duplicate(self, claim: str) -> Optional[PriorClaim]:
        """The one prior claim that is this claim reworded, if there is one."""
        hits = self.search(claim, top_k=1, floor=NEAR_DUPLICATE)
        return hits[0] if hits else None


_memory: Optional[ClaimMemory] = None
_memory_lock = threading.Lock()


def get_claim_memory() -> ClaimMemory:
    """The process-wide claim index."""
    global _memory
    if _memory is None:
        with _memory_lock:
            if _memory is None:
                _memory = ClaimMemory()
    return _memory
