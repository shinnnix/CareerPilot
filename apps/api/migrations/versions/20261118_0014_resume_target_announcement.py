"""resume workspace: target announcement + optimization announcement link

Module 1/3 integration: resumes can target a job-catalog announcement (the rows
the 职位信息 page imports) without dropping the legacy ``jobs`` column, and an
optimization run records which announcement it was measured against.

Revision ID: 20261118_0014
Revises: 20261117_0013
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261118_0014"
down_revision: str | None = "20261117_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("resumes") as batch_op:
        batch_op.add_column(sa.Column("target_announcement_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_resumes_target_announcement",
            "job_announcements",
            ["target_announcement_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_resumes_target_announcement_id", ["target_announcement_id"]
        )

    with op.batch_alter_table("resume_optimizations") as batch_op:
        batch_op.add_column(sa.Column("announcement_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_resume_optimizations_announcement",
            "job_announcements",
            ["announcement_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_resume_optimizations_announcement_id", ["announcement_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("resume_optimizations") as batch_op:
        batch_op.drop_index("ix_resume_optimizations_announcement_id")
        batch_op.drop_constraint(
            "fk_resume_optimizations_announcement", type_="foreignkey"
        )
        batch_op.drop_column("announcement_id")

    with op.batch_alter_table("resumes") as batch_op:
        batch_op.drop_index("ix_resumes_target_announcement_id")
        batch_op.drop_constraint("fk_resumes_target_announcement", type_="foreignkey")
        batch_op.drop_column("target_announcement_id")
