"""Shared vocabulary for the job catalog (module 1).

The catalog stores human-readable Chinese values instead of machine codes:
the whole product is Chinese-only, facets and CSV export become trivial, and
there is no enum-name/value mismatch when reading raw rows.
"""

from __future__ import annotations

COMPANY_TYPES = ("民企", "国企", "外企", "央企", "事业单位")
RECRUITMENT_TYPES = ("秋招", "春招", "社招", "实习", "补录")
DEFAULT_TARGET_COHORT = "不限"

# Row status is derived from the applications of an announcement (plan §2.6).
# Lower index = further along the funnel, so ``min`` picks the most advanced.
STATUS_PRIORITY = (
    "offer",
    "interview_done",
    "interview",
    "written_test",
    "applied",
    "rejected",
    "withdrawn",
    "not_applied",
    "saved",
    "preparing",
)

STATUS_LABELS = {
    "not_applied": "未投递",
    "saved": "未投递",
    "preparing": "未投递",
    "applied": "已投递",
    "written_test": "已笔试",
    "interview_done": "已面试",
    "interview": "已面试",
    "offer": "面试通过",
    "rejected": "已挂",
    "withdrawn": "已放弃",
    "deferred": "暂不投递",
}

# Filter options for the 状态 select, ordered by funnel progress.
FILTERABLE_STATUSES = (
    "not_applied",
    "applied",
    "written_test",
    "interview_done",
    "offer",
    "rejected",
    "withdrawn",
    "deferred",
)

# ``not_applied`` also matches the legacy draft statuses.
STATUS_FILTER_ALIASES = {
    "not_applied": {"not_applied", "saved", "preparing"},
}

# Normalised funnel order used by the SQL rank expression (module 1 filter).
# Legacy values collapse onto their new equivalent so a single CASE is enough.
ROW_STATUS_PRIORITY = (
    "offer",
    "interview_done",
    "written_test",
    "applied",
    "rejected",
    "withdrawn",
    "not_applied",
)

STATUS_RANK = {
    "offer": 0,
    "interview_done": 1,
    "interview": 1,
    "written_test": 2,
    "applied": 3,
    "rejected": 4,
    "withdrawn": 5,
    "not_applied": 6,
    "saved": 6,
    "preparing": 6,
}

# Buckets for announcements without any application (facets grouping).
NO_APPLICATION_BUCKET = 100
DEFERRED_BUCKET = 101

STATUS_PRIORITY_INDEX = {value: index for index, value in enumerate(STATUS_PRIORITY)}

DEFAULT_VISIBLE_COLUMNS = (
    "company_name",
    "company_type",
    "recruitment_type",
    "target_cohort",
    "location",
    "positions",
    "updated_at",
    "deadline",
    "announcement",
    "mark_status",
)

TABLE_COLUMNS = (
    "company_name",
    "company_type",
    "recruitment_type",
    "target_cohort",
    "location",
    "positions",
    "updated_at",
    "deadline",
    "announcement",
    "company_scale",
    "mark_status",
)

JOB_TABLE_KEY = "jobs"


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def derive_row_status(application_statuses: list[str], *, deferred: bool) -> str:
    """Collapse per-position application statuses into one row status."""
    if not application_statuses:
        return "deferred" if deferred else "not_applied"
    best = min(
        application_statuses,
        key=lambda value: STATUS_PRIORITY_INDEX.get(value, len(STATUS_PRIORITY)),
    )
    return best
