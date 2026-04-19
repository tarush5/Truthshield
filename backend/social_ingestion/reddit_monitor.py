"""
TruthShield — Reddit Monitor
Fetch viral posts and discussions from Reddit using PRAW.
"""

import logging
from typing import List, Dict, Any, Optional

import praw
from backend.config import get_settings

logger = logging.getLogger(__name__)


class RedditMonitor:
    def __init__(self):
        settings = get_settings()
        self.client_id = settings.REDDIT_CLIENT_ID
        self.client_secret = settings.REDDIT_CLIENT_SECRET
        self.reddit = None
        
        if self.client_id and self.client_secret:
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent="TruthShield/1.0 (by /u/TruthShield)"
                )
                logger.info("Reddit PRAW Client initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Reddit client: {e}")
        else:
            logger.warning("Reddit API keys missing. Reddit Monitor disabled.")

    def search_posts(self, query: str, limit: int = 10, subreddit: str = "all") -> List[Dict[str, Any]]:
        """
        Search for posts matching a query across Reddit or a specific subreddit.
        """
        if not self.reddit:
            return []
            
        try:
            sub = self.reddit.subreddit(subreddit)
            results = []
            
            for post in sub.search(query, limit=limit, sort="comments"):
                results.append({
                    "id": post.id,
                    "title": post.title,
                    "text": getattr(post, 'selftext', ''),
                    "url": post.url,
                    "permalink": f"https://reddit.com{post.permalink}",
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "upvote_ratio": post.upvote_ratio,
                    "created_utc": post.created_utc,
                    "subreddit": post.subreddit.display_name,
                    "author": post.author.name if post.author else "[deleted]"
                })
                
            return results
        except Exception as e:
            logger.error(f"Error searching Reddit for query '{query}': {e}")
            return []

    def get_social_signals(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get aggregated social signals for a specific URL on Reddit.
        """
        posts = self.search_posts(query=f"url:{url}", limit=50)
        
        if not posts:
            return None
            
        total_score = sum(p["score"] for p in posts)
        total_comments = sum(p["num_comments"] for p in posts)
        
        # Calculate a basic virality score
        engagement = total_score + total_comments * 2
        virality_score = min(engagement / 5000.0, 1.0)  # Normalize
        
        return {
            "platform": "reddit",
            "virality_score": round(virality_score, 4),
            "engagement": {
                "shares": len(posts),  # Crossposts/Links
                "likes": total_score,
                "comments": total_comments
            }
        }
