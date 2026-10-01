"""2.0 Phase 2: evidence store (pgvector), source registry, claims, file storage

Revision ID: b52e81c0d9a3
Revises: 7a1c2e9d4b10
Create Date: 2026-10-01 06:00:00.000000

On PostgreSQL this enables the `vector` extension and builds an HNSW index
(cosine) on chunk embeddings plus a GIN full-text index for keyword search.
SQLite stores embeddings as JSON and gets neither index.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

import truthshield.infra.database

revision: str = 'b52e81c0d9a3'
down_revision: Union[str, None] = '7a1c2e9d4b10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = truthshield.infra.database.GUID
Embedding = truthshield.infra.database.Embedding
JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _timestamps():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    ]


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'sources',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('category', sa.String(length=16), nullable=False),
        sa.Column('credibility', sa.Float(), nullable=False),
        sa.Column('curated', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sources_domain', 'sources', ['domain'], unique=True)
    op.create_index('ix_sources_category', 'sources', ['category'])

    op.create_table(
        'evidence_documents',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('source_id', GUID(), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('url_sha256', sa.String(length=64), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('content_scope', sa.String(length=16), nullable=False),
        sa.Column('content_sha256', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=48), nullable=True),
        sa.Column('language', sa.String(length=8), nullable=True),
        sa.Column('meta', JSONType, nullable=True),
        sa.Column('ingested_by', GUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ingested_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_evidence_documents_source_id', 'evidence_documents', ['source_id'])
    op.create_index('ix_evidence_documents_url_sha256', 'evidence_documents', ['url_sha256'], unique=True)

    op.create_table(
        'evidence_chunks',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('document_id', GUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('char_start', sa.Integer(), nullable=False),
        sa.Column('char_end', sa.Integer(), nullable=False),
        sa.Column('embedding', Embedding(), nullable=True),
        sa.Column('embedding_model', sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(['document_id'], ['evidence_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_evidence_chunks_document_id', 'evidence_chunks', ['document_id'])
    op.create_index('ix_evidence_chunks_model', 'evidence_chunks', ['embedding_model'])
    if _is_postgres():
        op.execute(
            "CREATE INDEX ix_evidence_chunks_embedding_hnsw ON evidence_chunks "
            "USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX ix_evidence_chunks_fts ON evidence_chunks "
            "USING gin (to_tsvector('simple', text))"
        )

    op.create_table(
        'claims',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('investigation_id', GUID(), nullable=False),
        sa.Column('claim_key', sa.String(length=8), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('assessment', sa.String(length=24), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source_count', sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_claims_investigation_id', 'claims', ['investigation_id'])
    op.create_index('ix_claims_assessment', 'claims', ['assessment'])

    with op.batch_alter_table('investigation_inputs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('storage_key', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('investigation_inputs', schema=None) as batch_op:
        batch_op.drop_column('storage_key')
    op.drop_index('ix_claims_assessment', table_name='claims')
    op.drop_index('ix_claims_investigation_id', table_name='claims')
    op.drop_table('claims')
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_fts")
        op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_embedding_hnsw")
    op.drop_index('ix_evidence_chunks_model', table_name='evidence_chunks')
    op.drop_index('ix_evidence_chunks_document_id', table_name='evidence_chunks')
    op.drop_table('evidence_chunks')
    op.drop_index('ix_evidence_documents_url_sha256', table_name='evidence_documents')
    op.drop_index('ix_evidence_documents_source_id', table_name='evidence_documents')
    op.drop_table('evidence_documents')
    op.drop_index('ix_sources_category', table_name='sources')
    op.drop_index('ix_sources_domain', table_name='sources')
    op.drop_table('sources')
