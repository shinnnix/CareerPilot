"""Regression tests for the six fixes (export auth, SSRF, catalog↔resume,
SQL status filter, robots.txt)."""

from fastapi.testclient import TestClient

from app.domains.ai.security import BaseUrlRejected, validate_base_url
from app.domains.jobs.adapters import wechat_article

ANNOUNCEMENT_TEXT = """星河智能 2027 届校园招聘公告
公司：星河智能

任职要求：
- 熟悉 Python、FastAPI 与 RAG

加分项：
- 了解 LangGraph
"""

RESUME_TEXT = """张三
13800000000
zhangsan@example.com

项目经历
简历助手 | 技术栈：Python、FastAPI
- 负责检索链路与评测脚本。

专业技能
- 熟练使用 Python 与 FastAPI。
"""


def import_announcement(client: TestClient) -> dict[str, object]:
    imported = client.post(
        "/api/v1/workspace/jobs/import/text",
        json={"raw_text": ANNOUNCEMENT_TEXT, "source_name": "星河智能招聘"},
    )
    assert imported.status_code == 201, imported.text
    payload = imported.json()
    confirmed = client.post(
        f"/api/v1/workspace/jobs/imports/{payload['id']}/confirm",
        json={
            "company_name": "星河智能",
            "title": "星河智能 2027 届校园招聘公告",
            "recruitment_type": "秋招",
            "target_cohort": "2027届",
            "locations": ["上海"],
            "positions": [
                {"title": "后端开发工程师", "category": "研发"},
                {"title": "算法工程师", "category": "算法"},
            ],
            "raw_text": ANNOUNCEMENT_TEXT,
            "deadline_text": "招满为止",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def create_resume(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/resumes/import/text",
        json={"display_name": "我的简历", "raw_text": RESUME_TEXT},
    )
    assert response.status_code == 201, response.text
    return response.json()


# -- fix 3/4: resume targets and optimises against a catalog announcement ----


def test_resume_can_target_an_announcement(client: TestClient) -> None:
    announcement = import_announcement(client)
    resume = create_resume(client)

    updated = client.patch(
        f"/api/v1/resumes/{resume['id']}",
        json={"target_announcement_id": announcement["id"]},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["target_announcement_id"] == announcement["id"]
    listed = client.get("/api/v1/resumes").json()["items"][0]
    assert listed["target_announcement_id"] == announcement["id"]


def test_resume_rejects_foreign_announcement_target(client: TestClient) -> None:
    announcement = import_announcement(client)
    resume = create_resume(client)

    response = client.patch(
        f"/api/v1/resumes/{resume['id']}",
        json={"target_announcement_id": announcement["id"]},
        headers={"X-User-ID": "someone-else"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "RESUME_NOT_FOUND"


def test_optimization_uses_announcement_as_jd(client: TestClient) -> None:
    announcement = import_announcement(client)
    resume = create_resume(client)

    response = client.post(
        f"/api/v1/resumes/{resume['id']}/optimizations",
        json={"announcement_id": announcement["id"]},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["match_report"]["source"] == "announcement"
    assert payload["announcement_id"] == announcement["id"]
    assert payload["jd"]["announcement_id"] == announcement["id"]
    assert "python" in payload["match_report"]["matched_required_skills"]
    citation_types = {
        citation["source_type"]
        for item in payload["suggestions"]
        for citation in item["citations"]
    }
    assert citation_types <= {"resume_entry", "resume_head", "announcement"}


def test_optimization_rejects_unknown_announcement(client: TestClient) -> None:
    resume = create_resume(client)

    response = client.post(
        f"/api/v1/resumes/{resume['id']}/optimizations",
        json={"announcement_id": "missing-announcement"},
    )

    assert response.status_code == 404


# -- fix 5: status filter runs in SQL (count + page stay consistent) ---------


def test_derived_status_filter_counts_pages_in_sql(client: TestClient) -> None:
    announcement = import_announcement(client)
    positions = client.get(f"/api/v1/workspace/jobs/{announcement['id']}").json()["positions"]
    client.post(
        "/api/v1/workspace/applications",
        json={
            "announcement_id": announcement["id"],
            "position_ids": [positions[0]["id"]],
            "status": "applied",
        },
    )

    filtered = client.get(
        "/api/v1/workspace/jobs",
        params={"status": "applied", "page": 1, "page_size": 1},
    ).json()
    empty = client.get(
        "/api/v1/workspace/jobs",
        params={"status": "offer", "page": 1, "page_size": 1},
    ).json()

    assert filtered["total"] == 1
    assert filtered["items"][0]["mark_status"] == "applied"
    assert empty["total"] == 0
    facets = client.get("/api/v1/workspace/jobs/filters").json()
    counts = {item["value"]: item["count"] for item in facets["statuses"]}
    assert counts["applied"] == 1
    assert counts["not_applied"] == 0


# -- fix 2: outbound base_url guard (SSRF) -----------------------------------


def test_base_url_guard_blocks_metadata_and_bad_schemes() -> None:
    for bad in (
        "http://169.254.169.254/latest",
        "ftp://api.example.com/v1",
        "http://metadata.google.internal/v1",
        "http://127.0.0.1.nip.invalidx/v1",
    ):
        try:
            validate_base_url(bad)
        except BaseUrlRejected:
            continue
        raise AssertionError(f"expected rejection: {bad}")


def test_base_url_guard_allows_loopback_for_local_models() -> None:
    assert validate_base_url("http://127.0.0.1:11434/v1") == "http://127.0.0.1:11434/v1"


def test_ai_test_endpoint_rejects_metadata_target(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workspace/settings/ai/test",
        json={
            "format": "openai",
            "base_url": "http://169.254.169.254/latest",
            "model": "gpt-4o-mini",
            "api_key": "sk-test",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


# -- fix 6: robots.txt -------------------------------------------------------


MP_ROBOTS = """User-agent: *
Allow: /$
Allow: /debug/
Disallow: /
"""


def test_robots_parser_matches_wechat_rules() -> None:
    rules = wechat_article.parse_robots(MP_ROBOTS)

    assert wechat_article.is_allowed_by_robots("/", rules) is True
    assert wechat_article.is_allowed_by_robots("/debug/x", rules) is True
    assert wechat_article.is_allowed_by_robots("/s/AbCdEf", rules) is False


def test_article_import_refuses_when_robots_disallows(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        wechat_article,
        "_robots_cache",
        {wechat_article.ROBOTS_URL: (float("inf"), MP_ROBOTS)},
    )

    response = client.post(
        "/api/v1/workspace/jobs/import/article",
        json={"url": "https://mp.weixin.qq.com/s/AbCdEf"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "JOB_IMPORT_ROBOTS_DISALLOWED"
    assert "CAREERPILOT_WECHAT_RESPECT_ROBOTS" in response.json()["message"]


def test_robots_guard_can_be_disabled_by_config(monkeypatch) -> None:
    settings = wechat_article.get_settings()
    monkeypatch.setattr(settings, "wechat_respect_robots", False)
    monkeypatch.setattr(
        wechat_article,
        "_robots_rules",
        lambda timeout: [wechat_article.RobotsRule(allow=False, pattern="/")],
    )

    # Disallowed path, but the operator explicitly opted out: no exception.
    wechat_article._ensure_robots_allowed("https://mp.weixin.qq.com/s/AbCdEf", timeout=1)


# -- remaining audit items ---------------------------------------------------


def test_llm_conflicts_keep_rule_value_and_are_flagged(monkeypatch) -> None:
    """§2.7.1: disagreements are surfaced, never silently overwritten."""

    from app.domains.ai import extraction

    class FakeClient:
        def complete(self, messages, *, system=None, max_tokens=None) -> str:
            return (
                '{"title": "模型标题", "company_name": "模型公司",'
                ' "locations": ["北京"], "positions": ["算法工程师"]}'
            )

    monkeypatch.setattr(extraction, "build_client", lambda config: FakeClient())
    parsed = {
        "title": "规则标题",
        "company_name": "规则公司",
        "locations": ["上海"],
        "positions": [],
    }

    merged, llm_used = extraction.enhance_announcement(
        parsed, "公告正文" * 20, config=object()
    )

    assert llm_used is True  # positions was blank and got filled
    assert merged["title"] == "规则标题"
    assert merged["company_name"] == "规则公司"
    assert merged["locations"] == ["上海"]
    assert merged["positions"] == ["算法工程师"]
    assert merged["needs_review"] is True
    assert set(merged["alternatives"]) == {"title", "company_name", "locations"}
    assert merged["alternatives"]["company_name"] == {
        "rule": "规则公司",
        "llm": "模型公司",
    }


def test_legacy_application_create_still_snapshots_company(
    client: TestClient, session_factory
) -> None:
    """Old /applications endpoint keeps rendering after the jobs row goes away."""

    from app.domains.applications.model import Application

    job = client.post(
        "/api/v1/jobs",
        json={
            "title": "后端开发实习生",
            "company_name": "星河智能",
            "city": "上海",
            "raw_text": "负责 FastAPI 接口开发与测试，每周到岗 4 天。",
        },
    ).json()
    created = client.post("/api/v1/applications", json={"job_id": job["id"]})
    assert created.status_code == 201, created.text

    with session_factory() as session:
        row = session.get(Application, created.json()["id"])
        assert row is not None
        assert row.company_name == "星河智能"
        assert row.position_title == "后端开发实习生"
