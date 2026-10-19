"""Connect applications to follow-up reminders and interview feedback."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_0010"
down_revision: str | None = "20261016_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("interview_feedback", sa.Text(), nullable=True))
    op.create_index("ix_applications_next_follow_up_at", "applications", ["next_follow_up_at"])


def downgrade() -> None:
    op.drop_index("ix_applications_next_follow_up_at", table_name="applications")
    op.drop_column("applications", "interview_feedback")
    op.drop_column("applications", "next_follow_up_at")
