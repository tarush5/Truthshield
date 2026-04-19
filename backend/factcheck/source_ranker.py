"""
TruthShield — Source Ranker
Score and rank evidence sources by credibility.
"""

import logging
from typing import List
from urllib.parse import urlparse

from backend.config import KNOWN_DISINFO_DOMAINS, SOURCE_CREDIBILITY
from backend.models.schemas import Evidence

logger = logging.getLogger(__name__)


class SourceRanker:
    """Rank evidence sources by credibility score."""

    DEFAULT_SCORE = 0.3  # Unknown sources

    def score_source(self, url: str) -> float:
        """
        Score a single source URL.

        Scoring tiers:
            Government (.gov.in)     = 0.9
            Major news outlets       = 0.7-0.85
            Fact-checking sites      = 0.8-0.85
            Wikipedia                = 0.65
            Unknown                  = 0.3
            Known disinfo            = 0.0

        Args:
            url: The source URL

        Returns:
            Credibility score (0.0 to 1.0)
        """
        try:
            domain = urlparse(url).netloc.lower()
            # Remove www. prefix
            domain = domain.replace("www.", "")
        except Exception:
            return self.DEFAULT_SCORE

        # Check known disinfo domains
        for disinfo_domain in KNOWN_DISINFO_DOMAINS:
            if disinfo_domain in domain:
                return 0.0

        # Check exact matches in credibility database
        for known_domain, score in SOURCE_CREDIBILITY.items():
            if known_domain in domain:
                return score

        # Check TLD-based scoring
        if domain.endswith(".gov") or domain.endswith(".gov.in"):
            return 0.85
        elif domain.endswith(".edu") or domain.endswith(".ac.in"):
            return 0.75
        elif domain.endswith(".org"):
            return 0.55
        elif domain.endswith(".mil"):
            return 0.8

        return self.DEFAULT_SCORE

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
            ev.source_score = self.score_source(ev.url)
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
