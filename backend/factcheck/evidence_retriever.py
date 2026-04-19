"""
TruthShield — Evidence Retriever (v2 — Fast & Accurate)

Retrieves evidence from FREE sources only, all concurrently:
  1. DuckDuckGo text search (ddgs) — primary web evidence
  2. DuckDuckGo news search (ddgs) — breaking news
  3. Wikipedia — encyclopedic context
  4. Google Fact Check Tools API — dedicated fact-check verdicts

Paid/broken APIs (NewsData, GNews, NewsAPI, GDELT, Google CSE) are removed
to eliminate wasted timeout cycles.
"""

import logging
import math
import re
import concurrent.futures
from typing import List
from urllib.parse import quote_plus, urlparse

from backend.config import get_settings, SOURCE_CREDIBILITY
from backend.models.schemas import Claim, Evidence

logger = logging.getLogger(__name__)

# Timeout per individual source (seconds)
_SOURCE_TIMEOUT = 4


class EvidenceRetriever:
    """Retrieve evidence from multiple free sources concurrently."""

    MAX_EVIDENCE_PER_CLAIM = 6

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    async def retrieve(self, claim: Claim) -> List[Evidence]:
        """Fetch evidence from all sources in parallel, dedup, and return."""
        wiki_query = (
            claim.entity
            if getattr(claim, "entity", None)
            else self._extract_search_terms(claim.text)
        )

        import asyncio

        tasks = [
            asyncio.create_task(asyncio.to_thread(self._ddg_text_search, claim.text)),
            asyncio.create_task(asyncio.to_thread(self._ddg_news_search, claim.text)),
            asyncio.create_task(asyncio.to_thread(self._search_wikipedia, wiki_query)),
            asyncio.create_task(asyncio.to_thread(self._google_factcheck, claim.text)),
        ]

        # Use strict timeout. Unfinished tasks are abandoned to prevent blocking.
        done, pending = await asyncio.wait(tasks, timeout=_SOURCE_TIMEOUT)

        all_evidence: List[Evidence] = []
        for task in done:
            try:
                results = task.result()
                all_evidence.extend(results)
            except Exception as exc:
                logger.warning(f"Source failed: {exc}")

        # Deduplicate by URL
        seen = set()
        unique = []
        for ev in all_evidence:
            if ev.url and ev.url not in seen:
                seen.add(ev.url)
                unique.append(ev)

        logger.info(
            f"Evidence for '{claim.text[:60]}…': "
            f"{len(unique)} unique (from {len(all_evidence)} raw)"
        )
        return unique[: self.MAX_EVIDENCE_PER_CLAIM]

    # ──────────────────────────────────────────────────────────
    # Source: DuckDuckGo text search (ddgs)
    # ──────────────────────────────────────────────────────────

    def _ddg_text_search(self, query: str) -> List[Evidence]:
        """Primary web search via ddgs library."""
        try:
            from ddgs import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(f"{query} fact check", max_results=3):
                    url = r.get("href", r.get("link", ""))
                    title = r.get("title", "")
                    snippet = r.get("body", r.get("snippet", ""))
                    if title and url:
                        results.append(
                            Evidence(
                                title=title,
                                url=url,
                                snippet=(snippet or "")[:300],
                                source_score=self._score_source(url),
                            )
                        )
            return results
        except Exception as e:
            logger.warning(f"ddgs text search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Source: DuckDuckGo news search
    # ──────────────────────────────────────────────────────────

    def _ddg_news_search(self, query: str) -> List[Evidence]:
        """Recent news via ddgs news endpoint."""
        try:
            from ddgs import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=2):
                    url = r.get("url", "")
                    title = r.get("title", "")
                    snippet = r.get("body", "")
                    if title and url:
                        results.append(
                            Evidence(
                                title=title,
                                url=url,
                                snippet=(snippet or "")[:300],
                                source_score=self._score_source(url),
                            )
                        )
            return results
        except Exception as e:
            logger.warning(f"ddgs news search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Source: Wikipedia
    # ──────────────────────────────────────────────────────────

    def _search_wikipedia(self, entity: str) -> List[Evidence]:
        """Search Wikipedia for context about the claim entity."""
        if not entity:
            return []
        try:
            import requests

            params = {
                "action": "query",
                "list": "search",
                "srsearch": entity,
                "format": "json",
                "srlimit": 2,
            }
            resp = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params=params,
                headers={"User-Agent": "TruthShield/2.0"},
                timeout=_SOURCE_TIMEOUT,
            )
            data = resp.json()

            results = []
            for item in data.get("query", {}).get("search", []):
                snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                results.append(
                    Evidence(
                        title=item.get("title", ""),
                        url=f"https://en.wikipedia.org/wiki/{quote_plus(item['title'])}",
                        snippet=snippet[:300],
                        source_score=0.65,
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Source: Google Fact Check Tools API (free, no key)
    # ──────────────────────────────────────────────────────────

    def _google_factcheck(self, query: str) -> List[Evidence]:
        """Search Google Fact Check Tools API."""
        try:
            import requests

            resp = requests.get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params={"query": query, "languageCode": "en"},
                timeout=_SOURCE_TIMEOUT,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for claim_review in data.get("claims", [])[:3]:
                reviews = claim_review.get("claimReview", [])
                for review in reviews[:1]:
                    results.append(
                        Evidence(
                            title=review.get("title", claim_review.get("text", "Fact Check")),
                            url=review.get("url", ""),
                            snippet=f"Rating: {review.get('textualRating', 'N/A')} — {claim_review.get('text', '')}",
                            source_score=0.85,
                        )
                    )
            return results
        except Exception as e:
            logger.warning(f"Google Fact Check API failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_search_terms(text: str) -> str:
        """Pull out likely entity names or significant words for Wikipedia."""
        entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        if entities:
            return " ".join(entities[:3])
        words = text.split()[:8]
        return " ".join(w for w in words if len(w) > 3)[:80]

    @staticmethod
    def _score_source(url: str) -> float:
        """Score a source URL based on known credibility database."""
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
            for known_domain, score in SOURCE_CREDIBILITY.items():
                if known_domain in domain:
                    return score
            return 0.5
        except Exception:
            return 0.5
