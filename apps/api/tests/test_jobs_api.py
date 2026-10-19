from fastapi.testclient import TestClient


def create_job(
    client: TestClient,
    payload: dict[str, object],
    *,
    user_id: str = "demo-user",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/jobs",
        json=payload,
        headers={"X-User-ID": user_id},
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_get_job(client: TestClient, job_payload: dict[str, object]) -> None:
    created = create_job(client, job_payload)

    response = client.get(f"/api/v1/jobs/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "AI 应用开发实习生"
    assert response.headers["X-Request-ID"].startswith("req_")


def test_list_search_filter_and_pagination(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    create_job(client, job_payload)
    second = {
        **job_payload,
        "title": "后端开发实习生",
        "company_name": "另一家公司",
        "city": "北京",
        "raw_text": "负责 Python Web 服务开发、测试与数据库维护，参与团队代码评审。",
    }
    create_job(client, second)

    response = client.get(
        "/api/v1/jobs",
        params={"keyword": "RAG", "city": "上海", "page": 1, "page_size": 10},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert result["items"][0]["company_name"] == "示例科技"
    assert result["page"] == 1
    assert result["page_size"] == 10


def test_patch_job(client: TestClient, job_payload: dict[str, object]) -> None:
    created = create_job(client, job_payload)

    response = client.patch(
        f"/api/v1/jobs/{created['id']}",
        json={
            "city": "杭州",
            "required_skills": ["Python", "FastAPI", "Vue 3"],
            "salary_min": "250",
        },
    )

    assert response.status_code == 200
    assert response.json()["city"] == "杭州"
    assert response.json()["salary_min"] == "250.00"


def test_delete_job(client: TestClient, job_payload: dict[str, object]) -> None:
    created = create_job(client, job_payload)

    delete_response = client.delete(f"/api/v1/jobs/{created['id']}")
    get_response = client.get(f"/api/v1/jobs/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
    assert get_response.json()["code"] == "JOB_NOT_FOUND"
    assert get_response.json()["request_id"].startswith("req_")


def test_jobs_are_isolated_by_user(client: TestClient, job_payload: dict[str, object]) -> None:
    created = create_job(client, job_payload, user_id="user-a")

    response = client.get(
        f"/api/v1/jobs/{created['id']}",
        headers={"X-User-ID": "user-b"},
    )

    assert response.status_code == 404


def test_rejects_invalid_job(client: TestClient, job_payload: dict[str, object]) -> None:
    invalid = {**job_payload, "salary_min": "500", "salary_max": "100"}

    response = client.post("/api/v1/jobs", json=invalid)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["request_id"].startswith("req_")


def test_patch_rejects_null_for_required_field(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    created = create_job(client, job_payload)

    response = client.patch(
        f"/api/v1/jobs/{created['id']}",
        json={"title": None},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_openapi_contains_job_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/jobs" in paths
    assert "/api/v1/jobs/{job_id}" in paths


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
