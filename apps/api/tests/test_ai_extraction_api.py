"""LLM extraction enhancement (plan §5.3.5).

Rule parsing always runs; the LLM may only fill blanks, and any failure keeps
the rule output with ``llm_used=False``.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from app.domains.ai.schemas import AI_CONFIG_HEADER, AiConfig, encode_ai_config

ANNOUNCEMENT = """某某科技有限公司 2026 届校园招聘公告

二、工作地点
上海、杭州

三、招聘流程
网申投递后统一安排笔试与面试，具体时间另行通知，请保持手机畅通。
"""

LLM_PAYLOAD = {
    "title": "LLM 编造的标题",
    "company_name": "LLM 编造的公司",
    "recruitment_type": "校招",
    "target_cohort": "2026届",
    "locations": ["北京"],
    "positions": ["后端开发实习生", "前端开发实习生"],
    "deadline_text": "2025-12-31",
}


class _ExtractionStub(BaseHTTPRequestHandler):
    mode: ClassVar[str] = "ok"

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.mode == "fail":
            self._respond(401, {"error": {"message": "invalid api key"}})
            return
        body = {
            "choices": [
                {"message": {"content": json.dumps(LLM_PAYLOAD, ensure_ascii=False)}}
            ]
        }
        self._respond(200, body)

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args: object) -> None:
        """Silence request logging."""


@pytest.fixture
def extraction_stub() -> Generator[str, None, None]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ExtractionStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _header(base_url: str) -> dict[str, str]:
    config = AiConfig(
        format="openai",
        base_url=base_url,
        model="gpt-4o-mini",
        api_key="sk-extraction",
    )
    return {AI_CONFIG_HEADER: encode_ai_config(config)}


def test_import_without_ai_config_stays_rule_only(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workspace/jobs/import/text",
        json={"raw_text": ANNOUNCEMENT, "source_name": "校招公告"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["llm_used"] is False
    assert body["status"] == "parsed_rule"


def test_import_uses_llm_only_to_fill_blanks(
    client: TestClient, extraction_stub: str
) -> None:
    _ExtractionStub.mode = "ok"

    response = client.post(
        "/api/v1/workspace/jobs/import/text",
        json={"raw_text": ANNOUNCEMENT, "source_name": "校招公告"},
        headers=_header(extraction_stub),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["llm_used"] is True
    assert body["status"] == "parsed_llm"
    parsed = body["parsed"]
    # Rule values win on conflict: the LLM's title/company/locations are ignored.
    assert parsed["title"] != LLM_PAYLOAD["title"]
    assert "上海" in parsed["locations"]
    assert "北京" not in parsed["locations"]
    # Blanks are filled from the LLM.
    assert parsed["positions"] == LLM_PAYLOAD["positions"]


def test_import_falls_back_when_llm_rejects_credentials(
    client: TestClient, extraction_stub: str
) -> None:
    _ExtractionStub.mode = "fail"
    try:
        response = client.post(
            "/api/v1/workspace/jobs/import/text",
            json={"raw_text": ANNOUNCEMENT, "source_name": "校招公告"},
            headers=_header(extraction_stub),
        )
    finally:
        _ExtractionStub.mode = "ok"

    assert response.status_code == 201
    body = response.json()
    assert body["llm_used"] is False
    assert body["status"] == "parsed_rule"
    assert body["parsed"]["positions"] == []


def test_import_ignores_malformed_ai_header(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workspace/jobs/import/text",
        json={"raw_text": ANNOUNCEMENT, "source_name": "校招公告"},
        headers={AI_CONFIG_HEADER: "not-base64!!"},
    )

    assert response.status_code == 201
    assert response.json()["llm_used"] is False
