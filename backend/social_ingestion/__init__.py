"""
TruthShield — Social Media Ingestion
Multi-platform monitoring: Twitter, Reddit, Telegram, YouTube,
Mastodon, Discord, and WhatsApp Tipline.
"""

from backend.social_ingestion.twitter_monitor import TwitterMonitor
from backend.social_ingestion.reddit_monitor import RedditMonitor
from backend.social_ingestion.telegram_monitor import TelegramMonitor
from backend.social_ingestion.youtube_monitor import YouTubeMonitor
from backend.social_ingestion.mastodon_monitor import MastodonMonitor
from backend.social_ingestion.discord_monitor import DiscordMonitor
from backend.social_ingestion.whatsapp_tipline_monitor import WhatsAppTiplineMonitor
from backend.social_ingestion.social_signal_enricher import SocialSignalEnricher

__all__ = [
    "TwitterMonitor",
    "RedditMonitor",
    "TelegramMonitor",
    "YouTubeMonitor",
    "MastodonMonitor",
    "DiscordMonitor",
    "WhatsAppTiplineMonitor",
    "SocialSignalEnricher",
]
