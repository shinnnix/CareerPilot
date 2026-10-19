from fastapi.testclient import TestClient


def create_job(client: TestClient, job_payload: dict[str, object], *, title: str) -> str:
    payload = {**job_payload, "title": title}
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_read_only_agent_run_completes_and_replays_sse(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    create_job(client, job_payload, title="RAG Agent 实习生")
    response = client.post(
        "/api/v1/agent/runs",
        json={
            "message": "帮我找 RAG 实习",
            "intent": "job_search",
            "query": "RAG",
        },
    )
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["result"]["total"] == 1

    stream = client.get(f"/api/v1/agent/runs/{run['id']}/events")
    assert stream.status_code == 200
    assert "event: intent_routed" in stream.text
    assert "event: run_completed" in stream.text
    assert "event: stream_end" in stream.text

    resumed_stream = client.get(
        f"/api/v1/agent/runs/{run['id']}/events",
        headers={"Last-Event-ID": "3"},
    )
    assert "id: 1\n" not in resumed_stream.text


def test_write_tool_waits_for_confirmation_and_is_idempotent(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    job_id = create_job(client, job_payload, title="需要确认的职位")
    run_request = {
        "message": "把这个职位加入申请看板",
        "intent": "create_application",
        "job_id": job_id,
    }
    first = client.post("/api/v1/agent/runs", json=run_request)
    assert first.status_code == 200
    assert first.json()["status"] == "waiting_confirmation"
    assert first.json()["result"] is None

    confirmed = client.post(
        f"/api/v1/agent/runs/{first.json()['id']}/confirm",
        json={"approved": True, "idempotency_key": "create-job-0001"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "completed"
    application_id = confirmed.json()["result"]["id"]

    second = client.post("/api/v1/agent/runs", json=run_request).json()
    replayed = client.post(
        f"/api/v1/agent/runs/{second['id']}/confirm",
        json={"approved": True, "idempotency_key": "create-job-0001"},
    )
    assert replayed.status_code == 200
    assert replayed.json()["result"]["id"] == application_id
    assert client.get("/api/v1/applications").json()["total"] == 1


def test_rejected_confirmation_has_no_side_effect(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    job_id = create_job(client, job_payload, title="拒绝写入的职位")
    run = client.post(
        "/api/v1/agent/runs",
        json={
            "message": "创建申请",
            "intent": "create_application",
            "job_id": job_id,
        },
    ).json()
    rejected = client.post(
        f"/api/v1/agent/runs/{run['id']}/confirm",
        json={"approved": False, "idempotency_key": "reject-job-0001"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "cancelled"
    assert client.get("/api/v1/applications").json()["total"] == 0


def test_agent_enforces_max_steps(client: TestClient, job_payload: dict[str, object]) -> None:
    create_job(client, job_payload, title="步骤限制职位")
    response = client.post(
        "/api/v1/agent/runs",
        json={
            "message": "找 RAG 职位",
            "intent": "job_search",
            "query": "RAG",
            "max_steps": 3,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "MAX_STEPS_EXCEEDED"


def test_agent_reports_missing_tool_inputs_as_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agent/runs",
        json={"message": "分析匹配", "intent": "match_report"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "AGENT_INPUT_MISSING"
    assert set(response.json()["details"]["missing"]) == {
        "job_id",
        "resume_document_id",
    }


def test_write_resume_cannot_bypass_max_steps(
    client: TestClient, job_payload: dict[str, object]
) -> None:
    job_id = create_job(client, job_payload, title="写操作步骤限制")
    run = client.post(
        "/api/v1/agent/runs",
        json={
            "message": "创建申请",
            "intent": "create_application",
            "job_id": job_id,
            "max_steps": 3,
        },
    ).json()
    response = client.post(
        f"/api/v1/agent/runs/{run['id']}/confirm",
        json={"approved": True, "idempotency_key": "limited-job-0001"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "MAX_STEPS_EXCEEDED"
    assert client.get("/api/v1/applications").json()["total"] == 0
