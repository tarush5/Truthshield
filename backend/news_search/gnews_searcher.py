"""
TruthShield — GNews Searcher
Search for news using the GNews API (free tier: 100 req/day).
Docs: https://gnews.io/docs/v4
"""

import logging
import requests
from typing import List, Dict, Any

from backend.config import get_settings

logger = logging.getLogger(__name__)


class GNewsSearcher:
    """Search for news articles using GNews API."""

    def __init__(self):
        self.api_key = get_settings().GNEWS_API_KEY
        self.base_url = "https://gnews.io/api/v4/search"

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for news articles matching the query.

        Args:
            query: Search query string
            limit: Maximum number of results (API max: 10 on free tier)

        Returns:
            List of article dicts with title, url, snippet, source, engine keys
        """
        if not self.api_key or self.api_key.startswith("your_"):
            logger.debug("GNEWS_API_KEY not configured. Skipping GNews search.")
            return []

        try:
            params = {
                "q": query[:256],  # API query limit
                "token": self.api_key,
                "lang": "en",
                "max": min(limit, 10),
                "sortby": "relevance",
            }

            response = requests.get(self.base_url, params=params, timeout=12)
            response.raise_for_status()

            data = response.json()

            results = []
            for article in data.get("articles", [])[:limit]:
                title = article.get("title", "")
                url = article.get("url", "")
                snippet = article.get("description", "") or article.get("content", "") or ""

                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet[:300],
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "engine": "GNews",
                    })

            logger.info(f"GNews returned {len(results)} results for: {query[:60]}")
            return results

        except requests.exceptions.Timeout:
            logger.warning("GNews request timed out")
            return []
        except Exception as e:
            logger.error(f"GNews search failed for query '{query[:60]}': {e}")
            return []
