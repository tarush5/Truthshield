"""Review categories, disputed finding and detector versions

Additive only: three nullable columns on investigation_reviews.

Revision ID: f2c8a1d5b7e4
Revises: e6b2d4f8a913
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f2c8a1d5b7e4"
down_revision: Union[str, None] = "e6b2d4f8a913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("investigation_reviews", sa.Column("category", sa.String(length=32), nullable=True))
    op.add_column("investigation_reviews", sa.Column("finding", sa.String(length=64), nullable=True))
    op.add_column("investigation_reviews", sa.Column("system_versions", JSONType, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("investigation_reviews") as batch:
        batch.drop_column("system_versions")
        batch.drop_column("finding")
        batch.drop_column("category")
