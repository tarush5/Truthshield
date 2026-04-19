"""
TruthShield — Twitter Monitor
Fetch viral claims and social signals from Twitter/X using Tweepy (v2 API).
"""

import logging
from typing import List, Dict, Any, Optional

import tweepy
from backend.config import get_settings

logger = logging.getLogger(__name__)


class TwitterMonitor:
    def __init__(self):
        settings = get_settings()
        self.bearer_token = settings.TWITTER_BEARER_TOKEN
        self.client = None
        
        if self.bearer_token:
            try:
                self.client = tweepy.Client(bearer_token=self.bearer_token)
                logger.info("Twitter v2 Client initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Twitter client: {e}")
        else:
            logger.warning("TWITTER_BEARER_TOKEN not found. Twitter Monitor disabled.")

    def search_recent_tweets(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for recent tweets matching a query.
        Useful for tracking viral claims or finding social signals for a specific URL.
        """
        if not self.client:
            return []
            
        try:
            response = self.client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["created_at", "public_metrics", "author_id", "lang"],
                user_fields=["username", "verified"],
                expansions=["author_id"]
            )
            
            if not response.data:
                return []
                
            users = {u["id"]: u for u in response.includes.get("users", [])}
            
            results = []
            for tweet in response.data:
                user = users.get(tweet.author_id, {})
                metrics = tweet.public_metrics or {}
                
                results.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at,
                    "lang": tweet.lang,
                    "metrics": {
                        "retweet_count": metrics.get("retweet_count", 0),
                        "reply_count": metrics.get("reply_count", 0),
                        "like_count": metrics.get("like_count", 0),
                        "quote_count": metrics.get("quote_count", 0)
                    },
                    "author": {
                        "id": user.get("id"),
                        "username": user.get("username"),
                        "verified": user.get("verified", False)
                    }
                })
                
            return results
        except Exception as e:
            logger.error(f"Error searching tweets for query '{query}': {e}")
            return []

    def get_social_signals(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get aggregated social signals for a specific URL on Twitter.
        """
        tweets = self.search_recent_tweets(query=f"url:\"{url}\"", max_results=100)
        
        if not tweets:
            return None
            
        total_retweets = sum(t["metrics"]["retweet_count"] for t in tweets)
        total_likes = sum(t["metrics"]["like_count"] for t in tweets)
        total_replies = sum(t["metrics"]["reply_count"] for t in tweets)
        
        # Calculate a basic virality score (0.0 to 1.0)
        engagement = total_retweets * 2 + total_likes + total_replies * 1.5
        virality_score = min(engagement / 10000.0, 1.0)  # Normalize to max 1.0 at 10k engagement
        
        return {
            "platform": "twitter",
            "virality_score": round(virality_score, 4),
            "engagement": {
                "shares": total_retweets,
                "likes": total_likes,
                "comments": total_replies,
                "mentions": len(tweets)
            }
        }
