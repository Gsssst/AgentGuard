"""Real LangGraph evidence for the strict AgentGuard observability boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import pytest

graph_api = pytest.importorskip(
    "langgraph.graph",
    reason="install agentguard[langgraph] for LangGraph observability tests",
)
messages = pytest.importorskip(
    "langchain_core.messages",
    reason="install agentguard[langgraph] for LangChain observability messages",
)
checkpoint_memory = pytest.importorskip(
    "langgraph.checkpoint.memory",
    reason="install agentguard[langgraph] for LangGraph observability checkpoints",
)
types_api = pytest.importorskip(
    "langgraph.types",
    reason="install agentguard[langgraph] for LangGraph observability resume tests",
)

from agentguard import EventCollector, Runtime
from agentguard.events.model import EventType
from agentguard.integrations.langgraph import GuardedToolNode, ToolGuard
from agentguard.runtime.policy import RetryPolicy, RetrySafety
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


SECRET = "collector-secret=/tmp/agentguard-private\nsecond-line"


class State(graph_api.MessagesState, total=False):
    _agentguard_prepared: dict[str, Any]


class RecordingTool:
    def __init__(self, name: str, behavior: str = "success") -> None:
        self.name = name
        self.behavior = behavior
        self.calls: list[dict[str, Any]] = []

    async def ainvoke(self, arguments: dict[str, Any]) -> Any:
        import asyncio

        self.calls.append(dict(arguments))
        if self.behavior == "transient":
            raise ConnectionError(SECRET)
        if self.behavior == "timeout":
            await asyncio.sleep(0.03)
        return {"tool": self.name, "value": arguments.get("value")}


def _tool_messages(state: dict[str, Any]) -> list[Any]:
    return [message for message in state["messages"] if isinstance(message, messages.ToolMessage)]


def _config(name: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": name, "run_id": f"run-{name}"}}


def _approval_graph(node: GuardedToolNode):
    builder = graph_api.StateGraph(State)
    builder.add_node("prepare", node.prepare)
    builder.add_node("approval", node.approval)
    builder.add_edge(graph_api.START, "prepare")
    builder.add_conditional_edges(
        "prepare",
        lambda state: "approval" if state.get("_agentguard_prepared", {}).get("pending") else "done",
        {"approval": "approval", "done": graph_api.END},
    )
    builder.add_edge("approval", graph_api.END)
    return builder.compile(checkpointer=checkpoint_memory.MemorySaver())


def _assert_safe_contiguous(collector: EventCollector, run_id: str) -> tuple[Any, ...]:
    timeline = collector.get_events(run_id)
    assert [event.sequence for event in timeline] == list(range(1, len(timeline) + 1))
    serialized = json.dumps([event.to_dict() for event in timeline], ensure_ascii=False)
    diagnostics = json.dumps(
        [
            {"code": item.code, "run_id": item.run_id, "source_type": item.source_type}
            for item in collector.diagnostics()
        ],
        ensure_ascii=False,
    )
    for sentinel in ("collector-secret", "/tmp/agentguard-private", "second-line"):
        assert sentinel not in serialized
        assert sentinel not in diagnostics
    return timeline


@pytest.mark.asyncio
async def test_public_stategraph_direct_batch_has_one_safe_correlated_timeline() -> None:
    collector = EventCollector()
    success = RecordingTool("success")
    transient = RecordingTool("transient", "transient")
    timeout = RecordingTool("timeout", "timeout")
    runtime = Runtime(
        ToolExecutor(
            ToolRegistry(),
            retry_policy=RetryPolicy(max_attempts=2, initial_delay=0),
        ),
        event_sink=collector,
    )
    node = GuardedToolNode(
        [success, transient, timeout],
        runtime=runtime,
        max_concurrency=3,
        guards={
            "success": ToolGuard(capabilities={"read"}),
            "transient": ToolGuard(capabilities={"read"}, retry_safety=RetrySafety.SAFE),
            "timeout": ToolGuard(capabilities={"read"}, timeout=0.005),
        },
    )
    builder = graph_api.StateGraph(State)
    builder.add_node("tools", node)
    builder.add_edge(graph_api.START, "tools")
    builder.add_edge("tools", graph_api.END)
    graph = builder.compile()
    ai = messages.AIMessage(
        content="",
        tool_calls=[
            {"name": "success", "args": {"value": "ok", "token": SECRET}, "id": "call-success"},
            {"name": "transient", "args": {"token": SECRET}, "id": "call-transient"},
            {"name": "timeout", "args": {}, "id": "call-timeout"},
        ],
    )

    result = await graph.ainvoke({"messages": [ai]}, _config("direct-observability"))
    tool_messages = _tool_messages(result)
    assert [message.tool_call_id for message in tool_messages] == [
        "call-success",
        "call-transient",
        "call-timeout",
    ]
    assert len(success.calls) == 1
    assert len(transient.calls) == 2
    assert len(timeout.calls) == 1

    timeline = _assert_safe_contiguous(collector, "run-direct-observability")
    starts = [event for event in timeline if event.event_type is EventType.BATCH_STARTED]
    finishes = [event for event in timeline if event.event_type is EventType.BATCH_FINISHED]
    assert len(starts) == len(finishes) == 1
    assert starts[0].batch_id == finishes[0].batch_id
    call_events = [event for event in timeline if event.call_id is not None]
    by_external = {
        tool_call_id: {event.call_id for event in call_events if event.tool_call_id == tool_call_id}
        for tool_call_id in ("call-success", "call-transient", "call-timeout")
    }
    assert all(len(call_ids) == 1 for call_ids in by_external.values())
    assert len({next(iter(call_ids)) for call_ids in by_external.values()}) == 3
    assert all(event.batch_id == starts[0].batch_id for event in call_events)


@pytest.mark.asyncio
async def test_messagesstate_pause_resume_reuses_ids_and_finishes_original_batch_once() -> None:
    collector = EventCollector()
    direct = RecordingTool("direct")
    approved = RecordingTool("approved")
    denied = RecordingTool("denied")
    node = GuardedToolNode(
        [direct, approved, denied],
        runtime=Runtime(ToolExecutor(ToolRegistry()), event_sink=collector),
        guards={
            "direct": ToolGuard(capabilities={"read"}),
            "approved": ToolGuard(capabilities={"write"}, approval_required=True),
            "denied": ToolGuard(capabilities={"write"}, approval_required=True),
        },
    )
    graph = _approval_graph(node)
    config = _config("approval-observability")
    ai = messages.AIMessage(
        content="",
        tool_calls=[
            {"name": "direct", "args": {"value": "safe"}, "id": "direct-id"},
            {"name": "approved", "args": {"password": SECRET}, "id": "approved-id"},
            {"name": "denied", "args": {"value": "blocked"}, "id": "denied-id"},
        ],
    )

    paused = await graph.ainvoke({"messages": [ai]}, config)
    assert _tool_messages(paused) == []
    prepared = paused["_agentguard_prepared"]
    expected_call_ids = {
        item["message_tool_call_id"]: item["call_id"] for item in prepared["pending"]
    }
    expected_call_ids["direct-id"] = prepared["immediate"]["0"]["call_id"]
    before_resume = collector.get_events("run-approval-observability")
    assert sum(event.event_type is EventType.BATCH_STARTED for event in before_resume) == 1
    assert not any(event.event_type is EventType.BATCH_FINISHED for event in before_resume)
    payload = paused["__interrupt__"][0].value

    resumed = await graph.ainvoke(
        types_api.Command(
            resume={
                "approved-id": {
                    "approved": True,
                    "actor": "integration-test",
                    "reason": SECRET,
                    "action_digest": payload["items"][0]["action_digest"],
                },
                "denied-id": {
                    "approved": False,
                    "actor": "integration-test",
                    "reason": SECRET,
                    "action_digest": payload["items"][1]["action_digest"],
                },
            }
        ),
        config,
    )

    assert [message.tool_call_id for message in _tool_messages(resumed)] == [
        "direct-id",
        "approved-id",
        "denied-id",
    ]
    assert len(direct.calls) == 1
    assert len(approved.calls) == 1
    assert denied.calls == []
    timeline = _assert_safe_contiguous(collector, "run-approval-observability")
    assert sum(event.event_type is EventType.BATCH_STARTED for event in timeline) == 1
    assert sum(event.event_type is EventType.BATCH_FINISHED for event in timeline) == 1
    for tool_call_id, expected_call_id in expected_call_ids.items():
        correlated = [event for event in timeline if event.tool_call_id == tool_call_id]
        assert correlated
        assert {event.call_id for event in correlated} == {expected_call_id}


@pytest.mark.asyncio
async def test_early_rejections_are_isolated_observable_and_keep_invalid_ids_internal() -> None:
    collector = EventCollector()
    known = RecordingTool("known")
    node = GuardedToolNode(
        [known],
        runtime=Runtime(ToolExecutor(ToolRegistry()), event_sink=collector),
        guards={},
    )

    class FakeAIMessage:
        tool_calls = [
            {"name": "known", "args": {}, "id": "duplicate"},
            {"name": "known", "args": {}, "id": "duplicate"},
            {"name": "missing", "args": {"secret": SECRET}, "id": "unknown-id"},
            {"name": "known", "args": "invalid", "id": "invalid-args"},
            {"name": "known", "args": {}, "id": " invalid-id "},
        ]

    result = await node({"messages": [FakeAIMessage()]}, {"run_id": "run-rejections"})
    assert len(result["messages"]) == 5
    assert known.calls == []
    assert result["messages"][-1].tool_call_id == "agentguard-invalid-call-4"
    timeline = _assert_safe_contiguous(collector, "run-rejections")
    assert sum(event.event_type is EventType.BATCH_STARTED for event in timeline) == 1
    assert sum(event.event_type is EventType.BATCH_FINISHED for event in timeline) == 1
    call_ids = [event.call_id for event in timeline if event.call_id is not None]
    assert len(set(call_ids)) == 5
    invalid_events = [event for event in timeline if event.call_id == call_ids[-1]]
    assert invalid_events and all(event.tool_call_id is None for event in invalid_events)


def test_core_import_does_not_load_optional_framework_or_console_packages() -> None:
    code = """
import builtins
real_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'langgraph', 'langchain_core', 'fastapi'}:
        raise AssertionError('optional package imported: ' + name)
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded
import agentguard
assert not any(name.startswith(('langgraph', 'langchain_core', 'fastapi')) for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", "import sys\n" + code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
