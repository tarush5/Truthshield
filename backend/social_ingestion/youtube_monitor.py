"""
TruthShield — YouTube Monitor
Track misinformation in YouTube videos, comments, and community posts
using the YouTube Data API v3.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class YouTubeMonitor:
    """Monitor YouTube for misinformation signals via Data API v3."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY", "")
        if not self.api_key:
            logger.warning("YOUTUBE_API_KEY not set — YouTube monitor disabled")

    def search_videos(
        self,
        query: str,
        max_results: int = 10,
        published_after_hours: int = 48,
    ) -> List[Dict]:
        """
        Search YouTube for videos matching a misinformation claim.

        Args:
            query: Search keywords (the claim text)
            max_results: Number of results (max 50 per page)
            published_after_hours: Only fetch videos from the last N hours

        Returns:
            List of video metadata dicts
        """
        if not self.api_key:
            return []

        after = (datetime.utcnow() - timedelta(hours=published_after_hours)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        try:
            resp = requests.get(
                f"{self.BASE_URL}/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "relevance",
                    "publishedAfter": after,
                    "maxResults": min(max_results, 50),
                    "key": self.api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            videos = []
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                videos.append(
                    {
                        "video_id": item["id"].get("videoId", ""),
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "url": f"https://youtube.com/watch?v={item['id'].get('videoId', '')}",
                        "platform": "youtube",
                    }
                )
            logger.info(f"YouTube: found {len(videos)} videos for '{query[:50]}...'")
            return videos

        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return []

    def get_video_stats(self, video_id: str) -> Optional[Dict]:
        """Fetch view count, like count, comment count for a video."""
        if not self.api_key:
            return None

        try:
            resp = requests.get(
                f"{self.BASE_URL}/videos",
                params={
                    "part": "statistics",
                    "id": video_id,
                    "key": self.api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if items:
                stats = items[0].get("statistics", {})
                return {
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                }
        except Exception as e:
            logger.error(f"YouTube stats fetch failed: {e}")
        return None

    def get_comments(
        self, video_id: str, max_results: int = 20
    ) -> List[Dict]:
        """
        Fetch top-level comments on a video.
        Useful for detecting misinformation narratives in comment threads.
        """
        if not self.api_key:
            return []

        try:
            resp = requests.get(
                f"{self.BASE_URL}/commentThreads",
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "order": "relevance",
                    "maxResults": min(max_results, 100),
                    "key": self.api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()

            comments = []
            for item in resp.json().get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                comments.append(
                    {
                        "author": top.get("authorDisplayName", ""),
                        "text": top.get("textDisplay", ""),
                        "likes": top.get("likeCount", 0),
                        "published_at": top.get("publishedAt", ""),
                    }
                )
            return comments

        except Exception as e:
            logger.error(f"YouTube comments fetch failed: {e}")
            return []

    def get_virality_signal(self, query: str) -> Dict:
        """
        Aggregate YouTube virality signals for a claim.
        Returns total views, engagement, and top video info.
        """
        videos = self.search_videos(query, max_results=5)
        if not videos:
            return {"platform": "youtube", "total_views": 0, "video_count": 0}

        total_views = 0
        total_likes = 0
        total_comments = 0

        for video in videos:
            stats = self.get_video_stats(video["video_id"])
            if stats:
                total_views += stats["views"]
                total_likes += stats["likes"]
                total_comments += stats["comments"]

        return {
            "platform": "youtube",
            "video_count": len(videos),
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "top_video_url": videos[0]["url"] if videos else "",
            "top_video_title": videos[0]["title"] if videos else "",
        }
