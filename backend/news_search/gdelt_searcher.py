"""
TruthShield — GDELT Searcher
Search global news using the GDELT Project Doc API.
"""

import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class GdeltSearcher:
    def __init__(self):
        self.base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
        
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search the GDELT 2.0 Doc API for global news coverage.
        """
        try:
            params = {
                "query": query,
                "mode": "artlist",
                "maxrecords": limit,
                "format": "json"
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            # GDELT occasionally returns 200 with invalid JSON if too busy, or 5xx.
            if response.status_code != 200:
                logger.warning(f"GDELT returned status code {response.status_code}")
                return []
                
            try:
                data = response.json()
            except ValueError:
                # GDELT might return plain text errors
                return []
                
            articles = data.get("articles", [])
            
            results = []
            for article in articles:
                results.append({
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "snippet": article.get("seendate", "") + " - " + article.get("domain", ""),
                    "source": article.get("domain", "Unknown"),
                    "engine": "GDELT"
                })
                
            return results
            
        except Exception as e:
            logger.error(f"GDELT search failed for query '{query}': {e}")
            return []
