"""
Scientific literature as evidence. **Off by default -- it measured badly.**

The idea was sound: the benchmark's abstentions cluster on claims a paper
settles and a news search does not -- whether vitamin C prevents colds,
whether cracking knuckles causes arthritis. Those have decades of published
work behind them, while news and encyclopedia sources return commentary
*about* the question rather than a finding.

It does not work well enough to enable, and the measurements are here so
nobody rebuilds it expecting a different answer.

Europe PMC -- fast (~300-800ms) and poorly targeted. Its free-text search
cannot bridge a colloquial claim to medical vocabulary. For "cracking your
knuckles causes arthritis" it returned "Diagnostic challenges of
dermatomyositis"; for "microwaving food makes it radioactive", "A tendency
coefficient-driven Pythagorean fuzzy distance approach". Query shape did
not rescue it: bag-of-words, AND-joined and TITLE-scoped variants all
returned the same unrelated papers. (One real bug was found and fixed along
the way -- `sort=CITED desc` was returning the most-cited paper matching
*any* term, which is why the first results were famous and irrelevant.)

OpenAlex -- better targeted, too slow, and inconsistent. It found exactly
the right papers for knuckle cracking on one run ("Does knuckle cracking
lead to arthritis of the fingers?") and zero on the next, taking 4083ms to
do it. Median about 2s against a whole-request median of 1537ms, so
enabling it would more than double request latency. Relevance was roughly
half useful: "Vitamin C and Immune Function" alongside "Vitamin D
supplementation" for a vitamin C claim, "Cold Plasma on Food Quality" for
microwaving.

The combination is what disqualifies it. Noisy evidence enters at
source_score 0.82, which outranks most news, so a wrong paper does not
merely fail to help -- it outweighs sources that would have. This codebase
spent real effort removing off-topic evidence; adding a slow source of more
of it is the wrong direction.

Kept and wired behind `ENABLE_SCHOLARLY_SOURCES` rather than deleted,
because a deployment weighted toward medical claims, with a tolerance for
latency, might reasonably decide differently -- and because the next person
to have this idea should find the numbers rather than the idea.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# Short: these run inside a shared fan-out budget, and a source that blocks
# the early-exit hurts every request whether or not it eventually answers.
TIMEOUT = 4.0

# Enough to establish a finding, few enough not to swamp the evidence list.
MAX_RESULTS = 4

# Abstracts run to thousands of characters. The first few hundred carry the
# finding; the rest is method and funding.
MAX_ABSTRACT = 600

# Identifies the caller, which is what both services ask for in place of a
# key. Anonymous bulk querying is how a free tier gets withdrawn.
USER_AGENT = "TruthShield/2.0 (misinformation analysis; contact via repository)"

# A review synthesises a literature; a single study is one data point. The
# ceiling stays under the fact-checkers' 0.95 so an explicit published
# debunk still outranks a paper the engine had to interpret.
SCORE_REVIEW = 0.92
SCORE_STUDY = 0.82
SCORE_PREPRINT = 0.60

_REVIEW_RE = re.compile(
    r"\b(systematic review|meta[- ]analysis|cochrane|review of|umbrella review)\b",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text or "").replace("&nbsp;", " ").strip()


def _score_for(title: str, journal: str, is_preprint: bool) -> float:
    if is_preprint:
        return SCORE_PREPRINT
    if _REVIEW_RE.search(f"{title} {journal}"):
        return SCORE_REVIEW
    return SCORE_STUDY


def search_europepmc(query: str, session, evidence_cls) -> List:
    """
    Biomedical literature via Europe PMC.

    `resultType=core` is what returns abstracts; the default returns
    metadata only, which would give the stance detector a title and nothing
    to read.
    """
    if not query or not query.strip():
        return []

    try:
        response = session.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={
                "query": query,
                "format": "json",
                "pageSize": MAX_RESULTS,
                "resultType": "core",
                # No explicit sort: Europe PMC's default is relevance, and
                # asking for `CITED desc` instead returned the most-cited
                # paper matching *any* term. That gave "Heart Disease and
                # Stroke Statistics" for a claim about sugar and
                # hyperactivity, and "connective tissue disease" for one
                # about knuckle cracking -- highly cited, entirely unrelated.
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            return []
        payload = response.json()
    except Exception as exc:
        logger.debug("Europe PMC unavailable: %s", exc)
        return []

    out = []
    for record in (payload.get("resultList", {}) or {}).get("result", [])[:MAX_RESULTS]:
        title = _clean(record.get("title", ""))
        abstract = _clean(record.get("abstractText", ""))
        if not title or not abstract:
            continue

        journal = _clean(record.get("journalTitle", ""))
        is_preprint = (record.get("source", "") or "").upper() == "PPR"

        doi = record.get("doi")
        pmid = record.get("pmid")
        if doi:
            url = f"https://doi.org/{doi}"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            url = "https://europepmc.org/"

        label = journal or "Europe PMC"
        if is_preprint:
            # Said in the title, because it travels with the evidence into
            # the report and a reader should not have to know that "PPR"
            # means unreviewed.
            label = f"{label} (preprint, not peer reviewed)"

        out.append(evidence_cls(
            title=f"{label}: {title}",
            url=url,
            snippet=abstract[:MAX_ABSTRACT],
            source_score=_score_for(title, journal, is_preprint),
        ))
    return out


def search_openalex(query: str, session, evidence_cls) -> List:
    """
    Cross-disciplinary literature via OpenAlex.

    Abstracts arrive as an inverted index -- a word-to-positions map -- so
    they have to be reassembled before they are any use as evidence.
    """
    if not query or not query.strip():
        return []

    try:
        response = session.get(
            "https://api.openalex.org/works",
            params={
                "search": query,
                "per-page": MAX_RESULTS,
                "sort": "relevance_score:desc",
                # Records with no abstract are citations, not evidence.
                "filter": "has_abstract:true",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            return []
        payload = response.json()
    except Exception as exc:
        logger.debug("OpenAlex unavailable: %s", exc)
        return []

    out = []
    for work in (payload.get("results") or [])[:MAX_RESULTS]:
        title = _clean(work.get("display_name", ""))
        abstract = _abstract_from_index(work.get("abstract_inverted_index"))
        if not title or not abstract:
            continue

        venue = ""
        location = work.get("primary_location") or {}
        source = location.get("source") or {}
        venue = _clean(source.get("display_name", "")) or "OpenAlex"

        is_preprint = (work.get("type", "") or "").lower() in ("preprint", "posted-content")
        if is_preprint:
            venue = f"{venue} (preprint, not peer reviewed)"

        out.append(evidence_cls(
            title=f"{venue}: {title}",
            url=work.get("doi") or work.get("id") or "https://openalex.org/",
            snippet=abstract[:MAX_ABSTRACT],
            source_score=_score_for(title, venue, is_preprint),
        ))
    return out


def _abstract_from_index(index: Optional[dict]) -> str:
    """
    Rebuild prose from OpenAlex's inverted index.

    The index maps each word to the positions it occupies, so the abstract
    is recovered by sorting words back into position order.
    """
    if not index:
        return ""
    try:
        positions = [
            (position, word)
            for word, spots in index.items()
            for position in spots
        ]
        positions.sort()
        return " ".join(word for _, word in positions)
    except Exception:
        return ""
