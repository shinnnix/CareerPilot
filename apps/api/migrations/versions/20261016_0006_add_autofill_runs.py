"""Add reviewable application autofill plans.

Revision ID: 20261016_0009
Revises: 20260908_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0009"
down_revision: str | None = "20260908_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "autofill_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("resume_document_id", sa.String(36), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("ready_count", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["resume_document_id"], ["knowledge_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_autofill_runs_user_id", "autofill_runs", ["user_id"])
    op.create_index("ix_autofill_runs_application_id", "autofill_runs", ["application_id"])
    op.create_index("ix_autofill_runs_resume_document_id", "autofill_runs", ["resume_document_id"])


def downgrade() -> None:
    op.drop_index("ix_autofill_runs_resume_document_id", table_name="autofill_runs")
    op.drop_index("ix_autofill_runs_application_id", table_name="autofill_runs")
    op.drop_index("ix_autofill_runs_user_id", table_name="autofill_runs")
    op.drop_table("autofill_runs")
