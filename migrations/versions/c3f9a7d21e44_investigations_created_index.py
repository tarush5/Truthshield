"""Index investigations.created_at for administrator-wide queries

Revision ID: c3f9a7d21e44
Revises: b52e81c0d9a3
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3f9a7d21e44"
down_revision: Union[str, None] = "b52e81c0d9a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_investigations_created", "investigations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_investigations_created", table_name="investigations")
