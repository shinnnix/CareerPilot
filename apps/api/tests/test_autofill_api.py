from fastapi.testclient import TestClient


def create_application(client: TestClient, job_payload: dict[str, object]) -> tuple[str, str]:
    job = client.post("/api/v1/jobs", json=job_payload).json()
    resume = client.post(
        "/api/v1/documents/text",
        json={
            "display_name": "自动填写简历",
            "document_type": "resume",
            "raw_text": (
                "张三\n邮箱：zhangsan@example.com\n手机：13812345678\n"
                "城市：上海\n\n项目经历\n使用 Python 和 FastAPI 构建求职系统。"
            ),
        },
    ).json()
    application = client.post(
        "/api/v1/applications", json={"job_id": job["id"], "status": "preparing"}
    ).json()
    return application["id"], resume["id"]


def test_autofill_plan_is_reviewable_and_source_bound(client: TestClient, job_payload) -> None:
    application_id, resume_id = create_application(client, job_payload)
    response = client.post(
        f"/api/v1/applications/{application_id}/autofill-plan",
        json={
            "resume_document_id": resume_id,
            "fields": [
                {"field_id": "email", "label": "Email", "field_type": "email", "required": True},
                {"field_id": "phone", "label": "手机", "field_type": "tel"},
                {"field_id": "city", "label": "工作城市", "field_type": "text"},
                {"field_id": "why", "label": "Why this role?", "field_type": "textarea"},
                {"field_id": "resume", "label": "Resume upload", "field_type": "file"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ready_count"] == 3
    assert body["review_count"] == 2
    fields = {item["field_id"]: item for item in body["fields"]}
    assert fields["email"]["value"] == "zhangsan@example.com"
    assert fields["email"]["status"] == "ready"
    assert fields["email"]["source_id"] == resume_id
    assert fields["why"]["value"] is None
    assert fields["why"]["status"] == "review"
    assert fields["resume"]["status"] == "unsupported"


def test_autofill_plan_rejects_non_resume_document(client: TestClient, job_payload) -> None:
    job = client.post("/api/v1/jobs", json=job_payload).json()
    document = client.post(
        "/api/v1/documents/text",
        json={
            "display_name": "职位材料",
            "document_type": "job_description",
            "raw_text": "职位描述\n需要 Python 和 FastAPI，工作地点：上海。",
        },
    ).json()
    application = client.post("/api/v1/applications", json={"job_id": job["id"]}).json()
    response = client.post(
        f"/api/v1/applications/{application['id']}/autofill-plan",
        json={"resume_document_id": document["id"], "fields": [{"field_id": "email", "label": "Email"}]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "RESUME_REQUIRED"
