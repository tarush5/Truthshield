"""
Public investigation identifiers: TS-YYYY-NNNNNN.

Allocated from a per-year counter row with a single
`UPDATE ... SET value = value + 1 RETURNING value`, which is atomic on
PostgreSQL and on SQLite >= 3.35. There is no read-then-write window for two
concurrent requests to fall into, and no reliance on row counts, which would
reissue a number after a delete.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from truthshield.infra.models import InvestigationCounter

PREFIX = "TS"


def format_public_id(year: int, value: int) -> str:
    return f"{PREFIX}-{year}-{value:06d}"


def next_public_id(session: Session, *, year: int | None = None) -> str:
    year = year or datetime.now(timezone.utc).year

    for _ in range(3):
        value = session.execute(
            update(InvestigationCounter)
            .where(InvestigationCounter.year == year)
            .values(value=InvestigationCounter.value + 1)
            .returning(InvestigationCounter.value)
        ).scalar_one_or_none()
        if value is not None:
            return format_public_id(year, value)

        # First investigation of the year. Two requests can race to create
        # the row; the loser retries the UPDATE, which then succeeds.
        try:
            with session.begin_nested():
                session.add(InvestigationCounter(year=year, value=1))
            return format_public_id(year, 1)
        except IntegrityError:
            continue

    raise RuntimeError("Could not allocate an investigation id.")
