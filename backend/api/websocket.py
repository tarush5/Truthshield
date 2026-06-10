"""
TruthShield — WebSocket Handler
Real-time streaming analysis via WebSocket using the Decision Pipeline.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.models.schemas import ContentType, Language, WSProgressMessage

logger = logging.getLogger(__name__)
ws_router = APIRouter()


class AnalysisProgressTracker:
    """Track and broadcast analysis progress via WebSocket."""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket

    async def send_progress(
        self, stage: str, progress: float, message: str = "", partial_result: dict = None
    ):
        """Send progress update to client."""
        msg = WSProgressMessage(
            stage=stage,
            progress=progress,
            message=message,
            partial_result=partial_result,
        )
        await self.ws.send_json(msg.model_dump())


@ws_router.websocket("/ws/analyze")
async def websocket_analyze(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming analysis.

    Client sends: {"text": "...", "lang": "en"} or {"url": "..."}
    Server streams: WSProgressMessage updates from each pipeline stage.

    The DecisionPipeline drives all analysis; progress is streamed
    via the progress_callback mechanism.
    """
    await websocket.accept()
    logger.info("WebSocket connection established")

    try:
        while True:
            # Receive analysis request
            data = await websocket.receive_json()
            text = data.get("text")
            url = data.get("url")
            lang = data.get("lang", "en")
            token = data.get("token")
            org_id = data.get("org_id")

            tracker = AnalysisProgressTracker(websocket)

            # Determine content type
            content_type = ContentType.TEXT
            if url:
                content_type = ContentType.URL

            # Resolve user from token
            user_uuid = None
            if token:
                from jose import jwt
                from backend.config import get_settings
                settings = get_settings()
                try:
                    payload = jwt.decode(
                        token,
                        settings.JWT_SECRET_KEY,
                        algorithms=[settings.JWT_ALGORITHM],
                        options={"verify_aud": False},
                    )
                    user_id = payload.get("sub")
                    if user_id:
                        import uuid
                        user_uuid = uuid.UUID(user_id)
                except Exception:
                    # Dev mode fallback
                    if settings.APP_ENV == "development" and settings.JWT_SECRET_KEY == "change-me-in-production":
                        try:
                            unverified_payload = jwt.get_unverified_claims(token)
                            user_id = unverified_payload.get("sub")
                            if user_id:
                                import uuid
                                user_uuid = uuid.UUID(user_id)
                        except Exception:
                            pass

            # Run the full pipeline with streaming progress
            from backend.api.routes import run_analysis_pipeline

            report = await run_analysis_pipeline(
                text=text,
                file_path=None,
                url=url,
                content_type=content_type,
                lang=lang,
                progress_callback=tracker.send_progress,
            )

            # Save report to Database
            if user_uuid:
                from backend.models.db import SessionLocal, Report as ReportDB, EvidenceDB
                db = SessionLocal()
                try:
                    org_uuid = None
                    if org_id:
                        try:
                            import uuid
                            org_uuid = uuid.UUID(org_id)
                        except ValueError:
                            pass

                    db_report = ReportDB(
                        id=report.id,
                        user_id=user_uuid,
                        org_id=org_uuid,
                        content_type=report.content_type.value,
                        input_text=report.original_text,
                        verdict=report.credibility.verdict,
                        confidence=report.credibility.trust_score / 100.0,
                    )
                    db.add(db_report)
                    
                    # Save evidence
                    if report.claims:
                        for claim_verdict in report.claims:
                            for ev in claim_verdict.evidence:
                                db_ev = EvidenceDB(
                                    report_id=report.id,
                                    source_url=ev.url,
                                    source_name=ev.title,
                                    credibility_score=ev.source_score,
                                )
                                db.add(db_ev)
                    db.commit()
                    logger.info(f"WS: Report {report.id} saved to DB for user {user_uuid}, org {org_uuid}")

                    # Log audit action
                    if org_uuid:
                        from backend.services.auth_service import AuthService
                        AuthService.log_action(
                            db,
                            org_uuid,
                            user_uuid,
                            "analyze_created",
                            {"report_id": report.id, "verdict": report.credibility.verdict, "content_type": content_type.value}
                        )
                except Exception as db_err:
                    logger.warning(f"WS: Failed to persist report to DB: {db_err}")
                finally:
                    db.close()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"stage": "error", "message": str(e)})
        except Exception:
            pass
