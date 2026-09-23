"""
Server-sent events for a running analysis.

Analysis takes one to four seconds, most of it waiting on evidence sources.
The blocking endpoint leaves the caller staring at a spinner for the whole
window with no way to tell a slow run from a stuck one.

SSE rather than WebSocket: the traffic is one-directional, it survives
proxies that mangle upgrades, and the browser reconnects on its own. There is
nothing for the client to send once the request is made.

The event stream is:

    event: stage     {"stage","progress","message","elapsed"}   many
    event: claim     {"text","verdict","confidence",...}        one per claim
    event: complete  the full ReportOut                         once
    event: error     {"detail"}                                 on failure

Every terminal path emits `complete` or `error`, so a client never has to
guess whether the stream ended or the connection died.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from truthshield.api import schemas
from truthshield.api.deps import require_principal
from truthshield.domain.types import ContentType, Language
from truthshield.infra.database import get_session
from truthshield.services.analysis import AnalysisService
from truthshield.services.auth import Principal
from truthshield.settings import get_settings

logger = logging.getLogger(__name__)

stream_router = APIRouter(tags=["analysis"])

# Proxies and load balancers commonly close an idle connection at 30s. A
# comment frame is not an event, so it costs the client nothing to ignore.
HEARTBEAT_SECONDS = 15.0


def _sse(event: str, data: dict) -> str:
    """One SSE frame. `data` must be on a single line, hence the compact dump."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@stream_router.post("/analyze/stream")
async def analyze_stream(
    request: Request,
    payload: schemas.AnalyzeRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
):
    """
    Run an analysis, streaming progress as it happens.

    Text and URL only. File uploads keep the blocking endpoint, since a
    multipart body cannot be sent alongside a streamed response cleanly and
    large media is queued to a worker anyway.
    """
    settings = get_settings()

    if not payload.text and not payload.url:
        raise HTTPException(status_code=400, detail="Provide text or a URL.")

    if payload.text and len(payload.text) > settings.MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Text exceeds the {settings.MAX_TEXT_LENGTH} character limit.",
        )

    url = payload.url
    content_type = ContentType.TEXT
    if url:
        from truthshield.security import BlockedURLError, assert_url_is_public
        try:
            url = assert_url_is_public(url)
        except BlockedURLError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        content_type = ContentType.URL

    report_id = uuid.uuid4().hex
    service = AnalysisService(session)

    async def events() -> AsyncIterator[str]:
        started = time.perf_counter()
        queue: asyncio.Queue = asyncio.Queue()

        async def on_progress(stage: str, progress: float, message: str) -> None:
            await queue.put(("stage", {
                "stage": stage,
                "progress": round(progress, 3),
                "message": message,
                "elapsed": round(time.perf_counter() - started, 2),
            }))

        async def work():
            try:
                report = await service.analyze(
                    report_id=report_id,
                    text=payload.text,
                    url=url,
                    content_type=content_type.value,
                    language=payload.language.value,
                    user_id=str(principal.user_id),
                    org_id=str(principal.org_id) if principal.org_id else None,
                    progress=on_progress,
                )
                # Claims individually, so the UI can render each verdict as it
                # is known rather than waiting for the whole document.
                for claim in report.claims:
                    await queue.put(("claim", schemas.ClaimOut.of(claim).model_dump()))
                await queue.put(("complete", schemas.ReportOut.of(report).model_dump()))
            except Exception as exc:
                logger.error("Streamed analysis %s failed: %s", report_id, exc, exc_info=True)
                # The message is generic on purpose: exception text describes
                # our internals and is of use only to an attacker.
                await queue.put(("error", {"detail": "Analysis failed. Please try again."}))
            finally:
                await queue.put((None, None))

        task = asyncio.create_task(work())

        # Tell the client its report id immediately, so a dropped connection
        # can still be recovered by polling GET /reports/{id}.
        yield _sse("accepted", {"id": report_id})

        try:
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event is None:
                    break
                yield _sse(event, data)

                # A client that navigated away should not keep the analysis —
                # and every source it is waiting on — running.
                if await request.is_disconnected():
                    logger.info("Client disconnected; cancelling analysis %s", report_id)
                    task.cancel()
                    break
        finally:
            if not task.done():
                task.cancel()
            # Surface a crash in the task itself rather than letting asyncio
            # report it as "exception was never retrieved" at shutdown.
            with_suppressed = asyncio.gather(task, return_exceptions=True)
            await with_suppressed

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            # nginx buffers proxied responses by default, which holds every
            # event until the stream closes and defeats the point entirely.
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
