"""Real LangGraph interrupt/resume evidence for the approval bridge."""

from __future__ import annotations

import json
import pytest

langgraph = pytest.importorskip(
    "langgraph",
    reason="install agentguard[langgraph] for LangGraph approval integration tests",
)
messages = pytest.importorskip(
    "langchain_core.messages",
    reason="install agentguard[langgraph] for LangChain approval messages",
)
graph_api = pytest.importorskip(
    "langgraph.graph",
    reason="install agentguard[langgraph] for LangGraph graph tests",
)
checkpoint_memory = pytest.importorskip(
    "langgraph.checkpoint.memory",
    reason="install agentguard[langgraph] for LangGraph checkpointer tests",
)
types_api = pytest.importorskip(
    "langgraph.types",
    reason="install agentguard[langgraph] for LangGraph interrupt/resume tests",
)

from agentguard import Runtime
from agentguard.integrations.langgraph import GuardedToolNode, ToolGuard
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


class State(graph_api.MessagesState, total=False):
    _agentguard_prepared: dict


class RecordingTool:
    def __init__(self, name: str):
        self.name = name
        self.calls: list[dict] = []

    async def ainvoke(self, args):
        self.calls.append(dict(args))
        return {"tool": self.name, "value": args.get("value")}


def _graph(node: GuardedToolNode):
    builder = graph_api.StateGraph(State)
    builder.add_node("prepare", node.prepare)
    builder.add_node("approval", node.approval)
    builder.add_edge(graph_api.START, "prepare")
    builder.add_edge("prepare", "approval")
    builder.add_edge("approval", graph_api.END)
    return builder.compile(checkpointer=checkpoint_memory.MemorySaver())


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id, "run_id": f"run-{thread_id}"}}


def _tool_messages(state: dict) -> list:
    """Return only tool results from MessagesState (which also keeps AIMessage)."""

    return [item for item in state["messages"] if isinstance(item, messages.ToolMessage)]


@pytest.mark.asyncio
async def test_stategraph_interrupt_resume_uses_same_thread_id_and_executes_once():
    direct = RecordingTool("read")
    approved = RecordingTool("write")
    node = GuardedToolNode(
        [direct, approved],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={
            "read": ToolGuard(capabilities={"read"}),
            "write": ToolGuard(capabilities={"write"}, approval_required=True),
        },
    )
    graph = _graph(node)
    config = _config("approval-thread-1")
    ai = messages.AIMessage(content="", tool_calls=[
        {"name": "read", "args": {"value": "safe"}, "id": "read-1", "type": "tool_call"},
        {"name": "write", "args": {"value": "change"}, "id": "write-1", "type": "tool_call"},
    ])

    paused = await graph.ainvoke({"messages": [ai]}, config)
    assert len(paused["__interrupt__"]) == 1
    payload = paused["__interrupt__"][0].value
    assert payload["pending_count"] == 1
    assert payload["items"][0]["tool_call_id"] == "write-1"
    assert direct.calls == [{"value": "safe"}]
    assert approved.calls == []

    resumed = await graph.ainvoke(
        types_api.Command(resume={
            "write-1": {
                "approved": True,
                "actor": "integration-test",
                "action_digest": payload["items"][0]["action_digest"],
            }
        }),
        config,
    )
    assert "__interrupt__" not in resumed
    tool_messages = _tool_messages(resumed)
    assert [message.tool_call_id for message in tool_messages] == ["read-1", "write-1"]
    assert json.loads(tool_messages[1].content) == {"tool": "write", "value": "change"}
    assert direct.calls == [{"value": "safe"}], "direct work must not replay across approval resume"
    assert approved.calls == [{"value": "change"}]


@pytest.mark.asyncio
async def test_stategraph_partial_approval_and_missing_decision_are_ordered_and_redacted():
    write = RecordingTool("write")
    delete = RecordingTool("delete")
    node = GuardedToolNode(
        [write, delete],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={
            "write": ToolGuard(capabilities={"write"}, approval_required=True),
            "delete": ToolGuard(capabilities={"destructive", "write"}, approval_required=True),
        },
    )
    graph = _graph(node)
    config = _config("approval-thread-2")
    ai = messages.AIMessage(content="", tool_calls=[
        {"name": "write", "args": {"value": "ok"}, "id": "write-2", "type": "tool_call"},
        {"name": "delete", "args": {"nested": {"password": "do-not-leak"}}, "id": "delete-2", "type": "tool_call"},
    ])
    paused = await graph.ainvoke({"messages": [ai]}, config)
    payload = paused["__interrupt__"][0].value
    assert payload["pending_count"] == 2
    serialized = json.dumps(payload)
    assert "do-not-leak" not in serialized
    assert payload["items"][1]["arguments"]["nested"]["password"] == "[REDACTED]"

    resumed = await graph.ainvoke(
        types_api.Command(resume={
            "write-2": {
                "approved": True,
                "action_digest": payload["items"][0]["action_digest"],
            }
        }),
        config,
    )
    tool_messages = _tool_messages(resumed)
    assert [message.tool_call_id for message in tool_messages] == ["write-2", "delete-2"]
    assert json.loads(tool_messages[0].content)["tool"] == "write"
    assert json.loads(tool_messages[1].content)["error"] == "PermissionDenied"
    assert len(write.calls) == 1 and delete.calls == []


@pytest.mark.asyncio
async def test_stategraph_digest_mismatch_and_missing_tool_fail_per_call():
    tool = RecordingTool("write")
    node = GuardedToolNode(
        [tool],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"write": ToolGuard(capabilities={"write"}, approval_required=True)},
    )
    graph = _graph(node)
    ai = messages.AIMessage(content="", tool_calls=[
        {"name": "write", "args": {"value": "x"}, "id": "write-3", "type": "tool_call"},
    ])

    config = _config("approval-thread-3")
    paused = await graph.ainvoke({"messages": [ai]}, config)
    resumed = await graph.ainvoke(
        types_api.Command(resume={"write-3": {"approved": True, "action_digest": "sha256:tampered"}}),
        config,
    )
    assert json.loads(_tool_messages(resumed)[0].content)["error"] == "PermissionDenied"
    assert tool.calls == []

    config = _config("approval-thread-4")
    paused = await graph.ainvoke({"messages": [ai]}, config)
    payload = paused["__interrupt__"][0].value
    node._tools.pop("write")
    resumed = await graph.ainvoke(
        types_api.Command(resume={"write-3": {"approved": True, "action_digest": payload["items"][0]["action_digest"]}}),
        config,
    )
    assert json.loads(_tool_messages(resumed)[0].content)["error"] == "UnknownTool"
    assert tool.calls == []


@pytest.mark.asyncio
async def test_messages_state_add_messages_has_one_ordered_result_per_call_after_resume():
    direct = RecordingTool("read")
    approved = RecordingTool("write")
    denied = RecordingTool("denied")
    node = GuardedToolNode(
        [direct, approved, denied],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={
            "read": ToolGuard(capabilities={"read"}),
            "write": ToolGuard(capabilities={"write"}, approval_required=True),
            # No guard for denied: it is a known adapter tool that must fail
            # closed without invoking the underlying function.
        },
    )
    graph = _graph(node)
    config = _config("messages-state-regression")
    ai = messages.AIMessage(content="", tool_calls=[
        {"name": "read", "args": {"value": "safe"}, "id": "read-mixed", "type": "tool_call"},
        {"name": "write", "args": {"value": "change"}, "id": "write-mixed", "type": "tool_call"},
        {"name": "denied", "args": {"value": "blocked"}, "id": "denied-mixed", "type": "tool_call"},
    ])

    paused = await graph.ainvoke({"messages": [ai]}, config)
    assert len(paused["__interrupt__"]) == 1
    paused_tools = [item for item in paused["messages"] if isinstance(item, messages.ToolMessage)]
    assert paused_tools == []
    payload = paused["__interrupt__"][0].value
    assert [item["tool_call_id"] for item in payload["items"]] == ["write-mixed"]
    assert direct.calls == [{"value": "safe"}]
    assert approved.calls == []
    assert denied.calls == []

    resumed = await graph.ainvoke(
        types_api.Command(resume={
            "write-mixed": {
                "approved": True,
                "actor": "messages-state-test",
                "action_digest": payload["items"][0]["action_digest"],
            }
        }),
        config,
    )
    tool_messages = [item for item in resumed["messages"] if isinstance(item, messages.ToolMessage)]
    assert len(tool_messages) == 3
    assert [item.tool_call_id for item in tool_messages] == [
        "read-mixed", "write-mixed", "denied-mixed"
    ]
    assert json.loads(tool_messages[0].content) == {"tool": "read", "value": "safe"}
    assert json.loads(tool_messages[1].content) == {"tool": "write", "value": "change"}
    assert json.loads(tool_messages[2].content)["error"] == "PermissionDenied"
    assert direct.calls == [{"value": "safe"}], "direct tool must not replay on resume"
    assert approved.calls == [{"value": "change"}]
    assert denied.calls == []
