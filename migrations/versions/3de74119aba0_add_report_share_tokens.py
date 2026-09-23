"""add report share tokens

Revision ID: 3de74119aba0
Revises: 4353d98cfdd7
Create Date: 2026-09-23 22:00:19.887453
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

# Custom column types used by the models. Autogenerate renders these by name
# but does not emit their imports, so a generated migration raises NameError
# on its first run without them.
import truthshield.infra.database


revision: str = '3de74119aba0'
down_revision: Union[str, None] = '4353d98cfdd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Opt-in public sharing for a report.

    Unique and nullable: SQL treats NULLs as distinct in a unique index, so
    every unshared report keeps a NULL token without colliding, while a
    minted token is guaranteed to address exactly one report.
    """
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('share_token', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('shared_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_reports_share_token'), ['share_token'], unique=True)



def downgrade() -> None:
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reports_share_token'))
        batch_op.drop_column('shared_at')
        batch_op.drop_column('share_token')

