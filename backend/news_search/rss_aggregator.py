"""
TruthShield — RSS Aggregator
Fetch latest feed entries from known reputable news sources.
"""

import logging
import feedparser
from typing import List, Dict, Any
import concurrent.futures

logger = logging.getLogger(__name__)

# Primary reputable feeds for Indian context
REPUTABLE_FEEDS = [
    "https://www.thehindu.com/news/national/feeder/default.rss",
    "https://feeds.feedburner.com/ndtvnews-india-news",
    "https://indianexpress.com/section/india/feed/",
    "https://www.altnews.in/feed/"
]

class RSSAggregator:
    def __init__(self):
        self.feeds = REPUTABLE_FEEDS

    def _fetch_feed(self, url: str) -> List[Dict[str, Any]]:
        try:
            parsed = feedparser.parse(url)
            articles = []
            for entry in parsed.entries[:5]:  # Get top 5 from each to prevent bloat
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "snippet": entry.get("summary", ""),
                    "source": parsed.feed.get("title", url),
                    "engine": "RSS"
                })
            return articles
        except Exception as e:
            logger.warning(f"Failed to fetch RSS feed {url}: {e}")
            return []

    def fetch_latest_relevant(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch latest articles across all feeds and do a naive keyword filter.
        (RSS is mostly for broad context, actual search relies on CSE/NewsAPI).
        """
        all_articles = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.feeds)) as executor:
            futures = [executor.submit(self._fetch_feed, url) for url in self.feeds]
            for future in futures:
                try:
                    all_articles.extend(future.result(timeout=10))
                except Exception:
                    pass
                    
        # Naive filtering based on query tokens
        query_tokens = set(query.lower().split())
        relevant = []
        
        for article in all_articles:
            title_tokens = set(article["title"].lower().split())
            # If at least one meaningful token matches, consider it relevant
            # In a real system, we'd use embedding similarity here.
            if len(query_tokens.intersection(title_tokens)) > 0:
                relevant.append(article)
                
        return relevant
