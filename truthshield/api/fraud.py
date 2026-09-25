"""
Fraud analysis endpoints.

Separate router from `/analyze`, which does fact-checking. The two answer
different questions -- is this claim true, versus is this artefact hostile --
and merging them behind one path would make the response shape depend on
what the input happened to look like.

`/fraud/analyze` is the universal entry point: submit anything, the
classifier decides what it is, and every applicable detector runs. The
dedicated scanners in the UI call the same endpoint with `only`, so there is
one code path and no chance of the specialised view disagreeing with the
general one.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from truthshield.api.deps import require_principal
from truthshield.services.auth import Principal
from truthshield.settings import get_settings

logger = logging.getLogger(__name__)

fraud_router = APIRouter(prefix="/fraud", tags=["fraud"])


class FraudAnalyzeRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Text, URL, message or email to examine.")
    hint: str = Field("", description="Known input kind, if the caller already knows it.")
    only: Optional[List[str]] = Field(
        None, description="Restrict to named detectors, as used by the dedicated scanners.",
    )


@fraud_router.get("/detectors")
def list_detectors():
    """
    What this deployment can detect.

    Served rather than hard-coded in the client so the UI cannot offer a
    scanner that the backend does not actually have registered.
    """
    from truthshield.fraud import catalogue

    return {"detectors": catalogue()}


@fraud_router.get("/safety")
def safety_centre(category: Optional[str] = Query(None, description="One category, or all.")):
    """
    What a reader should actually do next.

    Public: safety advice is useful to someone who has not signed up, and
    there is nothing here worth protecting. Served rather than hard-coded in
    the client so the advice shown always matches the categories the backend
    can actually produce.
    """
    from truthshield.fraud.contract import FraudCategory
    from truthshield.fraud.guidance import catalogue, for_category

    if category:
        try:
            chosen = FraudCategory(category.upper())
        except ValueError:
            raise HTTPException(status_code=404, detail="Unknown category.")
        return {"category": chosen.value, **for_category(chosen).as_dict()}

    return {"categories": catalogue()}


@fraud_router.post("/analyze")
def analyze_for_fraud(
    payload: FraudAnalyzeRequest = Body(...),
    principal: Principal = Depends(require_principal),
):
    """
    Examine a submission for fraud and scam signals.

    Returns a combined risk score with every contributing finding attached,
    plus `coverage` -- which detectors ran, which did not apply, and which
    failed. A low score from one detector and a low score from six are
    different statements, and the caller is entitled to tell them apart.
    """
    from truthshield.fraud import analyze

    settings = get_settings()
    if len(payload.content) > settings.MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Submission exceeds {settings.MAX_TEXT_LENGTH} characters.",
        )

    result = analyze(payload.content, hint=payload.hint, only=payload.only)

    # Never echoed back. The submission routinely contains exactly the
    # personal data the reader was being phished for, and storing or
    # returning it would reproduce the harm being reported.
    logger.info(
        "Fraud analysis by %s: %s %s (%d findings)",
        principal.user_id,
        result["risk_level"],
        result["category"],
        len(result["findings"]),
    )
    return result
