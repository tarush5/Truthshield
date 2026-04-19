"""
TruthShield — Discord Monitor
Track misinformation narratives across Discord servers
using Discord.py bot integration.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)

try:
    import discord
except ImportError:
    discord = None
    logger.warning("discord.py not installed — Discord monitor unavailable")


class DiscordMonitor:
    """
    Monitor Discord servers for misinformation signals.

    Requires a Discord bot token with MESSAGE_CONTENT intent enabled.
    The bot must be invited to target servers with read permissions.
    """

    # Channels commonly used to spread misinformation
    WATCHLIST_CHANNEL_KEYWORDS = [
        "news", "politics", "breaking", "viral", "facts",
        "india", "alert", "general", "debate", "media",
    ]

    def __init__(self):
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN", "")
        self.guild_ids = [
            gid.strip()
            for gid in os.getenv("DISCORD_GUILD_IDS", "").split(",")
            if gid.strip()
        ]
        if not self.bot_token:
            logger.warning("DISCORD_BOT_TOKEN not set — Discord monitor disabled")

    def search_messages_rest(
        self,
        query: str,
        channel_id: str,
        limit: int = 25,
    ) -> List[Dict]:
        """
        Search recent messages in a channel via REST API.
        Falls back to fetching recent messages and filtering locally
        since Discord's search API requires special permissions.

        Args:
            query: Keywords to search for
            channel_id: The Discord channel ID to search
            limit: Max messages to scan

        Returns:
            List of matching message dicts
        """
        if not self.bot_token:
            return []

        import requests

        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.get(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                params={"limit": min(limit, 100)},
                timeout=10,
            )
            resp.raise_for_status()
            messages = resp.json()

            query_lower = query.lower()
            query_words = set(query_lower.split())

            matching = []
            for msg in messages:
                content = msg.get("content", "").lower()
                # Match if at least 2 query words appear in the message
                word_hits = sum(1 for w in query_words if w in content)
                if word_hits >= min(2, len(query_words)):
                    matching.append(
                        {
                            "id": msg["id"],
                            "text": msg.get("content", ""),
                            "author": msg.get("author", {}).get("username", ""),
                            "timestamp": msg.get("timestamp", ""),
                            "attachments": len(msg.get("attachments", [])),
                            "reactions": sum(
                                r.get("count", 0)
                                for r in msg.get("reactions", [])
                            ),
                            "platform": "discord",
                            "channel_id": channel_id,
                        }
                    )

            logger.info(
                f"Discord: found {len(matching)} matching messages "
                f"in channel {channel_id}"
            )
            return matching

        except Exception as e:
            logger.error(f"Discord message fetch failed: {e}")
            return []

    def get_guild_channels(self, guild_id: str) -> List[Dict]:
        """List text channels in a guild, prioritizing news-related ones."""
        if not self.bot_token:
            return []

        import requests

        headers = {"Authorization": f"Bot {self.bot_token}"}

        try:
            resp = requests.get(
                f"https://discord.com/api/v10/guilds/{guild_id}/channels",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            channels = resp.json()

            text_channels = []
            for ch in channels:
                if ch.get("type") == 0:  # GUILD_TEXT
                    is_priority = any(
                        kw in ch.get("name", "").lower()
                        for kw in self.WATCHLIST_CHANNEL_KEYWORDS
                    )
                    text_channels.append(
                        {
                            "id": ch["id"],
                            "name": ch.get("name", ""),
                            "priority": is_priority,
                        }
                    )

            # Sort priority channels first
            text_channels.sort(key=lambda c: c["priority"], reverse=True)
            return text_channels

        except Exception as e:
            logger.error(f"Discord guild channels fetch failed: {e}")
            return []

    def get_virality_signal(self, query: str) -> Dict:
        """
        Aggregate Discord virality signals across monitored guilds.
        """
        total_matches = 0
        total_reactions = 0
        all_messages = []

        for guild_id in self.guild_ids:
            channels = self.get_guild_channels(guild_id)
            # Only scan top 3 priority channels per guild
            for ch in channels[:3]:
                msgs = self.search_messages_rest(query, ch["id"], limit=25)
                all_messages.extend(msgs)
                total_matches += len(msgs)
                total_reactions += sum(m["reactions"] for m in msgs)

        return {
            "platform": "discord",
            "guild_count": len(self.guild_ids),
            "total_matches": total_matches,
            "total_reactions": total_reactions,
            "sample_messages": [m["text"][:200] for m in all_messages[:3]],
        }
