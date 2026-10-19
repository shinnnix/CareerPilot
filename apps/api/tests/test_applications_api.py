from fastapi.testclient import TestClient


def create_job(client: TestClient, job_payload: dict[str, object]) -> str:
    response = client.post("/api/v1/jobs", json=job_payload)
    assert response.status_code == 201
    return response.json()["id"]


def create_resume(client: TestClient) -> str:
    response = client.post(
        "/api/v1/documents/text",
        json={
            "display_name": "申请用简历",
            "document_type": "resume",
            "raw_text": (
                "期望城市：上海\n每周可实习 5 天\n可实习 6 个月\n"
                "## 专业技能\nPython、FastAPI、RAG\n"
                "## 项目经历\n使用 FastAPI 和检索增强生成开发带引用的知识库。"
            ),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_application_board_timeline_and_transition_rules(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    job_id = create_job(client, job_payload)
    created = client.post(
        "/api/v1/applications",
        json={"job_id": job_id, "status": "saved", "notes": "重点岗位"},
    )
    assert created.status_code == 201
    application_id = created.json()["id"]

    duplicate = client.post("/api/v1/applications", json={"job_id": job_id})
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "APPLICATION_EXISTS"

    blocked_delete = client.delete(f"/api/v1/jobs/{job_id}")
    assert blocked_delete.status_code == 409
    assert blocked_delete.json()["code"] == "JOB_HAS_APPLICATION"

    updated = client.patch(
        f"/api/v1/applications/{application_id}",
        json={"status": "applied", "event_note": "官网投递完成"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "applied"
    assert updated.json()["applied_at"] is not None
    assert [event["event_type"] for event in updated.json()["events"]] == [
        "created",
        "status_changed",
    ]

    invalid = client.patch(f"/api/v1/applications/{application_id}", json={"status": "saved"})
    assert invalid.status_code == 409
    assert invalid.json()["code"] == "INVALID_APPLICATION_TRANSITION"

    board = client.get("/api/v1/applications?status=applied")
    assert board.status_code == 200
    assert board.json()["total"] == 1
    assert board.json()["items"][0]["company_name"] == "示例科技"


def test_application_and_feedback_are_user_scoped(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    job_id = create_job(client, job_payload)
    application = client.post("/api/v1/applications", json={"job_id": job_id}).json()
    forbidden = client.get(
        f"/api/v1/applications/{application['id']}",
        headers={"X-User-ID": "other-user"},
    )
    assert forbidden.status_code == 404

    feedback = client.put(
        f"/api/v1/jobs/{job_id}/feedback",
        json={"relevant": True, "reason": "技术栈匹配"},
    )
    assert feedback.status_code == 200
    changed = client.put(
        f"/api/v1/jobs/{job_id}/feedback",
        json={"relevant": False, "reason": "实习时间不匹配"},
    )
    assert changed.status_code == 200
    assert changed.json()["relevant"] is False


def test_personalization_only_saves_items_with_valid_citations(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    job_id = create_job(client, job_payload)
    resume_id = create_resume(client)
    client.post("/api/v1/retrieval/index", json={"document_id": resume_id})

    response = client.post(
        f"/api/v1/jobs/{job_id}/personalization",
        json={"resume_document_id": resume_id},
    )
    assert response.status_code == 200, response.json()
    result = response.json()
    assert result["resume_bullets"]["citation_valid"] is True
    assert result["skill_gap_plan"]["citation_valid"] is True
    assert result["resume_bullets"]["content"][0]["citations"][0]["source_type"] == "document_chunk"
