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

            tracker = AnalysisProgressTracker(websocket)

            # Determine content type
            content_type = ContentType.TEXT
            if url:
                content_type = ContentType.URL

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

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"stage": "error", "message": str(e)})
        except Exception:
            pass
