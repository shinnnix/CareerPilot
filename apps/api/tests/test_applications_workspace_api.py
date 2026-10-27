"""Module 2 — application records (plan §3.7 acceptance list)."""

from fastapi.testclient import TestClient

BASE = "/api/v1/workspace/applications"


def create_manual(
    client: TestClient,
    *,
    company: str = "星河智能",
    position: str = "后端开发工程师",
    status: str = "applied",
    applied_at: str | None = "2026-03-02T09:00:00+00:00",
    follow_up_at: str | None = None,
    channel: str | None = "官网",
    contact_name: str | None = "王老师",
    notes: str | None = None,
    allow_duplicate: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "company_name": company,
        "position_title": position,
        "status": status,
        "channel": channel,
        "contact_name": contact_name,
        "allow_duplicate": allow_duplicate,
    }
    if applied_at:
        payload["applied_at"] = applied_at
    if follow_up_at:
        payload["follow_up_at"] = follow_up_at
    if notes:
        payload["notes"] = notes
    response = client.post(BASE, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["items"][0]


def test_manual_create_returns_all_eight_columns(client: TestClient) -> None:
    row = create_manual(client, notes="内推码 ABC123")

    assert row["company_name"] == "星河智能"
    assert row["position_title"] == "后端开发工程师"
    assert row["status"] == "applied"
    assert row["status_label"] == "已投递"
    assert row["applied_at"] is not None
    assert row["channel"] == "官网"
    assert row["contact_name"] == "王老师"
    assert row["notes"] == "内推码 ABC123"
    assert row["row_version"] == 1
    assert row["is_terminal"] is False
    assert row["follow_up_at"] is None

    listing = client.get(BASE).json()
    assert listing["total"] == 1
    assert listing["page_count"] == 1
    assert listing["status_counts"] == {"applied": 1}


def test_manual_create_validates_required_fields_and_dates(client: TestClient) -> None:
    missing_company = client.post(BASE, json={"position_title": "后端开发工程师"})
    assert missing_company.status_code == 422
    assert missing_company.json()["code"] == "VALIDATION_ERROR"

    missing_position = client.post(BASE, json={"company_name": "星河智能"})
    assert missing_position.status_code == 422

    bad_dates = client.post(
        BASE,
        json={
            "company_name": "星河智能",
            "position_title": "后端开发工程师",
            "applied_at": "2026-03-10T00:00:00+00:00",
            "follow_up_at": "2026-03-01T00:00:00+00:00",
        },
    )
    assert bad_dates.status_code == 422


def test_applied_at_is_filled_when_status_implies_submission(client: TestClient) -> None:
    response = client.post(
        BASE,
        json={"company_name": "云杉科技", "position_title": "数据分析", "status": "applied"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["items"][0]["applied_at"] is not None

    draft = client.post(
        BASE,
        json={"company_name": "云杉科技", "position_title": "算法实习", "status": "not_applied"},
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["items"][0]["applied_at"] is None


def test_search_matches_company_position_contact_and_notes(client: TestClient) -> None:
    create_manual(client, company="星河智能", position="后端开发", contact_name="王老师")
    create_manual(
        client,
        company="云杉科技",
        position="数据分析",
        contact_name="李经理",
        notes="等待笔试通知",
        applied_at="2026-03-05T09:00:00+00:00",
    )

    def total(keyword: str) -> int:
        return client.get(BASE, params={"keyword": keyword}).json()["total"]

    assert total("星河") == 1
    assert total("数据分析") == 1
    assert total("李经理") == 1
    assert total("笔试通知") == 1
    assert total("不存在的关键词") == 0


def test_status_filter_and_counts_are_stacked_with_keyword(client: TestClient) -> None:
    create_manual(client, status="applied")
    create_manual(
        client,
        position="前端开发",
        status="written_test",
        applied_at="2026-03-03T09:00:00+00:00",
    )

    applied = client.get(BASE, params={"status": "applied"}).json()
    assert applied["total"] == 1
    assert applied["status_counts"] == {"applied": 1, "written_test": 1}

    combined = client.get(BASE, params={"status": "written_test", "keyword": "星河"}).json()
    assert combined["total"] == 1
    assert combined["items"][0]["position_title"] == "前端开发"

    unknown = client.get(BASE, params={"status": "interviewing"})
    assert unknown.status_code == 422


def test_transition_rules_are_forward_only_and_leave_events(client: TestClient) -> None:
    row = create_manual(client, status="not_applied", applied_at=None)
    application_id = row["id"]

    applied = client.patch(
        f"{BASE}/{application_id}",
        json={"status": "applied", "row_version": 1, "event_note": "官网投递完成"},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    assert applied.json()["applied_at"] is not None
    assert applied.json()["row_version"] == 2

    # Skipping a step is allowed: applied → interview_done.
    skipped = client.patch(
        f"{BASE}/{application_id}", json={"status": "interview_done", "row_version": 2}
    )
    assert skipped.status_code == 200, skipped.text

    backwards = client.patch(
        f"{BASE}/{application_id}", json={"status": "applied", "row_version": 3}
    )
    assert backwards.status_code == 409
    assert backwards.json()["code"] == "INVALID_APPLICATION_TRANSITION"
    assert "已面试" in backwards.json()["message"]

    # Same-status resubmission must not append an event.
    same = client.patch(
        f"{BASE}/{application_id}", json={"status": "interview_done", "row_version": 3}
    )
    assert same.status_code == 200
    event_types = [event["event_type"] for event in same.json()["events"]]
    assert event_types == ["created", "status_changed", "status_changed"]


def test_stale_row_version_conflicts(client: TestClient) -> None:
    row = create_manual(client)
    stale = client.patch(
        f"{BASE}/{row['id']}", json={"notes": "旧窗口的修改", "row_version": 9}
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "APPLICATION_VERSION_CONFLICT"
    assert stale.json()["details"]["current_row_version"] == 1


def test_terminal_status_closes_follow_up_and_marks_row(client: TestClient) -> None:
    row = create_manual(client, follow_up_at="2030-01-01T00:00:00+00:00")
    assert row["follow_up_at"] is not None

    rejected = client.patch(
        f"{BASE}/{row['id']}",
        json={
            "status": "rejected",
            "closed_reason": "技能不匹配",
            "rejected_stage": "面试",
            "row_version": 1,
        },
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["status_label"] == "已挂"
    assert body["is_terminal"] is True
    assert body["follow_up_at"] is None
    assert body["closed_reason"] == "技能不匹配"
    assert body["rejected_stage"] == "面试"


def test_invalid_closed_reason_is_rejected(client: TestClient) -> None:
    row = create_manual(client)
    response = client.patch(
        f"{BASE}/{row['id']}",
        json={"status": "rejected", "closed_reason": "看心情", "row_version": 1},
    )
    assert response.status_code == 422


def test_soft_delete_hides_row_from_list_and_detail(client: TestClient) -> None:
    row = create_manual(client)
    deleted = client.delete(f"{BASE}/{row['id']}")
    assert deleted.status_code == 204

    assert client.get(BASE).json()["total"] == 0
    assert client.get(f"{BASE}/{row['id']}").status_code == 404


def test_pagination_edges(client: TestClient) -> None:
    for index in range(25):
        create_manual(
            client,
            position=f"岗位-{index:02d}",
            applied_at=f"2026-03-{(index % 28) + 1:02d}T09:00:00+00:00",
        )

    first = client.get(BASE, params={"page": 1, "page_size": 10}).json()
    assert first["total"] == 25
    assert first["page_count"] == 3
    assert len(first["items"]) == 10

    last = client.get(BASE, params={"page": 3, "page_size": 10}).json()
    assert len(last["items"]) == 5

    beyond = client.get(BASE, params={"page": 9, "page_size": 10}).json()
    assert beyond["items"] == []
    assert beyond["total"] == 25


def test_stage_details_upsert_list_and_delete(client: TestClient) -> None:
    row = create_manual(client, status="written_test")
    application_id = row["id"]

    created = client.put(
        f"{BASE}/{application_id}/stage-details/written_test",
        json={
            "payload": {
                "taken_at": "2026-03-06T10:00:00+00:00",
                "duration_minutes": 90,
                "score": "88",
                "result": "passed",
                "notes": "两道算法题",
            }
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["stage"] == "written_test"
    assert created.json()["stage_label"] == "笔试详情"
    assert created.json()["payload"]["score"] == "88"

    updated = client.put(
        f"{BASE}/{application_id}/stage-details/written_test",
        json={"payload": {"score": "92", "result": "passed"}},
    )
    assert updated.status_code == 200
    assert updated.json()["payload"]["score"] == "92"

    listed = client.get(f"{BASE}/{application_id}/stage-details").json()
    assert len(listed) == 1
    assert listed[0]["payload"]["score"] == "92"

    # Details never change the status (plan §3.4.1).
    assert client.get(f"{BASE}/{application_id}").json()["status"] == "written_test"

    removed = client.delete(f"{BASE}/{application_id}/stage-details/written_test")
    assert removed.status_code == 204
    assert client.get(f"{BASE}/{application_id}/stage-details").json() == []
    assert (
        client.delete(f"{BASE}/{application_id}/stage-details/written_test").status_code == 404
    )


def test_stage_detail_validation_rejects_dirty_values_only(client: TestClient) -> None:
    row = create_manual(client, status="offer")

    negative_salary = client.put(
        f"{BASE}/{row['id']}/stage-details/offer",
        json={"payload": {"salary": {"monthly": -1}}},
    )
    assert negative_salary.status_code == 422
    assert negative_salary.json()["code"] == "STAGE_DETAIL_INVALID"

    # Empty payload is fine: details are optional back-fill.
    empty = client.put(f"{BASE}/{row['id']}/stage-details/offer", json={"payload": {}})
    assert empty.status_code == 200

    too_many_rounds = client.put(
        f"{BASE}/{row['id']}/stage-details/interview",
        json={"payload": {"rounds": [{"index": 1} for _ in range(16)]}},
    )
    assert too_many_rounds.status_code == 422

    unknown_stage = client.put(
        f"{BASE}/{row['id']}/stage-details/onsite", json={"payload": {}}
    )
    assert unknown_stage.status_code == 422


def test_detail_exposes_transitions_and_recommended_fields(client: TestClient) -> None:
    row = create_manual(client, status="applied")
    detail = client.get(f"{BASE}/{row['id']}").json()

    assert detail["allowed_transitions"] == [
        "written_test",
        "interview_done",
        "offer",
        "rejected",
        "withdrawn",
    ]
    assert detail["recommended_missing"] == []
    assert [event["event_type"] for event in detail["events"]] == ["created"]

    offer = client.patch(
        f"{BASE}/{row['id']}", json={"status": "offer", "row_version": 1}
    ).json()
    assert offer["recommended_missing"] == ["base_city", "start_date", "reply_deadline"]

    client.put(
        f"{BASE}/{row['id']}/stage-details/offer",
        json={"payload": {"base_city": "深圳", "start_date": "2026-07-01"}},
    )
    after = client.get(f"{BASE}/{row['id']}").json()
    assert after["recommended_missing"] == ["reply_deadline"]


def test_duplicate_hint_then_allow_duplicate(client: TestClient) -> None:
    create_manual(client)
    duplicate = client.post(
        BASE,
        json={
            "company_name": "星河智能",
            "position_title": "后端开发工程师",
            "status": "applied",
            "applied_at": "2026-03-02T09:00:00+00:00",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "APPLICATION_DUPLICATE_HINT"

    forced = create_manual(client, allow_duplicate=True)
    assert forced["id"]
    assert client.get(BASE).json()["total"] == 2


def test_follow_up_due_flag_and_endpoint(client: TestClient) -> None:
    create_manual(
        client,
        follow_up_at="2020-01-01T00:00:00+00:00",
        applied_at="2019-12-01T09:00:00+00:00",
        position="过期跟进",
    )
    create_manual(
        client,
        follow_up_at="2099-01-01T00:00:00+00:00",
        position="未来跟进",
        applied_at="2026-03-04T09:00:00+00:00",
    )

    rows = client.get(BASE).json()["items"]
    due = {row["position_title"]: row["follow_up_due"] for row in rows}
    assert due == {"过期跟进": True, "未来跟进": False}

    followups = client.get(f"{BASE}/follow-ups").json()
    assert followups["total"] == 1
    assert followups["items"][0]["position_title"] == "过期跟进"


def test_metrics_and_export(client: TestClient) -> None:
    create_manual(client, position="A", status="applied")
    create_manual(
        client,
        position="B",
        status="rejected",
        applied_at="2026-03-03T09:00:00+00:00",
        notes="流程过长",
    )

    metrics = client.get(f"{BASE}/metrics").json()
    assert metrics["total"] == 2
    assert metrics["by_status"]["applied"] == 1
    assert metrics["by_status"]["rejected"] == 1
    assert metrics["terminal"] == 1
    assert metrics["active"] == 1

    export = client.get(f"{BASE}/export")
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    text = export.text
    assert text.startswith("\ufeff")
    assert "公司,岗位,状态" in text
    assert "已挂" in text
    assert len([line for line in text.splitlines() if line.strip()]) == 3


def test_sort_by_follow_up_puts_empty_last(client: TestClient) -> None:
    create_manual(client, position="无跟进")
    create_manual(
        client,
        position="有跟进",
        follow_up_at="2026-04-01T00:00:00+00:00",
        applied_at="2026-03-05T09:00:00+00:00",
    )

    rows = client.get(BASE, params={"sort": "follow_up_asc"}).json()["items"]
    assert rows[0]["position_title"] == "有跟进"
    assert rows[-1]["position_title"] == "无跟进"


def test_applications_are_user_scoped(client: TestClient) -> None:
    row = create_manual(client)
    other = client.get(f"{BASE}/{row['id']}", headers={"X-User-ID": "other-user"})
    assert other.status_code == 404
    assert client.get(BASE, headers={"X-User-ID": "other-user"}).json()["total"] == 0
