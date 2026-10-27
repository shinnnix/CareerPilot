"""AI settings + assistant chat (plan §5.3 / §5.3.5).

A throwaway local HTTP server plays the role of both providers so the tests
cover the real transport (urllib, timeouts, retries, headers) instead of
mocking it away.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from app.domains.ai.metrics import ai_metrics
from app.domains.ai.schemas import AI_CONFIG_HEADER, AiConfig, encode_ai_config

SECRET = "sk-test-do-not-leak"


class _StubHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI/Anthropic stand-in.

    ``/chat/completions`` echoes the OpenAI shape, ``/v1/messages`` the
    Anthropic one. Any path containing ``unauthorized`` answers 401.
    """

    received: ClassVar[list[dict[str, object]]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        type(self).received.append(
            {
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": body,
            }
        )
        if "unauthorized" in self.path:
            self._respond(401, {"error": {"message": "invalid api key"}})
            return
        if self.path.endswith("/chat/completions"):
            self._respond(200, {"choices": [{"message": {"content": "pong-openai"}}]})
            return
        if self.path.endswith("/v1/messages"):
            self._respond(
                200,
                {"content": [{"type": "text", "text": "pong-anthropic"}]},
            )
            return
        self._respond(404, {"error": {"message": "not found"}})

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
def stub_base_url() -> Generator[str, None, None]:
    _StubHandler.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def reset_ai_metrics() -> Generator[None, None, None]:
    ai_metrics.reset()
    yield
    ai_metrics.reset()


def _config(base_url: str, **overrides: object) -> AiConfig:
    payload: dict[str, object] = {
        "format": "openai",
        "base_url": base_url,
        "model": "gpt-4o-mini",
        "api_key": SECRET,
    }
    payload.update(overrides)
    return AiConfig.model_validate(payload)


def test_openai_connection_uses_chat_completions(client: TestClient, stub_base_url: str) -> None:
    response = client.post("/api/v1/workspace/settings/ai/test", json=_config(stub_base_url).model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reply"] == "pong-openai"
    assert body["format"] == "openai"
    sent = _StubHandler.received[-1]
    assert sent["path"] == "/chat/completions"
    assert sent["headers"]["authorization"] == f"Bearer {SECRET}"


def test_anthropic_connection_uses_messages_endpoint(
    client: TestClient, stub_base_url: str
) -> None:
    config = _config(stub_base_url, format="anthropic", model="claude-3-5-sonnet")

    response = client.post("/api/v1/workspace/settings/ai/test", json=config.model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reply"] == "pong-anthropic"
    sent = _StubHandler.received[-1]
    assert sent["path"] == "/v1/messages"
    assert sent["headers"]["x-api-key"] == SECRET
    assert sent["headers"]["anthropic-version"] == "2023-06-01"
    # Anthropic rejects ``system`` inside messages and requires max_tokens.
    assert "max_tokens" in sent["body"]


def test_bad_credentials_return_ok_false_with_hint(
    client: TestClient, stub_base_url: str
) -> None:
    config = _config(f"{stub_base_url}/unauthorized")

    response = client.post("/api/v1/workspace/settings/ai/test", json=config.model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "401" in body["error"]
    assert "凭据被拒绝" in body["hint"]
    # A rejected key is not retried.
    assert len(_StubHandler.received) == 1


def test_echo_reports_config_without_the_key(client: TestClient) -> None:
    config = _config("http://127.0.0.1:9999")

    response = client.get(
        "/api/v1/workspace/settings/ai/echo",
        headers={AI_CONFIG_HEADER: encode_ai_config(config)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["model"] == "gpt-4o-mini"
    assert SECRET not in json.dumps(body)


def test_echo_tolerates_malformed_header(client: TestClient) -> None:
    response = client.get(
        "/api/v1/workspace/settings/ai/echo",
        headers={AI_CONFIG_HEADER: "not-base64!!"},
    )

    assert response.status_code == 200
    assert response.json() == {"configured": False}


def test_metrics_count_successful_calls(client: TestClient, stub_base_url: str) -> None:
    client.post("/api/v1/workspace/settings/ai/test", json=_config(stub_base_url).model_dump())

    response = client.get("/api/v1/workspace/settings/ai/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["calls"] == 1
    assert body["failures"] == 0
    assert body["by_format"] == {"openai": 1}


def test_assistant_chat_without_credentials_returns_409(client: TestClient) -> None:
    response = client.post("/api/v1/workspace/assistant/chat", json={"message": "帮我看看简历"})

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "AI_CREDENTIALS_MISSING"
    assert body["details"]["hint"]


def test_assistant_chat_with_credentials_answers(client: TestClient, stub_base_url: str) -> None:
    config = _config(stub_base_url)

    response = client.post(
        "/api/v1/workspace/assistant/chat",
        json={"message": "帮我看看简历", "history": [{"role": "user", "content": "你好"}]},
        headers={AI_CONFIG_HEADER: encode_ai_config(config)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "pong-openai"
    assert body["model"] == "gpt-4o-mini"
    sent = _StubHandler.received[-1]["body"]
    assert sent["messages"][0]["role"] == "system"
    assert sent["messages"][-1]["content"] == "帮我看看简历"


def test_assistant_chat_upstream_failure_returns_502(
    client: TestClient, stub_base_url: str
) -> None:
    config = _config(f"{stub_base_url}/unauthorized")

    response = client.post(
        "/api/v1/workspace/assistant/chat",
        json={"message": "帮我看看简历"},
        headers={AI_CONFIG_HEADER: encode_ai_config(config)},
    )

    assert response.status_code == 502
    assert response.json()["code"] == "AI_CALL_FAILED"
