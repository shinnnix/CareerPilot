"""create jobs table

Revision ID: 20260729_0001
Revises:
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("city", sa.String(length=50), nullable=True),
        sa.Column(
            "employment_type",
            sa.Enum(
                "internship", "full_time", "part_time", name="employmenttype", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column(
            "remote_type",
            sa.Enum("onsite", "hybrid", "remote", name="remotetype", native_enum=False),
            nullable=False,
        ),
        sa.Column("salary_min", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("internship_days_per_week", sa.Integer(), nullable=True),
        sa.Column("internship_months", sa.Integer(), nullable=True),
        sa.Column("required_skills", sa.JSON(), nullable=False),
        sa.Column("preferred_skills", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="jobstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_city"), "jobs", ["city"], unique=False)
    op.create_index(op.f("ix_jobs_company_name"), "jobs", ["company_name"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index(op.f("ix_jobs_title"), "jobs", ["title"], unique=False)
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_user_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_title"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_company_name"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_city"), table_name="jobs")
    op.drop_table("jobs")
