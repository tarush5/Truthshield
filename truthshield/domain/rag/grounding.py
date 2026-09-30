"""
Retrieval-augmented explanation.

The verdict is decided by the scoring engine, not here. This layer answers
the separate question a reader actually asks -- *why* -- by writing a short
explanation that is tied to the retrieved sources.

The whole design is about one failure mode. A language model handed a claim
and a stack of sources will write a fluent paragraph whether or not the
sources say what it claims they say, and a fluent paragraph with a citation
marker on it is more persuasive than no explanation at all. That makes an
ungrounded explanation worse than none on a misinformation product.

So three things are enforced, in order:

  1. **The model sees only retrieved text.** Sources are numbered and passed
     verbatim. It is told to answer from them and to say so when they do not
     settle the question.

  2. **Every citation is checked against the real source list.** A `[4]` when
     three sources were supplied is a hallucinated citation. Markers that do
     not resolve are stripped, and an explanation that loses all of its
     citations that way is discarded entirely rather than shown uncited.

  3. **The verdict is never taken from the model.** It may disagree with the
     engine in prose; it cannot change the ruling, the trust score or the
     stance labels. Explanation and adjudication stay separate so a
     persuasive generator cannot overturn a measured result.

With no API key configured, `explain()` returns None and callers show the
engine's own signal-derived reasoning. That is the default, and everything
downstream treats a missing explanation as normal rather than as an error.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

# Enough context to judge a claim; short enough to keep latency and cost
# sane. Past this, snippets repeat themselves more than they inform.
MAX_SOURCES = 8
MAX_SNIPPET_CHARS = 420

# A citation marker: [1], [2,3], [1, 4].
_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

_PROMPT = """You explain fact-check results. You are given a claim and numbered sources.

Write 2-3 sentences explaining what the sources show about the claim.

Rules:
- Use ONLY the numbered sources below. Do not add outside knowledge.
- Cite every factual statement with a marker like [1] or [2,3].
- Only cite source numbers that appear in the list.
- If the sources do not settle the claim, say so plainly.
- No preamble, no restating the claim, no hedging boilerplate. Start with the substance.

CLAIM: {claim}

SOURCES:
{sources}

EXPLANATION:"""


@dataclass(frozen=True)
class GroundedExplanation:
    """An explanation whose citations have been checked against the sources."""

    text: str
    cited: List[int]           # 1-based source numbers actually referenced
    model: str
    source_count: int

    @property
    def is_grounded(self) -> bool:
        return bool(self.cited)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "cited_sources": self.cited,
            "model": self.model,
            "source_count": self.source_count,
        }


def build_context(evidence: Sequence, *, limit: int = MAX_SOURCES) -> List[dict]:
    """
    Numbered, truncated sources for the prompt.

    Order is preserved: callers hand evidence in relevance order, and the
    numbering a reader sees in the explanation should match the order they
    see in the source list.
    """
    context: List[dict] = []
    for index, ev in enumerate(evidence[:limit], start=1):
        title = (getattr(ev, "title", "") or "").strip()
        snippet = (getattr(ev, "snippet", "") or "").strip()
        if not title and not snippet:
            continue
        context.append({
            "n": index,
            "title": title[:200],
            "snippet": snippet[:MAX_SNIPPET_CHARS],
            "url": getattr(ev, "url", "") or "",
        })
    return context


def _render(context: Sequence[dict]) -> str:
    return "\n\n".join(
        f"[{c['n']}] {c['title']}\n{c['snippet']}" for c in context
    )


def _verify(text: str, valid: set) -> tuple:
    """
    Strip citations that point at sources which do not exist.

    Returns the cleaned text and the sorted set of numbers it genuinely
    cites. A model that invents `[7]` against four sources gets that marker
    removed rather than passed to a reader who would reasonably trust it.
    """
    cited = set()

    def replace(match: re.Match) -> str:
        numbers = [int(n) for n in match.group(1).split(",")]
        real = [n for n in numbers if n in valid]
        if not real:
            return ""
        cited.update(real)
        return "[" + ",".join(str(n) for n in real) + "]"

    cleaned = _CITATION.sub(replace, text)
    # Removing a marker can leave " ." or a double space behind.
    cleaned = re.sub(r"\s+([.,;])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned, sorted(cited)


def explain(claim: str, evidence: Sequence) -> Optional[GroundedExplanation]:
    """
    A grounded explanation of what the evidence shows, or None.

    None is a normal outcome, not a failure: no API key, no usable sources,
    or a model answer that could not be grounded. Callers fall back to the
    engine's own reasoning.
    """
    context = build_context(evidence)
    if len(context) < 2:
        # One source cannot corroborate anything. Explaining from it would
        # dress a single snippet up as a survey of the evidence.
        return None

    prompt = _PROMPT.format(claim=claim.strip()[:500], sources=_render(context))

    try:
        answer, model = _complete(prompt)
    except Exception as exc:
        logger.info("Grounded explanation unavailable: %s", exc)
        return None

    if not answer:
        return None

    text, cited = _verify(answer.strip(), {c["n"] for c in context})
    if not cited:
        # Either it cited nothing or every marker was invented. An uncited
        # paragraph is exactly the fluent-but-unmoored output this layer
        # exists to keep out.
        logger.info("Discarded an explanation with no verifiable citations")
        return None

    return GroundedExplanation(
        text=text, cited=cited, model=model, source_count=len(context),
    )


def _complete(prompt: str) -> tuple:
    """
    Run the prompt against whichever provider is configured.

    Gemini first, Claude second -- matching the verdict engine's order so an
    operator has one set of keys to reason about rather than two.
    """
    from truthshield.settings import get_settings

    settings = get_settings()

    gemini_key = getattr(settings, "GEMINI_API_KEY", None)
    if gemini_key:
        from truthshield.domain.verdict.llm_config import GEMINI_MODEL
        text = _gemini(prompt, str(gemini_key), GEMINI_MODEL)
        if text:
            return text, GEMINI_MODEL

    claude_key = getattr(settings, "ANTHROPIC_API_KEY", None)
    if claude_key:
        from truthshield.domain.verdict.llm_config import CLAUDE_MODEL
        text = _claude(prompt, str(claude_key), CLAUDE_MODEL)
        if text:
            return text, CLAUDE_MODEL

    return None, ""


def _gemini(prompt: str, key: str, model: str) -> Optional[str]:
    import httpx

    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "content-type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            # Low temperature: this is a summarisation task over supplied
            # text, and creative variation here reads as invention.
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
        },
        timeout=20.0,
    )
    response.raise_for_status()
    candidates = response.json().get("candidates") or []
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts) or None


def _claude(prompt: str, key: str, model: str) -> Optional[str]:
    import httpx

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 400,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=20.0,
    )
    response.raise_for_status()
    blocks = response.json().get("content") or []
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text") or None
