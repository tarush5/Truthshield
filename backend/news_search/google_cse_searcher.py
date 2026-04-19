"""
TruthShield — Google Custom Search Engine
Search targeted Indian news sites and global fact-checkers using Google CSE.
"""

import logging
import requests
from typing import List, Dict, Any

from backend.config import get_settings

logger = logging.getLogger(__name__)


class GoogleCSESearcher:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.GOOGLE_CSE_API_KEY
        self.cx = settings.GOOGLE_CSE_ID
        self.base_url = "https://customsearch.googleapis.com/customsearch/v1"
        
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search via Google Programmable Search Engine.
        """
        if not self.api_key or not self.cx:
            logger.warning("Google CSE credentials missing. Skipping CSE search.")
            return []
            
        try:
            params = {
                "q": query,
                "cx": self.cx,
                "key": self.api_key,
                "num": min(limit, 10)  # Google allows max 10 per request
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            results = []
            for item in items:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": item.get("displayLink", "Unknown"),
                    "engine": "GoogleCSE"
                })
                
            return results
            
        except Exception as e:
            logger.error(f"Google CSE search failed for query '{query}': {e}")
            return []
