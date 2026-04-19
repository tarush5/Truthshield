"""
TruthShield — NewsAPI Searcher
Search for news using NewsAPI (newsapi.org).
"""

import logging
import requests
from typing import List, Dict, Any

from backend.config import get_settings

logger = logging.getLogger(__name__)


class NewsAPISearcher:
    def __init__(self):
        self.api_key = get_settings().NEWSAPI_KEY
        self.base_url = "https://newsapi.org/v2/everything"
        
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for news articles matching the query.
        """
        if not self.api_key:
            logger.warning("NEWSAPI_KEY not configured. Skipping NewsAPI search.")
            return []
            
        try:
            params = {
                "q": query,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": limit,
                "apiKey": self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("status") != "ok":
                return []
                
            results = []
            for article in data.get("articles", []):
                results.append({
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "snippet": article.get("description", "") or article.get("content", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "engine": "NewsAPI"
                })
                
            return results
            
        except Exception as e:
            logger.error(f"NewsAPI search failed for query '{query}': {e}")
            return []
