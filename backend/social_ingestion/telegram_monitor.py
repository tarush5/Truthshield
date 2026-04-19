"""
TruthShield — Telegram Monitor
Fetch messages from public Telegram channels using Telethon.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional

from telethon import TelegramClient
from backend.config import get_settings

logger = logging.getLogger(__name__)


class TelegramMonitor:
    def __init__(self):
        settings = get_settings()
        self.api_id = settings.TELEGRAM_API_ID
        self.api_hash = settings.TELEGRAM_API_HASH
        
        # We need a session file for Telethon
        self.session_name = "truthshield_session"
        self.client = None
        
        if self.api_id and self.api_hash:
            try:
                # Initialize but don't start yet. Start is async.
                self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
                logger.info("Telegram Telethon Client initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram client: {e}")
        else:
            logger.warning("Telegram API credentials missing. Telegram Monitor disabled.")

    async def start(self):
        """Async start for the Telethon client."""
        if self.client and not self.client.is_connected():
            await self.client.start()

    async def stop(self):
        """Disconnect the client."""
        if self.client and self.client.is_connected():
            await self.client.disconnect()

    async def fetch_recent_messages(self, channel_entity: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch recent messages from a public channel or group.
        `channel_entity` can be a username like 'IndiaToday' or an invite link.
        """
        if not self.client:
            return []
            
        try:
            await self.start()
            messages = await self.client.get_messages(channel_entity, limit=limit)
            
            results = []
            for msg in messages:
                if msg.message:  # Has text
                    results.append({
                        "id": msg.id,
                        "text": msg.message,
                        "date": msg.date.isoformat(),
                        "views": msg.views or 0,
                        "forwards": msg.forwards or 0,
                        "grouped_id": msg.grouped_id,
                        "has_media": bool(msg.media)
                    })
                    
            return results
        except Exception as e:
            logger.error(f"Error fetching Telegram messages from '{channel_entity}': {e}")
            return []

    async def search_global(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for a term across accessible Telegram messages.
        Note: Telegram API limits global search for users/bots tightly.
        """
        if not self.client:
            return []
            
        try:
            from telethon.tl.functions.messages import SearchGlobalRequest
            from telethon.tl.types import InputMessagesFilterEmpty
            
            await self.start()
            result = await self.client(SearchGlobalRequest(
                q=query,
                filter=InputMessagesFilterEmpty(),
                min_date=None,
                max_date=None,
                offset_rate=0,
                offset_peer=None,
                offset_id=0,
                limit=limit,
                folder_id=None
            ))
            
            results = []
            for msg in result.messages:
                if msg.message:
                    results.append({
                        "id": msg.id,
                        "text": msg.message,
                        "date": msg.date.isoformat() if hasattr(msg, 'date') else None,
                        "views": getattr(msg, 'views', 0) or 0,
                        "forwards": getattr(msg, 'forwards', 0) or 0,
                    })
            return results
            
        except Exception as e:
            logger.error(f"Telegram global search failed for '{query}': {e}")
            return []
            
    def get_sync_social_signals(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Synchronous wrapper to get social signals, normally used in background tasks.
        """
        if not self.client:
            return None
            
        try:
            # Create a new event loop for this sync wrapper if none exists
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            messages = loop.run_until_complete(self.search_global(url, limit=10))
            
            if not messages:
                return None
                
            total_views = sum(m["views"] for m in messages)
            total_forwards = sum(m["forwards"] for m in messages)
            
            engagement = total_views / 10 + total_forwards * 5
            virality_score = min(engagement / 10000.0, 1.0)
            
            return {
                "platform": "telegram",
                "virality_score": round(virality_score, 4),
                "engagement": {
                    "shares": total_forwards,
                    "views": total_views,
                    "mentions": len(messages)
                }
            }
        except Exception as e:
            logger.error(f"Failed to fetch sync Telegram signals: {e}")
            return None
