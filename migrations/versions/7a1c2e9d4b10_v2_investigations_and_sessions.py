"""2.0: investigations, refresh tokens, system roles

Revision ID: 7a1c2e9d4b10
Revises: 3de74119aba0
Create Date: 2026-10-01 04:00:00.000000

Additive only. No 1.x table is dropped or rewritten: reports, evidence and
feedback keep working, and every existing user becomes role USER.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

import truthshield.infra.database

revision: str = '7a1c2e9d4b10'
down_revision: Union[str, None] = '3de74119aba0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = truthshield.infra.database.GUID
JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _timestamps():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    # ── Users: platform role ─────────────────────────────────
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=16), nullable=False, server_default='USER'))
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))

    # ── Refresh tokens ───────────────────────────────────────
    op.create_table(
        'refresh_tokens',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('family_id', GUID(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replaced_by_id', GUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index('ix_refresh_tokens_family_id', 'refresh_tokens', ['family_id'])

    # ── Investigations ───────────────────────────────────────
    op.create_table(
        'investigations',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('public_id', sa.String(length=20), nullable=False),
        sa.Column('user_id', GUID(), nullable=True),
        sa.Column('org_id', GUID(), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('current_stage', sa.String(length=32), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.String(length=12), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('confidence_band', sa.String(length=12), nullable=True),
        sa.Column('classification', sa.String(length=48), nullable=True),
        sa.Column('language', sa.String(length=8), nullable=True),
        sa.Column('input_sha256', sa.String(length=64), nullable=False),
        sa.Column('excerpt', sa.String(length=240), nullable=True),
        sa.Column('result', JSONType, nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('processing_ms', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_investigations_public_id', 'investigations', ['public_id'], unique=True)
    op.create_index('ix_investigations_user_id', 'investigations', ['user_id'])
    op.create_index('ix_investigations_org_id', 'investigations', ['org_id'])
    op.create_index('ix_investigations_type', 'investigations', ['type'])
    op.create_index('ix_investigations_status', 'investigations', ['status'])
    op.create_index('ix_investigations_risk_level', 'investigations', ['risk_level'])
    op.create_index('ix_investigations_input_sha256', 'investigations', ['input_sha256'])
    op.create_index('ix_investigations_user_created', 'investigations', ['user_id', 'created_at'])

    op.create_table(
        'investigation_inputs',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('investigation_id', GUID(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('redacted_content', sa.Text(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('meta', JSONType, nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_investigation_inputs_investigation_id', 'investigation_inputs', ['investigation_id'])
    op.create_index('ix_investigation_inputs_sha256', 'investigation_inputs', ['sha256'])

    op.create_table(
        'investigation_events',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('investigation_id', GUID(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('stage', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('service', sa.String(length=48), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('detail', JSONType, nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_investigation_events_investigation_id', 'investigation_events', ['investigation_id'])

    op.create_table(
        'risk_factors',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('investigation_id', GUID(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('family', sa.String(length=24), nullable=False),
        sa.Column('severity', sa.String(length=12), nullable=False),
        sa.Column('provenance', sa.String(length=24), nullable=False),
        sa.Column('engine', sa.String(length=48), nullable=False),
        sa.Column('engine_version', sa.String(length=24), nullable=False),
        sa.Column('points', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_risk_factors_investigation_id', 'risk_factors', ['investigation_id'])
    op.create_index('ix_risk_factors_code', 'risk_factors', ['code'])

    op.create_table(
        'model_predictions',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('investigation_id', GUID(), nullable=False),
        sa.Column('model_name', sa.String(length=80), nullable=False),
        sa.Column('model_version', sa.String(length=24), nullable=False),
        sa.Column('model_kind', sa.String(length=16), nullable=False),
        sa.Column('task', sa.String(length=48), nullable=False),
        sa.Column('input_sha256', sa.String(length=64), nullable=False),
        sa.Column('prediction', JSONType, nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_model_predictions_investigation_id', 'model_predictions', ['investigation_id'])
    op.create_index('ix_model_predictions_model_name', 'model_predictions', ['model_name'])

    op.create_table(
        'investigation_counters',
        sa.Column('year', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('year'),
    )


def downgrade() -> None:
    op.drop_table('investigation_counters')
    op.drop_index('ix_model_predictions_model_name', table_name='model_predictions')
    op.drop_index('ix_model_predictions_investigation_id', table_name='model_predictions')
    op.drop_table('model_predictions')
    op.drop_index('ix_risk_factors_code', table_name='risk_factors')
    op.drop_index('ix_risk_factors_investigation_id', table_name='risk_factors')
    op.drop_table('risk_factors')
    op.drop_index('ix_investigation_events_investigation_id', table_name='investigation_events')
    op.drop_table('investigation_events')
    op.drop_index('ix_investigation_inputs_sha256', table_name='investigation_inputs')
    op.drop_index('ix_investigation_inputs_investigation_id', table_name='investigation_inputs')
    op.drop_table('investigation_inputs')
    for name in ('user_created', 'input_sha256', 'risk_level', 'status', 'type', 'org_id', 'user_id', 'public_id'):
        op.drop_index(f'ix_investigations_{name}', table_name='investigations')
    op.drop_table('investigations')
    op.drop_index('ix_refresh_tokens_family_id', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_token_hash', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('last_login_at')
        batch_op.drop_column('role')
