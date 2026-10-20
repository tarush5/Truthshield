"""Covering indexes for the dashboard

Replaces ix_investigations_created with a covering index (same leading
column), and adds a covering index on risk_factors for the top-factor count.
`id` is included so the risk-factor join never reads the investigation rows.

Revision ID: d81e5b0c7f2a
Revises: c3f9a7d21e44
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d81e5b0c7f2a"
down_revision: Union[str, None] = "c3f9a7d21e44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_investigations_created", table_name="investigations")
    op.create_index(
        "ix_investigations_dashboard", "investigations",
        ["created_at", "status", "risk_level", "risk_score", "type", "classification", "processing_ms", "id"],
    )
    op.create_index("ix_risk_factors_dashboard", "risk_factors", ["investigation_id", "points", "code", "title"])


def downgrade() -> None:
    op.drop_index("ix_risk_factors_dashboard", table_name="risk_factors")
    op.drop_index("ix_investigations_dashboard", table_name="investigations")
    op.create_index("ix_investigations_created", "investigations", ["created_at"])
