"""
TruthShield — Social Signal Enricher
Aggregates virality and engagement metrics across 7 platforms:
Twitter, Reddit, Telegram, YouTube, Mastodon, Discord, WhatsApp.
"""

import logging
import concurrent.futures
from typing import List, Dict, Any, Optional

from backend.models.schemas import SocialSignal
from backend.social_ingestion.twitter_monitor import TwitterMonitor
from backend.social_ingestion.reddit_monitor import RedditMonitor
from backend.social_ingestion.telegram_monitor import TelegramMonitor
from backend.social_ingestion.youtube_monitor import YouTubeMonitor
from backend.social_ingestion.mastodon_monitor import MastodonMonitor
from backend.social_ingestion.discord_monitor import DiscordMonitor
from backend.social_ingestion.whatsapp_tipline_monitor import WhatsAppTiplineMonitor

logger = logging.getLogger(__name__)


class SocialSignalEnricher:
    """
    Enriches a given URL or query with social signals across all 7 supported platforms.

    Platforms:
        1. Twitter/X      — Filtered Stream via Tweepy
        2. Reddit          — Subreddit monitoring via PRAW
        3. Telegram        — Channel monitoring via Telethon
        4. YouTube         — Video search + comment analysis via Data API v3
        5. Mastodon        — Fediverse search via public REST API
        6. Discord         — Server channel scanning via Bot REST API
        7. WhatsApp        — Tipline ingestion via Twilio webhook
    """

    def __init__(self):
        self.twitter = TwitterMonitor()
        self.reddit = RedditMonitor()
        self.telegram = TelegramMonitor()
        self.youtube = YouTubeMonitor()
        self.mastodon = MastodonMonitor()
        self.discord = DiscordMonitor()
        self.whatsapp = WhatsAppTiplineMonitor()

    def get_signals_for_url(self, url: str) -> List[SocialSignal]:
        """
        Fetch social signals for a specific source URL concurrently
        across all 7 platforms.
        """
        if not url:
            return []

        signals = []

        # Run all API calls concurrently to reduce latency
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                "Twitter": executor.submit(self.twitter.get_social_signals, url),
                "Reddit": executor.submit(self.reddit.get_social_signals, url),
                "Telegram": executor.submit(self.telegram.get_sync_social_signals, url),
                "YouTube": executor.submit(self._youtube_signal, url),
                "Mastodon": executor.submit(self._mastodon_signal, url),
                "Discord": executor.submit(self._discord_signal, url),
                "WhatsApp": executor.submit(self._whatsapp_signal, url),
            }

            for name, future in futures.items():
                try:
                    result = future.result(timeout=15)
                    if result:
                        signals.append(SocialSignal(**result))
                except Exception as e:
                    logger.warning(f"{name} signal fetching failed: {e}")

        logger.info(
            f"Enricher collected signals from {len(signals)}/7 platforms "
            f"for URL: {url[:80]}"
        )
        return signals

    def _youtube_signal(self, query: str) -> Optional[Dict]:
        """Convert YouTube virality data to SocialSignal format."""
        data = self.youtube.get_virality_signal(query)
        if data.get("video_count", 0) == 0:
            return None
        return {
            "platform": "youtube",
            "mentions": data.get("video_count", 0),
            "shares": data.get("total_views", 0),
            "sentiment": 0.0,
            "virality_score": min(data.get("total_views", 0) / 100000, 1.0),
            "engagement": {
                "views": data.get("total_views", 0),
                "likes": data.get("total_likes", 0),
                "comments": data.get("total_comments", 0),
                "top_video": data.get("top_video_url", ""),
            },
        }

    def _mastodon_signal(self, query: str) -> Optional[Dict]:
        """Convert Mastodon data to SocialSignal format."""
        data = self.mastodon.get_virality_signal(query)
        if data.get("post_count", 0) == 0:
            return None
        return {
            "platform": "mastodon",
            "mentions": data.get("post_count", 0),
            "shares": data.get("total_boosts", 0),
            "sentiment": 0.0,
            "virality_score": min(data.get("total_boosts", 0) / 500, 1.0),
            "engagement": {
                "boosts": data.get("total_boosts", 0),
                "favourites": data.get("total_favourites", 0),
                "replies": data.get("total_replies", 0),
                "top_post": data.get("top_post_url", ""),
            },
        }

    def _discord_signal(self, query: str) -> Optional[Dict]:
        """Convert Discord data to SocialSignal format."""
        data = self.discord.get_virality_signal(query)
        if data.get("total_matches", 0) == 0:
            return None
        return {
            "platform": "discord",
            "mentions": data.get("total_matches", 0),
            "shares": data.get("total_reactions", 0),
            "sentiment": 0.0,
            "virality_score": min(data.get("total_matches", 0) / 50, 1.0),
            "engagement": {
                "matches": data.get("total_matches", 0),
                "reactions": data.get("total_reactions", 0),
                "guilds": data.get("guild_count", 0),
            },
        }

    def _whatsapp_signal(self, query: str) -> Optional[Dict]:
        """Convert WhatsApp tipline data to SocialSignal format."""
        data = self.whatsapp.get_virality_signal(query)
        if data.get("matching_tips", 0) == 0:
            return None
        return {
            "platform": "whatsapp",
            "mentions": data.get("matching_tips", 0),
            "shares": data.get("unique_reporters", 0),
            "sentiment": 0.0,
            "virality_score": min(data.get("unique_reporters", 0) / 20, 1.0),
            "engagement": {
                "tips": data.get("matching_tips", 0),
                "unique_reporters": data.get("unique_reporters", 0),
                "has_media": data.get("has_media_evidence", False),
            },
        }

    def assess_crisis_potential(self, signals: List[SocialSignal]) -> bool:
        """
        Determine if content shows signs of rapid viral spread indicative
        of an ongoing crisis or active coordinated disinformation campaign.

        Criteria (any triggers crisis mode):
            1. Any single platform has virality_score > 0.7
            2. Content appears on 3+ platforms with high combined engagement
            3. YouTube views exceed 50K across matched videos
            4. WhatsApp tipline gets 5+ independent reports of same claim
        """
        if not signals:
            return False

        # Criterion 1: Any platform has high virality
        has_high_virality = any(s.virality_score > 0.7 for s in signals)

        # Criterion 2: Wide cross-platform spread
        cross_platform_presence = len(signals) >= 3
        total_shares = sum(s.engagement.get("shares", 0) for s in signals)
        has_high_velocity = total_shares > 1000

        # Criterion 3: YouTube viral breakout
        youtube_signals = [s for s in signals if s.platform == "youtube"]
        youtube_viral = any(
            s.engagement.get("views", 0) > 50000 for s in youtube_signals
        )

        # Criterion 4: Multiple WhatsApp tipline reports
        whatsapp_signals = [s for s in signals if s.platform == "whatsapp"]
        whatsapp_flood = any(
            s.engagement.get("unique_reporters", 0) >= 5 for s in whatsapp_signals
        )

        is_crisis = (
            has_high_virality
            or (cross_platform_presence and has_high_velocity)
            or youtube_viral
            or whatsapp_flood
        )

        if is_crisis:
            platforms = [s.platform for s in signals]
            logger.warning(
                f"CRISIS DETECTED across platforms: {platforms} | "
                f"virality={has_high_virality} cross_platform={cross_platform_presence} "
                f"youtube_viral={youtube_viral} whatsapp_flood={whatsapp_flood}"
            )

        return is_crisis
