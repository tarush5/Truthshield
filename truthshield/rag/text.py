"""
Text utilities for the evidence store: chunking, query expansion, passage
selection. Deterministic, so the same document always yields the same chunks
and the same claim the same queries.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

_SENTENCE = re.compile(r"(?<=[.!?।])\s+")
_WORD = re.compile(r"[^\W_]+", re.UNICODE)

STOPWORDS = frozenset("""
a an and are as at be been but by for from had has have he her his i if in into is it its of on or our she
so than that the their them then there these they this those to was we were what when where which who why
will with would you your not no nor do does did can could should may might must about after before over
also just very more most such only own same too says said claims claim according reported report new
""".split())

NEGATIONS = frozenset({"not", "no", "never", "nor", "cannot", "isn't", "aren't", "doesn't", "don't", "won't", "wasn't"})


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    start: int
    end: int


def chunk_text(text: str, *, target: int = 700, overlap: int = 1) -> List[Chunk]:
    """
    Sentence-aware chunks of roughly `target` characters.

    Never splits inside a sentence (a claim's evidence is usually one), and
    repeats the last `overlap` sentence(s) at the start of the next chunk so
    a statement spanning a boundary is retrievable from either side.
    """
    text = (text or "").strip()
    if not text:
        return []
    sentences, offsets, cursor = [], [], 0
    for part in _SENTENCE.split(text):
        if not part.strip():
            continue
        start = text.find(part, cursor)
        sentences.append(part)
        offsets.append(start)
        cursor = start + len(part)

    chunks: List[Chunk] = []
    i = 0
    while i < len(sentences):
        j, size = i, 0
        while j < len(sentences) and (size == 0 or size + len(sentences[j]) <= target):
            size += len(sentences[j]) + 1
            j += 1
        start = offsets[i]
        end = offsets[j - 1] + len(sentences[j - 1])
        chunks.append(Chunk(index=len(chunks), text=text[start:end], start=start, end=end))
        if j >= len(sentences):
            break
        i = max(i + 1, j - overlap)
    return chunks


def terms(text: str) -> List[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in STOPWORDS and len(w) > 1]


def expand_query(claim: str) -> List[Tuple[str, str]]:
    """
    (strategy, query) variants for one claim.

    * `original`   -- the claim as written
    * `keywords`   -- content words only; search engines and BM25 both do
                      better without function words
    * `neutral`    -- negations removed, so sources that *contradict* the claim
                      ("X does not cause Y") are found as readily as those that
                      repeat it
    * `entities`   -- capitalised names and numbers, the anchors a fact-check
                      is usually filed under
    """
    claim = " ".join((claim or "").split())
    out: List[Tuple[str, str]] = [("original", claim)]
    keywords = " ".join(dict.fromkeys(terms(claim)))[:200]
    if keywords and keywords.lower() != claim.lower():
        out.append(("keywords", keywords))
    neutral = " ".join(w for w in claim.split() if w.lower().strip(".,;:!?") not in NEGATIONS)
    if neutral != claim:
        out.append(("neutral", neutral))
    entities = re.findall(r"\b(?:[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)*|\d[\d,.%]*)\b", claim)
    entities = [e for e in dict.fromkeys(entities) if e.lower() not in STOPWORDS]
    if len(entities) >= 2:
        out.append(("entities", " ".join(entities)))
    seen, unique = set(), []
    for strategy, query in out:
        key = query.lower()
        if key not in seen:
            seen.add(key)
            unique.append((strategy, query))
    return unique


def bm25_scores(query: str, documents: Sequence[str], *, k1: float = 1.5, b: float = 0.75) -> List[float]:
    """Okapi BM25 of `query` against each document (used where Postgres FTS is not)."""
    q = terms(query)
    docs = [terms(d) for d in documents]
    if not q or not docs:
        return [0.0] * len(documents)
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n or 1.0
    df = {t: sum(1 for d in docs if t in d) for t in set(q)}
    scores = []
    for d in docs:
        length = len(d) or 1
        counts = {}
        for t in d:
            counts[t] = counts.get(t, 0) + 1
        score = 0.0
        for t in q:
            f = counts.get(t, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * length / avgdl))
        scores.append(score)
    return scores


def best_passage(query: str, text: str, *, sentences: int = 2, max_chars: int = 500) -> str:
    """The `sentences` most query-relevant consecutive sentences of a chunk."""
    parts = [p for p in _SENTENCE.split(text or "") if p.strip()]
    if len(parts) <= sentences:
        return text[:max_chars]
    qset = set(terms(query))
    windows = [" ".join(parts[i:i + sentences]) for i in range(len(parts) - sentences + 1)]
    best = max(windows, key=lambda w: len(qset & set(terms(w))))
    return best[:max_chars]
