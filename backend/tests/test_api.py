"""Tests for the FastAPI endpoints. The agent loop is replaced with a fake."""

import json

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def _parse_sse(body: str) -> list[dict]:
    events = []
    for chunk in body.strip().split("\n\n"):
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_chat_streams_events_from_agent(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    def fake_run_agent(messages):
        yield {"type": "tool_call", "name": "list_files", "arguments": {}}
        yield {"type": "tool_result", "name": "list_files", "result_preview": "[]"}
        yield {"type": "answer", "content": "Antwort."}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)

    resp = client.post("/chat", json={"messages": [{"role": "user", "content": "Hi"}]})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types == ["tool_call", "tool_result", "answer", "done"]
    assert events[2]["content"] == "Antwort."


def test_chat_emits_error_event_on_exception(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    def boom(messages):
        yield {"type": "tool_call", "name": "list_files", "arguments": {}}
        raise RuntimeError("kapow")

    monkeypatch.setattr(main, "run_agent", boom)

    resp = client.post("/chat", json={"messages": [{"role": "user", "content": "Hi"}]})
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert "error" in types
    err = next(e for e in events if e["type"] == "error")
    assert "kapow" in err["message"]
    assert types[-1] == "done"


def test_chat_validates_payload(client: TestClient):
    resp = client.post("/chat", json={"messages": [{"role": "user"}]})  # missing content
    assert resp.status_code == 422
