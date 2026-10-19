"""add pgvector embeddings and full text indexes

Revision ID: 20260807_0003
Revises: 20260803_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260807_0003"
down_revision: str | None = "20260803_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", "model_name", name="uq_chunk_embedding_model"),
    )
    op.create_index(
        op.f("ix_chunk_embeddings_chunk_id"),
        "chunk_embeddings",
        ["chunk_id"],
    )
    op.create_index(
        op.f("ix_chunk_embeddings_model_name"),
        "chunk_embeddings",
        ["model_name"],
    )
    op.create_index(
        op.f("ix_chunk_embeddings_user_id"),
        "chunk_embeddings",
        ["user_id"],
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_fts ON document_chunks "
        "USING gin (to_tsvector('simple', contextualized_content))"
    )
    op.execute(
        "CREATE INDEX ix_chunk_embeddings_hnsw ON chunk_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunk_embeddings_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_fts")
    op.drop_index(op.f("ix_chunk_embeddings_user_id"), table_name="chunk_embeddings")
    op.drop_index(op.f("ix_chunk_embeddings_model_name"), table_name="chunk_embeddings")
    op.drop_index(op.f("ix_chunk_embeddings_chunk_id"), table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
