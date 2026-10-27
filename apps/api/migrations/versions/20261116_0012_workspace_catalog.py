"""workspace job catalog: companies, announcements, positions, marks, imports

Backfills the legacy ``jobs`` table into the new catalog and links existing
applications to the announcement/position they came from. ``jobs`` stays
read-only for one release (plan §6.2 / §6.3).

Revision ID: 20261116_0012
Revises: 20261102_0011
Create Date: 2026-11-16
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20261116_0012"
down_revision: str | None = "20261102_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("company_type", sa.String(length=20), nullable=True),
        sa.Column("company_scale", sa.String(length=50), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=False)
    op.create_index(
        op.f("ix_companies_company_type"), "companies", ["company_type"], unique=False
    )

    op.create_table(
        "announcement_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("adapter_key", sa.String(length=50), nullable=False),
        sa.Column("home_url", sa.String(length=500), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_source_owner_name"),
    )
    op.create_index(
        op.f("ix_announcement_sources_owner_user_id"),
        "announcement_sources",
        ["owner_user_id"],
        unique=False,
    )

    op.create_table(
        "job_announcements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("recruitment_type", sa.String(length=20), nullable=True),
        sa.Column("target_cohort", sa.String(length=20), nullable=True),
        sa.Column("locations", sa.JSON(), nullable=False),
        sa.Column("locations_text", sa.String(length=300), nullable=True),
        sa.Column("positions_text", sa.Text(), nullable=True),
        sa.Column("announcement_url", sa.String(length=1000), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_channel", sa.String(length=50), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_text", sa.String(length=100), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("apply_method", sa.JSON(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="announcementstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            sa.Enum("private", "shared", name="announcementvisibility", native_enum=False),
            nullable=False,
        ),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["announcement_sources.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_announcements_title"), "job_announcements", ["title"])
    op.create_index(
        op.f("ix_job_announcements_company_id"), "job_announcements", ["company_id"]
    )
    op.create_index(
        op.f("ix_job_announcements_source_id"), "job_announcements", ["source_id"]
    )
    op.create_index(
        op.f("ix_job_announcements_recruitment_type"),
        "job_announcements",
        ["recruitment_type"],
    )
    op.create_index(
        op.f("ix_job_announcements_target_cohort"), "job_announcements", ["target_cohort"]
    )
    op.create_index(
        op.f("ix_job_announcements_published_at"), "job_announcements", ["published_at"]
    )
    op.create_index(
        op.f("ix_job_announcements_deadline_at"), "job_announcements", ["deadline_at"]
    )
    op.create_index(
        op.f("ix_job_announcements_status"), "job_announcements", ["status"]
    )
    op.create_index(
        op.f("ix_job_announcements_owner_user_id"),
        "job_announcements",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_job_announcements_dedupe_key"),
        "job_announcements",
        ["dedupe_key"],
        unique=True,
    )
    op.create_index(
        "ix_job_announcements_company_published",
        "job_announcements",
        ["company_id", "published_at"],
    )
    op.create_index(
        "ix_job_announcements_owner_updated",
        "job_announcements",
        ["owner_user_id", "updated_at"],
    )

    op.create_table(
        "job_positions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("announcement_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("city", sa.String(length=50), nullable=True),
        sa.Column("education", sa.String(length=50), nullable=True),
        sa.Column("headcount", sa.String(length=50), nullable=True),
        sa.Column("jd_text", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["announcement_id"], ["job_announcements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_positions_title"), "job_positions", ["title"])
    op.create_index(op.f("ix_job_positions_category"), "job_positions", ["category"])
    op.create_index(
        op.f("ix_job_positions_announcement_id"), "job_positions", ["announcement_id"]
    )

    op.create_table(
        "user_job_marks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("announcement_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["announcement_id"], ["job_announcements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "announcement_id", name="uq_mark_user_announcement"),
    )
    op.create_index(op.f("ix_user_job_marks_user_id"), "user_job_marks", ["user_id"])
    op.create_index(
        op.f("ix_user_job_marks_announcement_id"), "user_job_marks", ["announcement_id"]
    )

    op.create_table(
        "job_imports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("parsed", sa.JSON(), nullable=False),
        sa.Column("raw_snapshot", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("llm_used", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_imports_user_id"), "job_imports", ["user_id"])
    op.create_index(op.f("ix_job_imports_status"), "job_imports", ["status"])

    op.create_table(
        "user_table_preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("table_key", sa.String(length=50), nullable=False),
        sa.Column("visible_columns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "table_key", name="uq_table_pref"),
    )
    op.create_index(
        op.f("ix_user_table_preferences_user_id"), "user_table_preferences", ["user_id"]
    )

    # -- applications: catalog linkage + module 2 columns -------------------
    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("announcement_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("position_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("company_name", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("position_title", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("channel", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("contact_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("contact_info", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("closed_reason", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("rejected_stage", sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column("row_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column("job_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.create_foreign_key(
            "fk_applications_announcement",
            "job_announcements",
            ["announcement_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_applications_position",
            "job_positions",
            ["position_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_applications_announcement_id", ["announcement_id"])
        batch_op.create_index("ix_applications_position_id", ["position_id"])
        batch_op.create_unique_constraint(
            "uq_application_user_position", ["user_id", "position_id"]
        )

    _backfill_catalog()
    op.create_index(
        "ix_applications_user_applied",
        "applications",
        ["user_id", "applied_at"],
    )
    op.create_index(
        "ix_applications_user_status_updated",
        "applications",
        ["user_id", "status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_applications_user_status_updated", table_name="applications")
    op.drop_index("ix_applications_user_applied", table_name="applications")
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_constraint("uq_application_user_position", type_="unique")
        batch_op.drop_index("ix_applications_position_id")
        batch_op.drop_index("ix_applications_announcement_id")
        batch_op.drop_constraint("fk_applications_position", type_="foreignkey")
        batch_op.drop_constraint("fk_applications_announcement", type_="foreignkey")
        for column in (
            "deleted_at",
            "row_version",
            "rejected_stage",
            "closed_reason",
            "contact_info",
            "contact_name",
            "channel",
            "position_title",
            "company_name",
            "position_id",
            "announcement_id",
        ):
            batch_op.drop_column(column)

    op.drop_index(
        op.f("ix_user_table_preferences_user_id"), table_name="user_table_preferences"
    )
    op.drop_table("user_table_preferences")
    op.drop_index(op.f("ix_job_imports_status"), table_name="job_imports")
    op.drop_index(op.f("ix_job_imports_user_id"), table_name="job_imports")
    op.drop_table("job_imports")
    op.drop_index(op.f("ix_user_job_marks_announcement_id"), table_name="user_job_marks")
    op.drop_index(op.f("ix_user_job_marks_user_id"), table_name="user_job_marks")
    op.drop_table("user_job_marks")
    op.drop_index(op.f("ix_job_positions_announcement_id"), table_name="job_positions")
    op.drop_index(op.f("ix_job_positions_category"), table_name="job_positions")
    op.drop_index(op.f("ix_job_positions_title"), table_name="job_positions")
    op.drop_table("job_positions")
    for index_name in (
        "ix_job_announcements_owner_updated",
        "ix_job_announcements_company_published",
        "ix_job_announcements_dedupe_key",
        "ix_job_announcements_owner_user_id",
        "ix_job_announcements_status",
        "ix_job_announcements_deadline_at",
        "ix_job_announcements_published_at",
        "ix_job_announcements_target_cohort",
        "ix_job_announcements_recruitment_type",
        "ix_job_announcements_source_id",
        "ix_job_announcements_company_id",
        "ix_job_announcements_title",
    ):
        op.drop_index(op.f(index_name), table_name="job_announcements")
    op.drop_table("job_announcements")
    op.drop_index(
        op.f("ix_announcement_sources_owner_user_id"), table_name="announcement_sources"
    )
    op.drop_table("announcement_sources")
    op.drop_index(op.f("ix_companies_company_type"), table_name="companies")
    op.drop_index(op.f("ix_companies_name"), table_name="companies")
    op.drop_table("companies")


def _backfill_catalog() -> None:
    """jobs → companies + announcements + positions, then link applications."""
    bind = op.get_bind()

    jobs = sa.table(
        "jobs",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("title", sa.String),
        sa.column("company_name", sa.String),
        sa.column("city", sa.String),
        sa.column("employment_type", sa.String),
        sa.column("raw_text", sa.Text),
        sa.column("source_url", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    companies = sa.table(
        "companies",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("company_type", sa.String),
        sa.column("company_scale", sa.String),
        sa.column("industry", sa.String),
        sa.column("website", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    announcements = sa.table(
        "job_announcements",
        sa.column("id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("source_id", sa.String),
        sa.column("title", sa.String),
        sa.column("recruitment_type", sa.String),
        sa.column("target_cohort", sa.String),
        sa.column("locations", sa.JSON),
        sa.column("locations_text", sa.String),
        sa.column("positions_text", sa.Text),
        sa.column("announcement_url", sa.String),
        sa.column("source_url", sa.String),
        sa.column("source_channel", sa.String),
        sa.column("published_at", sa.DateTime),
        sa.column("deadline_at", sa.DateTime),
        sa.column("deadline_text", sa.String),
        sa.column("raw_text", sa.Text),
        sa.column("apply_method", sa.JSON),
        sa.column("snapshot_at", sa.DateTime),
        sa.column("status", sa.String),
        sa.column("visibility", sa.String),
        sa.column("owner_user_id", sa.String),
        sa.column("dedupe_key", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    positions = sa.table(
        "job_positions",
        sa.column("id", sa.String),
        sa.column("announcement_id", sa.String),
        sa.column("title", sa.String),
        sa.column("category", sa.String),
        sa.column("city", sa.String),
        sa.column("education", sa.String),
        sa.column("headcount", sa.String),
        sa.column("jd_text", sa.Text),
        sa.column("sort_order", sa.Integer),
    )
    applications = sa.table(
        "applications",
        sa.column("id", sa.String),
        sa.column("job_id", sa.String),
        sa.column("announcement_id", sa.String),
        sa.column("position_id", sa.String),
        sa.column("company_name", sa.String),
        sa.column("position_title", sa.String),
    )

    company_ids: dict[str, str] = {}
    legacy_links: dict[str, tuple[str, str, str, str]] = {}
    now = _now()

    for job in bind.execute(sa.select(jobs)).mappings():
        company_name = (job["company_name"] or "").strip() or "未知公司"
        company_id = company_ids.get(company_name)
        if company_id is None:
            existing = bind.execute(
                sa.select(companies.c.id).where(companies.c.name == company_name)
            ).scalar()
            if existing:
                company_id = str(existing)
            else:
                company_id = str(uuid4())
                bind.execute(
                    sa.insert(companies).values(
                        id=company_id,
                        name=company_name,
                        created_at=now,
                        updated_at=now,
                    )
                )
            company_ids[company_name] = company_id

        announcement_id = str(uuid4())
        position_id = str(uuid4())
        locations = [job["city"]] if job["city"] else []
        recruitment_type = "实习" if job["employment_type"] == "internship" else "社招"
        bind.execute(
            sa.insert(announcements).values(
                id=announcement_id,
                company_id=company_id,
                source_id=None,
                title=job["title"],
                recruitment_type=recruitment_type,
                target_cohort=None,
                locations=locations,
                locations_text="、".join(locations) or None,
                positions_text=job["title"],
                announcement_url=job["source_url"],
                source_url=job["source_url"],
                source_channel="legacy",
                published_at=job["created_at"],
                deadline_at=None,
                deadline_text=None,
                raw_text=job["raw_text"] or "",
                apply_method={},
                snapshot_at=job["created_at"],
                status="active",
                visibility="private",
                owner_user_id=job["user_id"],
                dedupe_key=f"legacy:{job['id']}",
                created_at=job["created_at"],
                updated_at=job["updated_at"],
            )
        )
        bind.execute(
            sa.insert(positions).values(
                id=position_id,
                announcement_id=announcement_id,
                title=job["title"],
                category=None,
                city=job["city"],
                education=None,
                headcount=None,
                jd_text=job["raw_text"],
                sort_order=0,
            )
        )
        legacy_links[job["id"]] = (
            announcement_id,
            position_id,
            company_name,
            job["title"],
        )

    for job_id, (announcement_id, position_id, company_name, title) in legacy_links.items():
        bind.execute(
            sa.update(applications)
            .where(applications.c.job_id == job_id)
            .values(
                announcement_id=announcement_id,
                position_id=position_id,
                company_name=company_name,
                position_title=title,
            )
        )
