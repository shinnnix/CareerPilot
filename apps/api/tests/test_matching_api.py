from fastapi.testclient import TestClient


def create_resume(client: TestClient, *, city: str = "上海") -> str:
    response = client.post(
        "/api/v1/documents/text",
        json={
            "display_name": "候选人简历",
            "document_type": "resume",
            "raw_text": (
                f"期望城市：{city}\n每周可实习 5 天\n可实习 6 个月\n"
                "## 专业技能\nPython、FastAPI、检索增强生成、Vue 3\n"
                "## 项目经历\n使用 FastAPI 和 RAG 构建带引用的私人知识库。"
            ),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_job(client: TestClient, job_payload: dict[str, object]) -> str:
    response = client.post("/api/v1/jobs", json=job_payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_match_report_explains_score_and_evidence(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    resume_id = create_resume(client)
    job_id = create_job(client, job_payload)
    client.post("/api/v1/retrieval/index", json={"document_id": resume_id})

    response = client.post(
        f"/api/v1/jobs/{job_id}/match",
        json={"resume_document_id": resume_id},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["eligible"] is True
    assert report["total_score"] > 50
    assert {"python", "fastapi", "rag"} <= set(report["matched_required_skills"])
    assert report["breakdown"]["required_skill_coverage"] == 1.0
    assert report["evidence"]
    assert report["scoring_version"] == "explainable-match-v1"


def test_hard_gate_blocks_city_mismatch(client: TestClient, job_payload: dict[str, object]) -> None:
    resume_id = create_resume(client, city="北京")
    job_id = create_job(client, job_payload)
    response = client.post(
        f"/api/v1/jobs/{job_id}/match",
        json={"resume_document_id": resume_id},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["eligible"] is False
    assert report["total_score"] == 0
    assert report["hard_gate"]["checks"]["city"] is False


def test_match_rejects_non_resume_document(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    document = client.post(
        "/api/v1/documents/text",
        json={
            "display_name": "学习笔记",
            "document_type": "learning_note",
            "raw_text": "## FastAPI\n这是一份用于测试匹配类型校验的学习笔记。",
        },
    ).json()
    job_id = create_job(client, job_payload)
    response = client.post(
        f"/api/v1/jobs/{job_id}/match",
        json={"resume_document_id": document["id"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "RESUME_REQUIRED"
