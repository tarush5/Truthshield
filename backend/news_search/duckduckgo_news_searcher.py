"""
TruthShield — DuckDuckGo News Searcher
Fast, reliable news search using the ddgs library.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class DuckDuckGoNewsSearcher:
    """Search for news articles using DuckDuckGo via ddgs."""

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for news articles matching the query.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of article dicts with title, url, snippet, source, engine keys
        """
        try:
            from ddgs import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=limit):
                    title = r.get("title", "")
                    url = r.get("url", "")
                    snippet = r.get("body", "")
                    source = r.get("source", "DDG News")

                    if title and url:
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet[:300] if snippet else "",
                            "source": source,
                            "engine": "DuckDuckGo News",
                        })

            logger.info(f"DDG News returned {len(results)} results for: {query[:60]}")
            return results

        except Exception as e:
            logger.warning(f"DDG News search failed: {e}")
            return []
