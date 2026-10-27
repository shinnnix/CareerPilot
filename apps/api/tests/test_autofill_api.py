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
        "/api/v1/applications", json={"job_id": job["id"], "status": "not_applied"}
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


def test_profile_overrides_resume_and_is_labelled_profile(
    client: TestClient, job_payload
) -> None:
    """Plan §5.1: confirmed profile data wins over resume extraction."""
    application_id, resume_id = create_application(client, job_payload)
    response = client.post(
        f"/api/v1/applications/{application_id}/autofill-plan",
        json={
            "resume_document_id": resume_id,
            "profile": {
                "basic": {
                    "name": "李四",
                    "email": "lisi@example.com",
                    "phone": "13900001111",
                    "city": "北京",
                },
                "education": [{"school": "浙江大学", "major": "软件工程", "degree": "本科"}],
                "links": {"github": "https://github.com/lisi"},
            },
            "fields": [
                {"field_id": "email", "label": "Email", "field_type": "email"},
                {"field_id": "phone", "label": "手机号", "field_type": "tel"},
                {"field_id": "city", "label": "工作城市", "field_type": "text"},
                {"field_id": "school", "label": "毕业院校", "field_type": "text"},
                {"field_id": "gh", "label": "GitHub", "field_type": "url"},
            ],
        },
    )

    assert response.status_code == 200
    fields = {item["field_id"]: item for item in response.json()["fields"]}
    assert fields["email"]["value"] == "lisi@example.com"
    assert fields["email"]["source_type"] == "profile"
    assert fields["email"]["confidence"] == 0.99
    assert fields["phone"]["value"] == "13900001111"
    assert fields["city"]["value"] == "北京"
    assert fields["school"]["value"] == "浙江大学"
    assert fields["gh"]["value"] == "https://github.com/lisi"


def test_profile_name_never_fills_company_or_recruiter_boxes(
    client: TestClient, job_payload
) -> None:
    application_id, resume_id = create_application(client, job_payload)
    response = client.post(
        f"/api/v1/applications/{application_id}/autofill-plan",
        json={
            "resume_document_id": resume_id,
            "profile": {"basic": {"name": "李四"}},
            "fields": [
                {"field_id": "name", "label": "姓名", "field_type": "text"},
                {"field_id": "company", "label": "公司名称", "field_type": "text"},
                {"field_id": "recruiter", "label": "Recruiter name", "field_type": "text"},
            ],
        },
    )

    assert response.status_code == 200
    fields = {item["field_id"]: item for item in response.json()["fields"]}
    assert fields["name"]["value"] == "李四"
    assert fields["name"]["source_type"] == "profile"
    assert fields["company"]["value"] != "李四"
    assert fields["recruiter"]["value"] != "李四"


def test_profile_is_ignored_when_absent(client: TestClient, job_payload) -> None:
    application_id, resume_id = create_application(client, job_payload)
    response = client.post(
        f"/api/v1/applications/{application_id}/autofill-plan",
        json={
            "resume_document_id": resume_id,
            "fields": [{"field_id": "email", "label": "Email", "field_type": "email"}],
        },
    )

    assert response.status_code == 200
    field = response.json()["fields"][0]
    assert field["value"] == "zhangsan@example.com"
    assert field["source_type"] == "resume"
