"""
TruthShield — Article Deduplicator
Deduplicate search results across engines using fuzzy string matching.
"""

import logging
from typing import List, Dict, Any

from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)

class ArticleDeduplicator:
    """
    Removes duplicated articles across different search engines.
    If multiple sources report the same AP/Reuters wire, we group them.
    """
    def __init__(self, similarity_threshold: int = 85):
        self.threshold = similarity_threshold

    def deduplicate(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not articles:
            return []

        unique_articles = []

        for current_article in articles:
            # Check if this article matches any existing unique article
            is_duplicate = False
            for unique in unique_articles:
                # Compare URLs
                if current_article.get("url") and current_article["url"] == unique.get("url"):
                    is_duplicate = True
                    break
                
                # Compare Titles using fuzzy ratio
                title1 = current_article.get("title", "")
                title2 = unique.get("title", "")
                
                if title1 and title2:
                    score = fuzz.token_sort_ratio(title1, title2)
                    if score >= self.threshold:
                        is_duplicate = True
                        # Potentially merge sources or engines?
                        if "engines" not in unique:
                            unique["engines"] = [unique.get("engine", "Unknown")]
                        if current_article.get("engine") not in unique["engines"]:
                            unique["engines"].append(current_article.get("engine"))
                        break
                        
            if not is_duplicate:
                current_article["engines"] = [current_article.get("engine", "Unknown")]
                unique_articles.append(current_article)

        num_deduped = len(articles) - len(unique_articles)
        if num_deduped > 0:
            logger.info(f"Deduplicator removed {num_deduped} duplicate articles.")

        return unique_articles
