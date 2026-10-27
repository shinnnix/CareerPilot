from fastapi.testclient import TestClient

ANNOUNCEMENT_TEXT = """【星河智能】2027届校园招聘公告

星河智能2027届秋季校园招聘正式启动，面向全国高校应届毕业生。

招聘岗位：后端开发工程师、算法工程师、前端开发工程师

工作地点：上海、深圳、杭州

任职要求：熟悉 Python / Java，具备良好的工程能力。

简历投递截止时间：2026年11月30日

投递方式：请将简历发送至 campus@xinghe.example.com
"""

SECOND_TEXT = """云帆数据 2026届春季招聘

招聘岗位：数据分析师

工作地点：北京

截止时间：2026年12月31日

投递方式：https://yunfan.example.com/careers
"""


def import_and_confirm(
    client: TestClient,
    *,
    raw_text: str = ANNOUNCEMENT_TEXT,
    company_type: str | None = "民企",
    overrides: dict[str, object] | None = None,
    user_id: str = "demo-user",
) -> dict[str, object]:
    headers = {"X-User-ID": user_id}
    imported = client.post(
        "/api/v1/workspace/jobs/import/text",
        json={"raw_text": raw_text},
        headers=headers,
    )
    assert imported.status_code == 201, imported.text
    draft = imported.json()["parsed"]

    payload: dict[str, object] = {
        "title": draft["title"],
        "company_name": draft["company_name"],
        "company_type": company_type,
        "recruitment_type": draft["recruitment_type"],
        "target_cohort": draft["target_cohort"],
        "locations": draft["locations"],
        "positions": [{"title": title, "city": "上海"} for title in draft["positions"]],
        "deadline_text": draft["deadline_text"],
        "deadline_at": (draft["deadline_at"] or "")[:10] or None,
        "apply_method": draft["apply_method"],
    }
    payload.update(overrides or {})

    confirmed = client.post(
        f"/api/v1/workspace/jobs/imports/{imported.json()['id']}/confirm",
        json=payload,
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def test_text_import_parses_announcement_fields(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workspace/jobs/import/text", json={"raw_text": ANNOUNCEMENT_TEXT}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    draft = body["parsed"]
    assert body["status"] == "parsed_rule"
    assert body["llm_used"] is False
    assert draft["company_name"] == "星河智能"
    assert draft["title"] == "星河智能2027届校园招聘公告"
    assert draft["recruitment_type"] == "秋招"
    assert draft["target_cohort"] == "2027届"
    assert draft["locations"] == ["上海", "深圳", "杭州"]
    assert draft["positions"] == ["后端开发工程师", "算法工程师", "前端开发工程师"]
    assert draft["deadline_text"] == "2026-11-30"
    assert draft["apply_method"]["emails"] == ["campus@xinghe.example.com"]
    assert draft["confidence"]["company_name"] == "high"


def test_import_rejects_short_text(client: TestClient) -> None:
    response = client.post("/api/v1/workspace/jobs/import/text", json={"raw_text": "太短了"})

    assert response.status_code == 422


def test_article_import_rejects_non_wechat_url(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workspace/jobs/import/article",
        json={"url": "https://example.com/jobs/1"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "JOB_IMPORT_FAILED"


def test_confirm_creates_catalog_row_and_derived_status(client: TestClient) -> None:
    announcement = import_and_confirm(client)

    assert announcement["company"]["name"] == "星河智能"
    assert announcement["company"]["type"] == "民企"
    assert announcement["mark_status"] == "not_applied"
    assert len(announcement["positions"]) == 3

    listing = client.get("/api/v1/workspace/jobs")

    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["company"]["name"] == "星河智能"
    assert row["position_count"] == 3
    assert row["positions_preview"].startswith("后端开发工程师")
    assert row["deadline"]["text"] == "2026-11-30"
    assert row["mark_status_label"] == "未投递"
    assert row["applied_position_count"] == 0


def test_confirm_twice_conflicts(client: TestClient) -> None:
    import_and_confirm(client)
    imported = client.post(
        "/api/v1/workspace/jobs/import/text", json={"raw_text": ANNOUNCEMENT_TEXT}
    ).json()
    draft = imported["parsed"]

    response = client.post(
        f"/api/v1/workspace/jobs/imports/{imported['id']}/confirm",
        json={
            "title": draft["title"],
            "company_name": draft["company_name"],
            "target_cohort": draft["target_cohort"],
            "positions": [{"title": "后端开发工程师"}],
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "JOB_ANNOUNCEMENT_EXISTS"


def test_list_filters_by_company_type_recruitment_type_and_location(client: TestClient) -> None:
    import_and_confirm(client)
    import_and_confirm(
        client,
        raw_text=SECOND_TEXT,
        company_type="国企",
        overrides={
            "company_name": "云帆数据",
            "title": "云帆数据2026届春季招聘",
            "recruitment_type": "春招",
            "target_cohort": "2026届",
            "locations": ["北京"],
            "positions": [{"title": "数据分析师", "category": "数据"}],
        },
    )

    assert client.get("/api/v1/workspace/jobs").json()["total"] == 2
    assert (
        client.get("/api/v1/workspace/jobs", params={"company_type": "国企"}).json()["total"] == 1
    )
    assert (
        client.get("/api/v1/workspace/jobs", params={"recruitment_type": "秋招"}).json()["total"]
        == 1
    )
    assert client.get("/api/v1/workspace/jobs", params={"location": "深圳"}).json()["total"] == 1
    assert client.get("/api/v1/workspace/jobs", params={"job_category": "数据"}).json()["total"] == 1
    assert client.get("/api/v1/workspace/jobs", params={"keyword": "星河"}).json()["total"] == 1
    assert client.get("/api/v1/workspace/jobs", params={"company": "云帆"}).json()["total"] == 1


def test_create_applications_from_positions_and_derive_row_status(client: TestClient) -> None:
    announcement = import_and_confirm(client)
    position_ids = [item["id"] for item in announcement["positions"][:2]]

    created = client.post(
        "/api/v1/workspace/applications",
        json={
            "announcement_id": announcement["id"],
            "position_ids": position_ids,
            "status": "applied",
            "channel": "官网",
        },
    )

    assert created.status_code == 201, created.text
    assert created.json()["total"] == 2
    assert all(item["job_id"] is None for item in created.json()["items"])
    assert created.json()["items"][0]["company_name"] == "星河智能"

    row = client.get("/api/v1/workspace/jobs").json()["items"][0]
    assert row["mark_status"] == "applied"
    assert row["mark_status_label"] == "已投递"
    assert row["applied_position_count"] == 2
    assert row["stage_summary"] == {"已投递": 2}

    duplicate = client.post(
        "/api/v1/workspace/applications",
        json={"announcement_id": announcement["id"], "position_ids": position_ids[:1]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "APPLICATION_EXISTS"


def test_filter_by_derived_status(client: TestClient) -> None:
    announcement = import_and_confirm(client)
    client.post(
        "/api/v1/workspace/applications",
        json={
            "announcement_id": announcement["id"],
            "position_ids": [announcement["positions"][0]["id"]],
            "status": "applied",
        },
    )

    assert client.get("/api/v1/workspace/jobs", params={"status": "applied"}).json()["total"] == 1
    assert client.get("/api/v1/workspace/jobs", params={"status": "not_applied"}).json()["total"] == 0
    assert client.get("/api/v1/workspace/jobs", params={"status": "offer"}).json()["total"] == 0


def test_deferred_mark_hides_and_can_be_filtered_back(client: TestClient) -> None:
    announcement = import_and_confirm(client)

    marked = client.patch(
        f"/api/v1/workspace/jobs/{announcement['id']}/mark",
        json={"status": "deferred", "note": "等春招"},
    )

    assert marked.status_code == 200
    assert marked.json()["mark_status"] == "deferred"
    assert marked.json()["note"] == "等春招"

    deferred = client.get("/api/v1/workspace/jobs", params={"status": "deferred"}).json()
    assert deferred["total"] == 1
    assert deferred["items"][0]["mark_note"] == "等春招"
    assert client.get("/api/v1/workspace/jobs", params={"status": "not_applied"}).json()["total"] == 0

    cleared = client.patch(
        f"/api/v1/workspace/jobs/{announcement['id']}/mark", json={"status": "none"}
    )
    assert cleared.status_code == 200
    assert cleared.json()["mark_status"] == "not_applied"


def test_facets_return_counts(client: TestClient) -> None:
    import_and_confirm(client)

    response = client.get("/api/v1/workspace/jobs/filters")

    assert response.status_code == 200
    body = response.json()
    recruitment = {item["value"]: item["count"] for item in body["recruitment_types"]}
    assert recruitment["秋招"] == 1
    assert recruitment["春招"] == 0
    locations = {item["value"]: item["count"] for item in body["locations"]}
    assert locations == {"上海": 1, "深圳": 1, "杭州": 1}
    statuses = {item["value"]: item["count"] for item in body["statuses"]}
    assert statuses["not_applied"] == 1


def test_table_preference_roundtrip_and_validation(client: TestClient) -> None:
    initial = client.get("/api/v1/workspace/preferences/job-table")

    assert initial.status_code == 200
    assert "company_name" in initial.json()["visible_columns"]
    assert len(initial.json()["available_columns"]) == 11

    saved = client.put(
        "/api/v1/workspace/preferences/job-table",
        json={"visible_columns": ["company_name", "positions", "mark_status"]},
    )
    assert saved.status_code == 200
    assert saved.json()["visible_columns"] == ["company_name", "positions", "mark_status"]
    assert client.get("/api/v1/workspace/preferences/job-table").json()["visible_columns"] == [
        "company_name",
        "positions",
        "mark_status",
    ]

    assert (
        client.put(
            "/api/v1/workspace/preferences/job-table", json={"visible_columns": []}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/v1/workspace/preferences/job-table",
            json={"visible_columns": ["unknown"]},
        ).status_code
        == 422
    )


def test_export_csv_contains_catalog_row(client: TestClient) -> None:
    import_and_confirm(client)

    response = client.get("/api/v1/workspace/jobs/export")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    lines = response.text.splitlines()
    assert lines[0].startswith("公司名称")
    assert "星河智能" in lines[1]


def test_catalog_is_isolated_by_user(client: TestClient) -> None:
    import_and_confirm(client, user_id="user-a")

    assert client.get("/api/v1/workspace/jobs", headers={"X-User-ID": "user-b"}).json()["total"] == 0
    assert client.get("/api/v1/workspace/jobs", headers={"X-User-ID": "user-a"}).json()["total"] == 1
