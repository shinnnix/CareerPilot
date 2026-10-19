"""add users and document prompt-injection quarantine

Revision ID: 20260825_0005
Revises: 20260810_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0005"
down_revision: str | None = "20260810_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.add_column(
        "knowledge_documents",
        sa.Column(
            "prompt_injection_detected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "security_flags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.create_index(
        "ix_knowledge_documents_prompt_injection_detected",
        "knowledge_documents",
        ["prompt_injection_detected"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_documents_prompt_injection_detected",
        table_name="knowledge_documents",
    )
    op.drop_column("knowledge_documents", "security_flags")
    op.drop_column("knowledge_documents", "prompt_injection_detected")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
