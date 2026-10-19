"""create knowledge documents and chunks

Revision ID: 20260803_0002
Revises: 20260729_0001
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0002"
down_revision: str | None = "20260729_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum(
                "resume",
                "job_description",
                "learning_note",
                "other",
                name="documenttype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "parse_status",
            sa.Enum("parsed", "failed", name="parsestatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("parse_version", sa.String(length=50), nullable=False),
        sa.Column("parse_confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "review_status",
            sa.Enum("pending", "confirmed", name="reviewstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("extracted_data", sa.JSON(), nullable=False),
        sa.Column("index_version", sa.String(length=50), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "content_hash", name="uq_documents_user_hash"),
    )
    op.create_index(
        op.f("ix_knowledge_documents_document_type"),
        "knowledge_documents",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_parse_status"),
        "knowledge_documents",
        ["parse_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_review_status"),
        "knowledge_documents",
        ["review_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_user_id"),
        "knowledge_documents",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section_path", sa.JSON(), nullable=False),
        sa.Column("chunk_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contextualized_content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("estimated_token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("index_version", sa.String(length=50), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "index_version", "position", name="uq_chunk_version_position"
        ),
    )
    op.create_index(
        op.f("ix_document_chunks_chunk_type"),
        "document_chunks",
        ["chunk_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"),
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_index_version"),
        "document_chunks",
        ["index_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_user_id"),
        "document_chunks",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_chunks_user_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_index_version"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_chunk_type"), table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index(op.f("ix_knowledge_documents_user_id"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_review_status"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_parse_status"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_document_type"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
