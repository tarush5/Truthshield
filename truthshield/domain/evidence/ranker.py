"""
Source ranking — orders evidence by publisher credibility.

Ported from the previous implementation rather than rewritten. These modules
carry a long tail of fixes that were each found by running the system against
real evidence and measuring the result — anchored domain matching, stem-based
relevance, sentence-scoped negation, typographic apostrophes, the
two-character token floor that made "5G" visible, the question-headline guard,
publisher recovery from aggregator links, and the minimum-evidence rule.
Retyping them would have quietly reintroduced the bugs they exist to prevent.

What changed in the port: imports resolve inside `truthshield`, and the public
surface is adapted to `truthshield.domain.types` via `adapters.py`.
"""

import logging
from typing import List

from truthshield.domain.credibility import UNKNOWN_DOMAIN_SCORE, score_domain
from truthshield.domain.verdict.legacy_types import Evidence

logger = logging.getLogger(__name__)


class SourceRanker:
    """Rank evidence sources by credibility score."""

    # Kept as an alias so callers that referenced the old constant keep working.
    # The value moved from 0.30 to the 0.50 the credibility table is calibrated
    # against: the tier 8/9/10 entries in config describe themselves as sitting
    # "below the 0.50 unknown-domain default", but against a 0.30 default the
    # demotions inverted — news.google.com (0.45) and nypost.com (0.40) were
    # outranking genuinely unknown domains instead of being outranked by them.
    DEFAULT_SCORE = UNKNOWN_DOMAIN_SCORE

    def score_source(self, url: str) -> float:
        """
        Score a single source URL.

        Delegates to the shared table in backend.config so this and
        EvidenceRetriever cannot drift apart again.

        Args:
            url: The source URL

        Returns:
            Credibility score (0.0 to 1.0); 0.0 marks a known disinfo domain.
        """
        return score_domain(url)

    def rank_evidence(self, evidence: List[Evidence]) -> List[Evidence]:
        """
        Score and rank evidence by source credibility.

        Args:
            evidence: List of Evidence objects

        Returns:
            Sorted list of Evidence with updated source_score
        """
        scored_evidence = []
        for ev in evidence:
            # Score whoever actually published the item. `url` can be an
            # aggregator interstitial that names nobody — scoring it rated
            # every Google News article 0.45 regardless of whether Reuters or a
            # content farm wrote it, and silently discarded the publisher the
            # retriever had already resolved.
            ev.source_score = self.score_source(getattr(ev, "source_domain", None) or ev.url)
            scored_evidence.append(ev)

        # Sort by source_score descending
        scored_evidence.sort(key=lambda e: e.source_score, reverse=True)

        logger.info(
            f"Ranked {len(scored_evidence)} evidence pieces. "
            f"Top score: {scored_evidence[0].source_score if scored_evidence else 'N/A'}"
        )

        return scored_evidence

    def filter_disinfo(self, evidence: List[Evidence]) -> List[Evidence]:
        """Remove evidence from known disinformation sources."""
        filtered = [ev for ev in evidence if ev.source_score > 0.0]
        removed_count = len(evidence) - len(filtered)
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} evidence from known disinfo sources")
        return filtered
