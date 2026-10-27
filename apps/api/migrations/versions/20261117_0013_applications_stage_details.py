"""application records: stage details table, link column, status enum remap

Module 2 (plan §3.2 / §3.4 / §6.1). The status set becomes
``not_applied / applied / written_test / interview_done / offer / rejected /
withdrawn``: there is no ``interviewing`` state, and the two legacy draft
statuses collapse into ``not_applied``.

Revision ID: 20261117_0013
Revises: 20261116_0012
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261117_0013"
down_revision: str | None = "20261116_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (legacy value, new value) — applied in order, see plan §3.2.
_STATUS_FORWARD = (
    ("saved", "not_applied"),
    ("preparing", "not_applied"),
    ("interview", "interview_done"),
)
# Downgrade cannot restore which draft status a row had, so both collapse back
# to ``saved``; ``interview_done`` maps back to ``interview``.
_STATUS_BACKWARD = (
    ("not_applied", "saved"),
    ("written_test", "applied"),
    ("interview_done", "interview"),
)


def upgrade() -> None:
    op.create_table(
        "application_stage_details",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "application_id", "stage", name="uq_stage_detail_application_stage"
        ),
    )
    op.create_index(
        op.f("ix_application_stage_details_application_id"),
        "application_stage_details",
        ["application_id"],
    )
    op.create_index(
        op.f("ix_application_stage_details_user_id"),
        "application_stage_details",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_application_stage_details_stage"),
        "application_stage_details",
        ["stage"],
    )

    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("link", sa.String(length=1000), nullable=True))
        # The legacy enum column was sized to its longest old value ("preparing",
        # 9 chars). New statuses are longer ("not_applied" = 11,
        # "interview_done" = 14), and PostgreSQL enforces VARCHAR length on the
        # UPDATE below — SQLite does not, which is why this only surfaced in Docker.
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=9),
            type_=sa.String(length=20),
            existing_nullable=False,
        )

    _remap_statuses(_STATUS_FORWARD)


def downgrade() -> None:
    _remap_statuses(_STATUS_BACKWARD)

    with op.batch_alter_table("applications") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=20),
            type_=sa.String(length=9),
            existing_nullable=False,
        )
        batch_op.drop_column("link")

    op.drop_index(
        op.f("ix_application_stage_details_stage"), table_name="application_stage_details"
    )
    op.drop_index(
        op.f("ix_application_stage_details_user_id"), table_name="application_stage_details"
    )
    op.drop_index(
        op.f("ix_application_stage_details_application_id"),
        table_name="application_stage_details",
    )
    op.drop_table("application_stage_details")


def _remap_statuses(mapping: tuple[tuple[str, str], ...]) -> None:
    """Rewrite legacy status strings in place (the column is plain VARCHAR)."""
    bind = op.get_bind()
    applications = sa.table(
        "applications",
        sa.column("status", sa.String),
    )
    for old, new in mapping:
        bind.execute(
            sa.update(applications).where(applications.c.status == old).values(status=new)
        )
