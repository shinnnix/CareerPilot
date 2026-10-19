"""add agent runs, applications and personalized artifacts

Revision ID: 20260810_0004
Revises: 20260807_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0004"
down_revision: str | None = "20260807_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(9), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),
    )
    for column in ("user_id", "job_id", "status"):
        op.create_index(f"ix_applications_{column}", "applications", [column])

    op.create_table(
        "application_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_events_application_id", "application_events", ["application_id"]
    )
    op.create_index("ix_application_events_user_id", "application_events", ["user_id"])

    op.create_table(
        "match_feedback",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("relevant", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_feedback_user_job"),
    )
    op.create_index("ix_match_feedback_user_id", "match_feedback", ["user_id"])
    op.create_index("ix_match_feedback_job_id", "match_feedback", ["job_id"])

    op.create_table(
        "generated_artifacts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("resume_document_id", sa.String(36), nullable=False),
        sa.Column("artifact_type", sa.String(16), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("citation_valid", sa.Boolean(), nullable=False),
        sa.Column("generator_version", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["resume_document_id"],
            ["knowledge_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "job_id", "resume_document_id", "artifact_type"):
        op.create_index(f"ix_generated_artifacts_{column}", "generated_artifacts", [column])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("intent", sa.String(18), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_node", sa.String(50), nullable=False),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("checkpoint_state", sa.JSON(), nullable=False),
        sa.Column("pending_action", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "intent", "status"):
        op.create_index(f"ix_agent_runs_{column}", "agent_runs", [column])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("node", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_event_sequence"),
    )
    op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])
    op.create_index("ix_agent_events_user_id", "agent_events", ["user_id"])

    op.create_table(
        "tool_receipts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_tool_receipt_key"),
    )
    op.create_index("ix_tool_receipts_user_id", "tool_receipts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_receipts_user_id", table_name="tool_receipts")
    op.drop_table("tool_receipts")
    op.drop_index("ix_agent_events_user_id", table_name="agent_events")
    op.drop_index("ix_agent_events_run_id", table_name="agent_events")
    op.drop_table("agent_events")
    for column in ("status", "intent", "user_id"):
        op.drop_index(f"ix_agent_runs_{column}", table_name="agent_runs")
    op.drop_table("agent_runs")
    for column in ("artifact_type", "resume_document_id", "job_id", "user_id"):
        op.drop_index(f"ix_generated_artifacts_{column}", table_name="generated_artifacts")
    op.drop_table("generated_artifacts")
    op.drop_index("ix_match_feedback_job_id", table_name="match_feedback")
    op.drop_index("ix_match_feedback_user_id", table_name="match_feedback")
    op.drop_table("match_feedback")
    op.drop_index("ix_application_events_user_id", table_name="application_events")
    op.drop_index("ix_application_events_application_id", table_name="application_events")
    op.drop_table("application_events")
    for column in ("status", "job_id", "user_id"):
        op.drop_index(f"ix_applications_{column}", table_name="applications")
    op.drop_table("applications")
