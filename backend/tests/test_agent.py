"""Tests for the agent tool-calling loop.

These tests fake the OpenAI client so no network calls are made. We drive the
loop through a scripted sequence of responses and assert that (a) tool calls
are executed against the real tools module, (b) events are yielded in the
right order, and (c) the loop terminates correctly.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import agent


def _tool_call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _completion(content: str | None = None, tool_calls=None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


class FakeClient:
    def __init__(self, scripted_responses: list[SimpleNamespace]):
        self._responses = list(scripted_responses)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeClient: no more scripted responses")
        return self._responses.pop(0)


@pytest.fixture
def patch_client(monkeypatch: pytest.MonkeyPatch):
    holder: dict = {}

    def install(responses: list[SimpleNamespace]) -> FakeClient:
        fake = FakeClient(responses)
        monkeypatch.setattr(agent, "_client", lambda: fake)
        holder["fake"] = fake
        return fake

    return install


def test_agent_answers_without_tool_calls(patch_client, kb: Path):
    fake = patch_client([_completion(content="Kurze Antwort ohne Tools.")])

    events = list(agent.run_agent([{"role": "user", "content": "Hi"}]))

    assert events == [{"type": "answer", "content": "Kurze Antwort ohne Tools."}]
    assert len(fake.calls) == 1
    # System prompt is injected + user message passed through.
    messages = fake.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "Hi"}


def test_agent_executes_tool_call_then_answers(patch_client, kb: Path):
    fake = patch_client(
        [
            _completion(
                tool_calls=[_tool_call("c1", "keyword_search", {"query": "pelacarsen"})]
            ),
            _completion(content="Pelacarsen wird in der HORIZON-Studie untersucht."),
        ]
    )

    events = list(agent.run_agent([{"role": "user", "content": "Was ist pelacarsen?"}]))

    types = [e["type"] for e in events]
    assert types == ["tool_call", "tool_result", "answer"]

    assert events[0]["name"] == "keyword_search"
    assert events[0]["arguments"] == {"query": "pelacarsen"}
    assert "trials.md" in events[1]["result_preview"]
    assert "HORIZON" in events[2]["content"]

    # Second LLM call must include the tool result as a "tool" message.
    second_messages = fake.calls[1]["messages"]
    tool_msgs = [m for m in second_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "c1"
    assert "pelacarsen" in tool_msgs[0]["content"].lower()


def test_agent_handles_multiple_tool_calls_in_one_turn(patch_client, kb: Path):
    fake = patch_client(
        [
            _completion(
                tool_calls=[
                    _tool_call("a", "list_files", {}),
                    _tool_call("b", "read_file", {"filename": "basics.md"}),
                ]
            ),
            _completion(content="Fertig."),
        ]
    )

    events = list(agent.run_agent([{"role": "user", "content": "?"}]))

    # Two (call, result) pairs then one answer.
    types = [e["type"] for e in events]
    assert types == ["tool_call", "tool_result", "tool_call", "tool_result", "answer"]
    assert events[0]["name"] == "list_files"
    assert events[2]["name"] == "read_file"

    # Second turn should have two tool messages, one per call id.
    second = fake.calls[1]["messages"]
    tool_ids = [m["tool_call_id"] for m in second if m.get("role") == "tool"]
    assert tool_ids == ["a", "b"]


def test_agent_handles_bad_tool_call_args(patch_client, kb: Path):
    # Invalid JSON in arguments should be tolerated (parsed as {}).
    bad_call = SimpleNamespace(
        id="x",
        type="function",
        function=SimpleNamespace(name="list_files", arguments="not-json"),
    )
    patch_client(
        [
            _completion(tool_calls=[bad_call]),
            _completion(content="ok"),
        ]
    )

    events = list(agent.run_agent([{"role": "user", "content": "?"}]))
    assert events[0] == {"type": "tool_call", "name": "list_files", "arguments": {}}
    assert events[-1]["type"] == "answer"


def test_agent_surfaces_tool_exception_as_error_result(
    patch_client, kb: Path, monkeypatch: pytest.MonkeyPatch
):
    def boom(name, args):
        raise RuntimeError("boom")

    monkeypatch.setattr(agent, "dispatch_tool", boom)

    patch_client(
        [
            _completion(tool_calls=[_tool_call("c1", "list_files", {})]),
            _completion(content="handled"),
        ]
    )

    events = list(agent.run_agent([{"role": "user", "content": "?"}]))
    result_events = [e for e in events if e["type"] == "tool_result"]
    assert len(result_events) == 1
    assert "ERROR" in result_events[0]["result_preview"]


def test_agent_respects_max_iterations(patch_client, kb: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(agent, "MAX_TOOL_ITERATIONS", 2)
    # Infinite tool-calling model — never yields a final answer.
    looping = [
        _completion(tool_calls=[_tool_call(f"c{i}", "list_files", {})]) for i in range(5)
    ]
    patch_client(looping)

    events = list(agent.run_agent([{"role": "user", "content": "?"}]))
    answer = [e for e in events if e["type"] == "answer"]
    assert len(answer) == 1
    assert "Maximale" in answer[0]["content"]


def test_agent_filters_empty_and_unknown_roles(patch_client, kb: Path):
    fake = patch_client([_completion(content="ok")])
    list(
        agent.run_agent(
            [
                {"role": "user", "content": ""},  # empty — dropped
                {"role": "system", "content": "ignore me"},  # wrong role — dropped
                {"role": "user", "content": "real"},
            ]
        )
    )
    msgs = fake.calls[0]["messages"]
    user_msgs = [m for m in msgs if m["role"] == "user"]
    assert user_msgs == [{"role": "user", "content": "real"}]
