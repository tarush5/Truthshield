"""
TruthShield — WhatsApp Tipline Monitor
Ingest user-reported misinformation tips from WhatsApp via Twilio webhook.
This module processes incoming WhatsApp messages forwarded to the
TruthShield tipline number and feeds them into the analysis pipeline.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class WhatsAppTiplineMonitor:
    """
    Process misinformation tips received via WhatsApp.

    Works with the existing Twilio webhook in routes.py.
    This monitor maintains a queue of incoming tips and provides
    aggregation methods for the social signal enricher.
    """

    def __init__(self):
        self.tipline_number = os.getenv(
            "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886"
        )
        # In-memory tip queue (use Redis in production)
        self._tip_queue: List[Dict] = []
        self._processed_count = 0

    def ingest_tip(
        self,
        sender: str,
        message_body: str,
        media_url: Optional[str] = None,
        num_media: int = 0,
        timestamp: Optional[str] = None,
    ) -> Dict:
        """
        Ingest a tip from a WhatsApp user.

        Called by the Twilio webhook handler when a message arrives.

        Args:
            sender: WhatsApp number of the sender
            message_body: The text content of the message
            media_url: URL of any attached media
            num_media: Number of media attachments
            timestamp: When the message was received

        Returns:
            Tip record dict
        """
        tip = {
            "id": f"wa_tip_{self._processed_count + 1}",
            "sender_hash": hash(sender) % 10**8,  # Anonymized
            "text": message_body,
            "media_url": media_url,
            "has_media": num_media > 0,
            "media_count": num_media,
            "received_at": timestamp or datetime.utcnow().isoformat(),
            "platform": "whatsapp",
            "status": "pending",
        }

        self._tip_queue.append(tip)
        self._processed_count += 1

        logger.info(
            f"WhatsApp tipline: ingested tip #{tip['id']} "
            f"({len(message_body)} chars, {num_media} media)"
        )
        return tip

    def get_pending_tips(self, limit: int = 10) -> List[Dict]:
        """Get unprocessed tips from the queue."""
        pending = [t for t in self._tip_queue if t["status"] == "pending"]
        return pending[:limit]

    def mark_processed(self, tip_id: str, analysis_id: Optional[str] = None):
        """Mark a tip as processed after analysis."""
        for tip in self._tip_queue:
            if tip["id"] == tip_id:
                tip["status"] = "processed"
                tip["analysis_id"] = analysis_id
                break

    def get_tip_stats(self) -> Dict:
        """Get tipline statistics for the social signal enricher."""
        total = len(self._tip_queue)
        pending = sum(1 for t in self._tip_queue if t["status"] == "pending")
        processed = sum(1 for t in self._tip_queue if t["status"] == "processed")

        return {
            "platform": "whatsapp_tipline",
            "total_tips": total,
            "pending_tips": pending,
            "processed_tips": processed,
            "unique_senders": len(set(t["sender_hash"] for t in self._tip_queue)),
            "media_tips": sum(1 for t in self._tip_queue if t["has_media"]),
        }

    def search_similar_tips(self, query: str, threshold: int = 2) -> List[Dict]:
        """
        Find tips in the queue that mention similar keywords.

        Args:
            query: The claim text to match against
            threshold: Minimum keyword matches required

        Returns:
            List of matching tips
        """
        query_words = set(query.lower().split())
        matching = []

        for tip in self._tip_queue:
            tip_words = set(tip["text"].lower().split())
            overlap = len(query_words & tip_words)
            if overlap >= min(threshold, len(query_words)):
                matching.append(tip)

        return matching

    def get_virality_signal(self, query: str) -> Dict:
        """
        Aggregate WhatsApp tipline virality signals.
        Multiple users reporting the same claim = higher virality.
        """
        similar_tips = self.search_similar_tips(query)
        unique_reporters = len(set(t["sender_hash"] for t in similar_tips))

        return {
            "platform": "whatsapp",
            "matching_tips": len(similar_tips),
            "unique_reporters": unique_reporters,
            "has_media_evidence": any(t["has_media"] for t in similar_tips),
            "earliest_report": (
                min(t["received_at"] for t in similar_tips)
                if similar_tips
                else None
            ),
        }
