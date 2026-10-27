"""resume versions, reminder inbox, application↔resume linkage

P1 closure (plan §13.7): a locked resume snapshot per application, a persisted
reminder inbox, and the columns that connect them.

Revision ID: 20261119_0015
Revises: 20261118_0014
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261119_0015"
down_revision: str | None = "20261118_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("resume_id", sa.String(length=36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("head", sa.JSON(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "locked",
                "applied_optimization",
                "manual",
                name="resumeversionsource",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("optimization_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["optimization_id"], ["resume_optimizations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resume_id", "version_no", name="uq_resume_version_no"),
    )
    op.create_index(op.f("ix_resume_versions_user_id"), "resume_versions", ["user_id"])
    op.create_index(op.f("ix_resume_versions_resume_id"), "resume_versions", ["resume_id"])
    op.create_index(
        op.f("ix_resume_versions_optimization_id"),
        "resume_versions",
        ["optimization_id"],
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=True),
        sa.Column("rule_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "done",
                "dismissed",
                name="reminderstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(op.f("ix_reminders_user_id"), "reminders", ["user_id"])
    op.create_index(op.f("ix_reminders_application_id"), "reminders", ["application_id"])
    op.create_index(op.f("ix_reminders_rule_type"), "reminders", ["rule_type"])
    op.create_index(op.f("ix_reminders_due_at"), "reminders", ["due_at"])
    op.create_index(op.f("ix_reminders_status"), "reminders", ["status"])
    op.create_index(op.f("ix_reminders_dedupe_key"), "reminders", ["dedupe_key"])

    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("resume_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("resume_version_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_applications_resume", "resumes", ["resume_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_foreign_key(
            "fk_applications_resume_version",
            "resume_versions",
            ["resume_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_applications_resume_id", ["resume_id"])
        batch_op.create_index(
            "ix_applications_resume_version_id", ["resume_version_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_index("ix_applications_resume_version_id")
        batch_op.drop_index("ix_applications_resume_id")
        batch_op.drop_constraint("fk_applications_resume_version", type_="foreignkey")
        batch_op.drop_constraint("fk_applications_resume", type_="foreignkey")
        batch_op.drop_column("resume_version_id")
        batch_op.drop_column("resume_id")

    op.drop_index(op.f("ix_reminders_dedupe_key"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_status"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_due_at"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_rule_type"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_application_id"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_user_id"), table_name="reminders")
    op.drop_table("reminders")

    op.drop_index(op.f("ix_resume_versions_optimization_id"), table_name="resume_versions")
    op.drop_index(op.f("ix_resume_versions_resume_id"), table_name="resume_versions")
    op.drop_index(op.f("ix_resume_versions_user_id"), table_name="resume_versions")
    op.drop_table("resume_versions")
