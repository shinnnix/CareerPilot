"""create resume workspace and resume optimization records

Revision ID: 20261102_0011
Revises: 20261019_0010
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0011"
down_revision: str | None = "20261019_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "template",
            sa.Enum(
                "classic",
                "modern",
                "elegant",
                "compact",
                name="resumetemplate",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("font_size", sa.Integer(), nullable=False),
        sa.Column("head", sa.JSON(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("target_job_id", sa.String(length=36), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "upload",
                "text",
                "manual",
                name="resumesource",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("analysis", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["target_job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resumes_user_id"), "resumes", ["user_id"], unique=False)
    op.create_index(op.f("ix_resumes_document_id"), "resumes", ["document_id"], unique=False)
    op.create_index(op.f("ix_resumes_target_job_id"), "resumes", ["target_job_id"], unique=False)
    op.create_index(
        "ix_resumes_user_updated", "resumes", ["user_id", "updated_at"], unique=False
    )

    op.create_table(
        "resume_optimizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("resume_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("jd_document_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "generated",
                "applied",
                "reverted",
                "discarded",
                name="optimizationstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("jd_snapshot", sa.JSON(), nullable=False),
        sa.Column("match_report", sa.JSON(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("base_content_version", sa.Integer(), nullable=False),
        sa.Column("before_apply_snapshot", sa.JSON(), nullable=True),
        sa.Column("applied_suggestion_ids", sa.JSON(), nullable=False),
        sa.Column("generator_version", sa.String(length=50), nullable=False),
        sa.Column("prompt_injection_detected", sa.Boolean(), nullable=False),
        sa.Column("security_flags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["jd_document_id"], ["knowledge_documents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resume_optimizations_user_id"),
        "resume_optimizations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_optimizations_resume_id"),
        "resume_optimizations",
        ["resume_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_optimizations_job_id"),
        "resume_optimizations",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_optimizations_jd_document_id"),
        "resume_optimizations",
        ["jd_document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_optimizations_status"),
        "resume_optimizations",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_optimizations_prompt_injection_detected"),
        "resume_optimizations",
        ["prompt_injection_detected"],
        unique=False,
    )
    op.create_index(
        "ix_resume_optimizations_resume_created",
        "resume_optimizations",
        ["resume_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resume_optimizations_resume_created", table_name="resume_optimizations"
    )
    op.drop_index(
        op.f("ix_resume_optimizations_prompt_injection_detected"),
        table_name="resume_optimizations",
    )
    op.drop_index(op.f("ix_resume_optimizations_status"), table_name="resume_optimizations")
    op.drop_index(
        op.f("ix_resume_optimizations_jd_document_id"), table_name="resume_optimizations"
    )
    op.drop_index(op.f("ix_resume_optimizations_job_id"), table_name="resume_optimizations")
    op.drop_index(op.f("ix_resume_optimizations_resume_id"), table_name="resume_optimizations")
    op.drop_index(op.f("ix_resume_optimizations_user_id"), table_name="resume_optimizations")
    op.drop_table("resume_optimizations")
    op.drop_index("ix_resumes_user_updated", table_name="resumes")
    op.drop_index(op.f("ix_resumes_target_job_id"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_document_id"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_user_id"), table_name="resumes")
    op.drop_table("resumes")
