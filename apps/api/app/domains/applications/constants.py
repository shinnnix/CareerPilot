"""Shared vocabulary for the application records module (plan §3.2).

Statuses describe *completed* milestones only: there is deliberately no
``interviewing`` state, because a user never edits a record mid-interview.
Scheduling and rounds live in ``application_stage_details`` instead.
"""

from __future__ import annotations

# Ordered by funnel progress; lower index = further along.
STATUS_ORDER = (
    "not_applied",
    "applied",
    "written_test",
    "interview_done",
    "offer",
    "rejected",
    "withdrawn",
)

STATUS_LABELS = {
    "not_applied": "未投递",
    "applied": "已投递",
    "written_test": "已笔试",
    "interview_done": "已面试",
    "offer": "面试通过",
    "rejected": "已挂",
    "withdrawn": "已放弃",
}

# Statuses that end the funnel. They close follow-up reminders (plan §3.2).
TERMINAL_STATUSES = frozenset({"offer", "rejected", "withdrawn"})

# Statuses that imply an actual submission and therefore need ``applied_at``.
APPLIED_STATUSES = frozenset(
    {"applied", "written_test", "interview_done", "offer", "rejected", "withdrawn"}
)

# Forward-only, skipping allowed (plan §3.2). ``rejected`` / ``withdrawn`` can be
# corrected back to ``applied`` for mis-clicks; the event log keeps the history.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "not_applied": frozenset({"applied"}),
    "applied": frozenset({"written_test", "interview_done", "offer", "rejected", "withdrawn"}),
    "written_test": frozenset({"interview_done", "offer", "rejected", "withdrawn"}),
    "interview_done": frozenset({"offer", "rejected", "withdrawn"}),
    "offer": frozenset({"withdrawn"}),
    "rejected": frozenset({"applied"}),
    "withdrawn": frozenset({"applied"}),
}

# Source statuses for a correction back to ``applied`` (logged separately).
CORRECTABLE_STATUSES = frozenset({"rejected", "withdrawn"})

# Statuses offered in the 状态 filter, funnel order.
FILTERABLE_STATUSES = STATUS_ORDER

# Rows migrated from the pre-module-2 enum still match ``not_applied``.
STATUS_FILTER_ALIASES = {
    "not_applied": frozenset({"not_applied", "saved", "preparing"}),
    "interview_done": frozenset({"interview_done", "interview"}),
}

CHANNELS = ("官网", "公众号邮箱", "网申链接", "内推", "招聘平台", "其他")

CLOSED_REASONS = ("HC 取消", "技能不匹配", "竞争失败", "流程过长", "薪资不符", "其他")

REJECTED_STAGES = ("简历", "笔试", "面试", "终面", "未知")

# Stage detail keys. ``interview`` is a *detail* stage, not a status.
STAGES = ("written_test", "interview", "offer")

STAGE_LABELS = {
    "written_test": "笔试详情",
    "interview": "面试详情",
    "offer": "Offer 详情",
}

# Which status the detail normally accompanies — used for hints only, never
# enforced (plan §3.4.1: details are optional back-fill).
STAGE_HINTS = {
    "written_test": "已笔试",
    "interview": "已面试",
    "offer": "面试通过",
}

STATUS_INDEX = {value: index for index, value in enumerate(STATUS_ORDER)}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def next_statuses(current: str) -> list[str]:
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    return sorted(allowed, key=lambda value: STATUS_INDEX.get(value, len(STATUS_ORDER)))
