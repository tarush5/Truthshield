"""
TruthShield — Mastodon Monitor
Track misinformation across the Mastodon fediverse.
Uses the public Mastodon REST API — no authentication required for
public timeline and search on most instances.
"""

import logging
import os
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class MastodonMonitor:
    """Monitor Mastodon instances for misinformation signals."""

    def __init__(self):
        # Default to mastodon.social — the largest instance
        self.instance_url = os.getenv(
            "MASTODON_INSTANCE_URL", "https://mastodon.social"
        )
        self.access_token = os.getenv("MASTODON_ACCESS_TOKEN", "")
        self._headers = {}
        if self.access_token:
            self._headers["Authorization"] = f"Bearer {self.access_token}"

    def search_posts(
        self, query: str, limit: int = 10
    ) -> List[Dict]:
        """
        Search public Mastodon posts (statuses) for a keyword/claim.

        Args:
            query: The claim text to search
            limit: Max number of results

        Returns:
            List of post dicts with text, author, boosts, favourites
        """
        try:
            resp = requests.get(
                f"{self.instance_url}/api/v2/search",
                params={
                    "q": query,
                    "type": "statuses",
                    "limit": min(limit, 40),
                },
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            posts = []
            for status in data.get("statuses", []):
                posts.append(
                    {
                        "id": status["id"],
                        "text": status.get("content", ""),
                        "author": status.get("account", {}).get("username", ""),
                        "author_followers": status.get("account", {}).get(
                            "followers_count", 0
                        ),
                        "boosts": status.get("reblogs_count", 0),
                        "favourites": status.get("favourites_count", 0),
                        "replies": status.get("replies_count", 0),
                        "url": status.get("url", ""),
                        "created_at": status.get("created_at", ""),
                        "platform": "mastodon",
                    }
                )
            logger.info(
                f"Mastodon: found {len(posts)} posts for '{query[:50]}...'"
            )
            return posts

        except Exception as e:
            logger.error(f"Mastodon search failed: {e}")
            return []

    def get_trending_tags(self) -> List[Dict]:
        """Fetch trending hashtags — useful for detecting viral narratives."""
        try:
            resp = requests.get(
                f"{self.instance_url}/api/v1/trends/tags",
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            return [
                {
                    "name": tag.get("name", ""),
                    "url": tag.get("url", ""),
                    "uses_today": int(
                        tag.get("history", [{}])[0].get("uses", 0)
                    )
                    if tag.get("history")
                    else 0,
                    "accounts_today": int(
                        tag.get("history", [{}])[0].get("accounts", 0)
                    )
                    if tag.get("history")
                    else 0,
                }
                for tag in resp.json()
            ]
        except Exception as e:
            logger.error(f"Mastodon trending fetch failed: {e}")
            return []

    def get_virality_signal(self, query: str) -> Dict:
        """
        Aggregate Mastodon virality signals for a claim.
        """
        posts = self.search_posts(query, limit=20)
        if not posts:
            return {"platform": "mastodon", "post_count": 0, "total_boosts": 0}

        total_boosts = sum(p["boosts"] for p in posts)
        total_favs = sum(p["favourites"] for p in posts)
        total_replies = sum(p["replies"] for p in posts)
        max_followers = max(p["author_followers"] for p in posts)

        return {
            "platform": "mastodon",
            "post_count": len(posts),
            "total_boosts": total_boosts,
            "total_favourites": total_favs,
            "total_replies": total_replies,
            "max_author_followers": max_followers,
            "top_post_url": posts[0]["url"] if posts else "",
        }
