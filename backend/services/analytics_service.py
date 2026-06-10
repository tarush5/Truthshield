"""
TruthShield — Analytics and Threat Telemetry Service
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.models.db import Report

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service to compute threat intelligence feeds, trends, and aggregate metrics."""

    @staticmethod
    def get_workspace_stats(db: Session, org_id: uuid.UUID) -> Dict[str, Any]:
        """Aggregate analysis statistics for a given workspace."""
        total_scans = db.query(Report).filter(Report.org_id == org_id).count()
        fake_news = db.query(Report).filter(
            Report.org_id == org_id,
            Report.verdict == "FALSE"
        ).count()

        deepfakes = db.query(Report).filter(
            Report.org_id == org_id,
            Report.content_type == "image",
            Report.verdict == "FALSE"
        ).count()

        voice_clones = db.query(Report).filter(
            Report.org_id == org_id,
            Report.content_type == "audio",
            Report.verdict == "FALSE"
        ).count()

        # Query weekly scan trend (last 7 days)
        today = datetime.now(timezone.utc).date()
        weekly_trend = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            start_dt = datetime.combine(d, datetime.min.time())
            end_dt = datetime.combine(d, datetime.max.time())
            
            count = db.query(Report).filter(
                Report.org_id == org_id,
                Report.created_at >= start_dt,
                Report.created_at <= end_dt
            ).count()
            
            weekly_trend.append({
                "day": d.strftime("%a"),
                "scans": count
            })

        # Query recent scans
        recent_reports = db.query(Report).filter(
            Report.org_id == org_id
        ).order_by(Report.created_at.desc()).limit(10).all()

        recent_scans = [
            {
                "id": r.id,
                "content_type": r.content_type,
                "text": (r.input_text or "")[:60] + "..." if r.input_text else "Media File/URL",
                "verdict": r.verdict,
                "confidence": int(r.confidence * 100),
                "date": r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in recent_reports
        ]

        return {
            "total_scans": total_scans,
            "fake_news": fake_news,
            "deepfakes": deepfakes,
            "voice_clones": voice_clones,
            "weekly_trend": weekly_trend,
            "recent_scans": recent_scans,
        }

    @staticmethod
    def get_threat_vectors(db: Session, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Generate threat intelligence geolocations for flagged misinformation.
        Returns coordinates and telemetry for visual SaaS threat maps.
        """
        flagged_reports = db.query(Report).filter(
            Report.verdict == "FALSE"
        ).order_by(Report.created_at.desc()).limit(limit).all()

        # Standard mock coordinates for various global coordinates
        coordinates = [
            {"city": "New York", "lat": 40.7128, "lng": -74.0060},
            {"city": "London", "lat": 51.5074, "lng": -0.1278},
            {"city": "Mumbai", "lat": 19.0760, "lng": 72.8777},
            {"city": "Tokyo", "lat": 35.6762, "lng": 139.6503},
            {"city": "Sydney", "lat": -33.8688, "lng": 151.2093},
        ]

        threats = []
        for idx, r in enumerate(flagged_reports):
            coord = coordinates[idx % len(coordinates)]
            threats.append({
                "id": r.id,
                "claim": (r.input_text or "")[:50] + "..." if r.input_text else "Deepfake Media Vector",
                "content_type": r.content_type,
                "severity": "HIGH" if r.confidence > 0.8 else "MEDIUM",
                "lat": coord["lat"],
                "lng": coord["lng"],
                "city": coord["city"],
                "timestamp": r.created_at.isoformat()
            })

        # Fallback default values if no data exists yet
        if not threats:
            threats = [
                {
                    "id": "1",
                    "claim": "Deepfake video of prime minister circulating on WhatsApp",
                    "content_type": "video",
                    "severity": "HIGH",
                    "lat": 19.0760,
                    "lng": 72.8777,
                    "city": "Mumbai",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                {
                    "id": "2",
                    "claim": "Fake audio clone claiming bank runs in NYC",
                    "content_type": "audio",
                    "severity": "HIGH",
                    "lat": 40.7128,
                    "lng": -74.0060,
                    "city": "New York",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                {
                    "id": "3",
                    "claim": "Misleading news article regarding tax law changes",
                    "content_type": "text",
                    "severity": "MEDIUM",
                    "lat": 51.5074,
                    "lng": -0.1278,
                    "city": "London",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ]

        return threats
