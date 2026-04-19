"""
TruthShield — NewsData.io Searcher
Search for news using the NewsData.io API (free tier: 200 req/day).
Docs: https://newsdata.io/documentation
"""

import logging
import requests
from typing import List, Dict, Any

from backend.config import get_settings

logger = logging.getLogger(__name__)


class NewsDataSearcher:
    """Search for news articles using NewsData.io API."""

    def __init__(self):
        self.api_key = get_settings().NEWSDATA_API_KEY
        self.base_url = "https://newsdata.io/api/1/latest"

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for news articles matching the query.

        Args:
            query: Search query string
            limit: Maximum number of results (API returns up to 10 per call)

        Returns:
            List of article dicts with title, url, snippet, source, engine keys
        """
        if not self.api_key or self.api_key.startswith("your_"):
            logger.debug("NEWSDATA_API_KEY not configured. Skipping NewsData.io search.")
            return []

        try:
            params = {
                "apikey": self.api_key,
                "q": query[:512],  # API query limit
                "language": "en",
                "size": min(limit, 10),
            }

            response = requests.get(self.base_url, params=params, timeout=12)
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "success":
                logger.warning(f"NewsData.io returned status: {data.get('status')}")
                return []

            results = []
            for article in data.get("results", [])[:limit]:
                title = article.get("title", "")
                url = article.get("link", "")
                snippet = (
                    article.get("description", "")
                    or article.get("content", "")
                    or ""
                )

                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet[:300],
                        "source": article.get("source_name", "Unknown"),
                        "engine": "NewsData.io",
                    })

            logger.info(f"NewsData.io returned {len(results)} results for: {query[:60]}")
            return results

        except requests.exceptions.Timeout:
            logger.warning("NewsData.io request timed out")
            return []
        except Exception as e:
            logger.error(f"NewsData.io search failed for query '{query[:60]}': {e}")
            return []
