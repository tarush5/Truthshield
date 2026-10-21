"""Investigation reviews: feedback, appeals and reviewer decisions

Additive only: one new table. No existing table is altered.

Revision ID: e6b2d4f8a913
Revises: d81e5b0c7f2a
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import truthshield.infra.database

revision: str = "e6b2d4f8a913"
down_revision: Union[str, None] = "d81e5b0c7f2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = truthshield.infra.database.GUID


def upgrade() -> None:
    op.create_table(
        "investigation_reviews",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("investigation_id", GUID(), nullable=False),
        sa.Column("author_id", GUID(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("user_label", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("system_score", sa.Integer(), nullable=True),
        sa.Column("system_level", sa.String(length=12), nullable=True),
        sa.Column("system_confidence", sa.Float(), nullable=True),
        sa.Column("system_classification", sa.String(length=48), nullable=True),
        sa.Column("system_config_version", sa.String(length=32), nullable=True),
        sa.Column("reviewer_id", GUID(), nullable=True),
        sa.Column("reviewer_label", sa.String(length=16), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigation_reviews_investigation_id", "investigation_reviews", ["investigation_id"])
    op.create_index("ix_investigation_reviews_author_id", "investigation_reviews", ["author_id"])
    op.create_index("ix_investigation_reviews_queue", "investigation_reviews", ["status", "kind", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_investigation_reviews_queue", table_name="investigation_reviews")
    op.drop_index("ix_investigation_reviews_author_id", table_name="investigation_reviews")
    op.drop_index("ix_investigation_reviews_investigation_id", table_name="investigation_reviews")
    op.drop_table("investigation_reviews")
