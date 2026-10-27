"""P1 features: reminder inbox, resume version locking, status correction,
batch marks."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

RESUME_TEXT = """李四
13900000000
lisi@example.com

项目经历
检索助手 | 技术栈：Python、FastAPI
- 负责检索链路与评测脚本。

专业技能
- 熟练使用 Python 与 FastAPI。
"""

ANNOUNCEMENT_TEXT = """星河智能 2027 届校园招聘公告
公司：星河智能

任职要求：
- 熟悉 Python、FastAPI 与 RAG
"""


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


def create_resume(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/resumes/import/text",
        json={"display_name": "我的简历", "raw_text": RESUME_TEXT},
    )
    assert response.status_code == 201, response.text
    return response.json()


def import_announcement(client: TestClient, *, suffix: str = "") -> dict[str, object]:
    imported = client.post(
        "/api/v1/workspace/jobs/import/text",
        json={"raw_text": ANNOUNCEMENT_TEXT, "source_name": "星河智能招聘"},
    )
    draft = imported.json()
    confirmed = client.post(
        f"/api/v1/workspace/jobs/imports/{draft['id']}/confirm",
        json={
            "company_name": "星河智能",
            "title": f"星河智能 2027 届校园招聘公告{suffix}",
            "positions": [{"title": "后端开发工程师"}, {"title": "算法工程师"}],
            "raw_text": ANNOUNCEMENT_TEXT,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def create_manual_application(
    client: TestClient,
    *,
    follow_up_at: str | None = None,
    status: str = "applied",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "company_name": "示例公司",
        "position_title": "后端实习",
        "status": status,
    }
    if follow_up_at:
        payload["follow_up_at"] = follow_up_at
    response = client.post("/api/v1/workspace/applications", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["items"][0]


# -- resume versions ---------------------------------------------------------


def test_applied_application_locks_a_resume_snapshot(client: TestClient) -> None:
    resume = create_resume(client)
    announcement = import_announcement(client)
    positions = client.get(
        f"/api/v1/workspace/jobs/{announcement['id']}"
    ).json()["positions"]

    created = client.post(
        "/api/v1/workspace/applications",
        json={
            "announcement_id": announcement["id"],
            "position_ids": [positions[0]["id"]],
        },
    )
    assert created.status_code == 201, created.text
    application_id = created.json()["items"][0]["id"]

    detail = client.get(f"/api/v1/workspace/applications/{application_id}").json()
    assert detail["resume_id"] == resume["id"]
    version = detail["resume_version"]
    assert version is not None and version["version_no"] == 1

    # Editing the resume afterwards must not rewrite the locked snapshot.
    changed = [dict(section) for section in resume["sections"]]
    project = next(section for section in changed if section["key"] == "project")
    project["entries"][0]["bullets"] = ["改写后的项目描述"]
    patched = client.patch(
        f"/api/v1/resumes/{resume['id']}", json={"sections": changed}
    )
    assert patched.status_code == 200, patched.text

    version_detail = client.get(
        f"/api/v1/resumes/{resume['id']}/versions/1"
    ).json()
    project_snapshot = next(
        section for section in version_detail["sections"] if section["key"] == "project"
    )
    assert project_snapshot["entries"][0]["bullets"] == [
        "负责检索链路与评测脚本。"
    ]
    versions = client.get(f"/api/v1/resumes/{resume['id']}/versions").json()
    assert versions["total"] == 1


def test_manual_lock_endpoint_creates_a_new_version(client: TestClient) -> None:
    resume = create_resume(client)
    application = create_manual_application(client, status="not_applied")

    locked = client.post(
        f"/api/v1/workspace/applications/{application['id']}/resume-version",
        json={"resume_id": resume["id"], "note": "手动锁定"},
    )

    assert locked.status_code == 200, locked.text
    assert locked.json()["resume_version"]["version_no"] == 1
    events = locked.json()["events"]
    assert any(event["event_type"] == "resume_version_locked" for event in events)


# -- reminders ---------------------------------------------------------------


def test_follow_up_reminder_is_generated_idempotently(client: TestClient) -> None:
    create_manual_application(client, follow_up_at=_iso(timedelta(days=-1)))

    first = client.get("/api/v1/workspace/reminders").json()
    second = client.get("/api/v1/workspace/reminders").json()

    assert first["total"] == 1
    assert first["items"][0]["rule_type"] == "follow_up_due"
    assert second["total"] == 1  # dedupe_key prevents duplicates
    assert second["pending"] == 1
    assert second["due_now"] == 1


def test_reminder_dismiss_is_not_resurrected(client: TestClient) -> None:
    create_manual_application(client, follow_up_at=_iso(timedelta(days=-1)))
    reminder = client.get("/api/v1/workspace/reminders").json()["items"][0]

    dismissed = client.post(
        f"/api/v1/workspace/reminders/{reminder['id']}/dismiss"
    )
    assert dismissed.status_code == 200
    assert client.get("/api/v1/workspace/reminders").json()["total"] == 0


def test_snooze_hides_until_due(client: TestClient) -> None:
    create_manual_application(client, follow_up_at=_iso(timedelta(days=-1)))
    reminder = client.get("/api/v1/workspace/reminders").json()["items"][0]

    snoozed = client.post(
        f"/api/v1/workspace/reminders/{reminder['id']}/snooze", json={"hours": 48}
    )

    assert snoozed.status_code == 200
    assert snoozed.json()["snoozed_until"] is not None
    assert client.get("/api/v1/workspace/reminders").json()["total"] == 0
    assert (
        client.get(
            "/api/v1/workspace/reminders", params={"include_snoozed": True}
        ).json()["total"]
        == 1
    )


def test_terminal_status_clears_pending_reminders(client: TestClient) -> None:
    application = create_manual_application(
        client, follow_up_at=_iso(timedelta(days=-1))
    )
    assert client.get("/api/v1/workspace/reminders").json()["total"] == 1

    rejected = client.patch(
        f"/api/v1/workspace/applications/{application['id']}",
        json={"status": "rejected", "row_version": application["row_version"]},
    )
    assert rejected.status_code == 200, rejected.text

    assert client.get("/api/v1/workspace/reminders").json()["total"] == 0


def test_reminders_are_user_scoped(client: TestClient) -> None:
    create_manual_application(client, follow_up_at=_iso(timedelta(days=-1)))

    other = client.get(
        "/api/v1/workspace/reminders", headers={"X-User-ID": "other-user"}
    ).json()

    assert other["total"] == 0


# -- status correction -------------------------------------------------------


def test_rejected_can_be_corrected_back_to_applied(client: TestClient) -> None:
    application = create_manual_application(client)
    rejected = client.patch(
        f"/api/v1/workspace/applications/{application['id']}",
        json={"status": "rejected", "row_version": application["row_version"]},
    ).json()
    assert "applied" in rejected["allowed_transitions"]

    corrected = client.patch(
        f"/api/v1/workspace/applications/{application['id']}",
        json={
            "status": "applied",
            "row_version": rejected["row_version"],
            "event_note": "误操作修正",
        },
    )

    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["status"] == "applied"
    assert any(
        event["event_type"] == "status_corrected"
        for event in corrected.json()["events"]
    )


# -- batch marks -------------------------------------------------------------


def test_batch_defer_and_restore(client: TestClient) -> None:
    first = import_announcement(client, suffix="（A）")
    second = import_announcement(client, suffix="（B）")
    ids = [first["id"], second["id"]]

    deferred = client.patch(
        "/api/v1/workspace/jobs/marks",
        json={"announcement_ids": ids, "status": "deferred", "note": "等春招"},
    )
    assert deferred.status_code == 200, deferred.text
    assert {item["mark_status"] for item in deferred.json()} == {"deferred"}
    listed = client.get(
        "/api/v1/workspace/jobs", params={"status": "deferred"}
    ).json()
    assert listed["total"] == 2

    restored = client.patch(
        "/api/v1/workspace/jobs/marks",
        json={"announcement_ids": ids, "status": "none"},
    )
    assert restored.status_code == 200
    assert {item["mark_status"] for item in restored.json()} == {"not_applied"}
    assert (
        client.get("/api/v1/workspace/jobs", params={"status": "deferred"}).json()["total"]
        == 0
    )
