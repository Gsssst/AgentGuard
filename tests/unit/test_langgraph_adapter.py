import importlib
import asyncio
import json
import subprocess
import sys

import pytest

from agentguard import PermissionPolicy, Runtime
from agentguard.runtime.policy import RetryPolicy, RetrySafety
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


class FakeAIMessage:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


class FakeToolMessage:
    def __init__(self, content, tool_call_id):
        self.content = content
        self.tool_call_id = tool_call_id


class FakeTool:
    name = "echo"

    async def ainvoke(self, args):
        return {"value": args["value"]}


class SyncTool:
    name = "sync_echo"

    def invoke(self, args):
        return args["value"]


class BrokenTool:
    name = "broken"

    async def ainvoke(self, args):
        raise RuntimeError("secret-token=/tmp/private-key")


class BatchTool:
    name = "batch"

    def __init__(self, calls=None):
        self.calls = calls if calls is not None else []

    async def ainvoke(self, args):
        self.calls.append(args["value"])
        await asyncio.sleep(args.get("delay", 0))
        return args["value"]


def _adapter_or_skip():
    try:
        return importlib.import_module("agentguard.integrations.langgraph")
    except ImportError:
        pytest.skip("install agentguard[langgraph] for LangGraph adapter tests")


@pytest.mark.asyncio
async def test_core_imports_without_optional_dependencies() -> None:
    result = subprocess.run([sys.executable, "-c", "import agentguard"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_adapter_import_without_dependency_is_actionable() -> None:
    code = "import agentguard.integrations.langgraph"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if result.returncode:
        assert "agentguard[langgraph]" in result.stderr


@pytest.mark.asyncio
async def test_guarded_node_success_preserves_tool_call_id() -> None:
    adapter = _adapter_or_skip()
    from langchain_core.messages import AIMessage

    node = adapter.GuardedToolNode(
        [FakeTool()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"echo": adapter.ToolGuard(capabilities={"read"})},
    )
    message = AIMessage(content="", tool_calls=[{"name": "echo", "args": {"value": "ok"}, "id": "call-1", "type": "tool_call"}])
    result = await node({"messages": [message]}, {"run_id": "run-1"})
    assert result["messages"][0].tool_call_id == "call-1"
    assert json.loads(result["messages"][0].content) == {"value": "ok"}


@pytest.mark.asyncio
async def test_missing_guard_does_not_invoke_tool() -> None:
    adapter = _adapter_or_skip()
    from langchain_core.messages import AIMessage

    tool = FakeTool()
    node = adapter.GuardedToolNode([tool], runtime=Runtime(ToolExecutor(ToolRegistry())), guards={})
    message = AIMessage(content="", tool_calls=[{"name": "echo", "args": {}, "id": "call-2", "type": "tool_call"}])
    result = await node({"messages": [message]})
    payload = json.loads(result["messages"][0].content)
    assert payload["error"] == "PermissionDenied"


@pytest.mark.asyncio
async def test_sync_tool_uses_invoke_fallback() -> None:
    adapter = _adapter_or_skip()
    node = adapter.GuardedToolNode(
        [SyncTool()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"sync_echo": adapter.ToolGuard(capabilities={"read"})},
    )
    result = await node({"messages": [FakeAIMessage([]), FakeAIMessage([])]})
    assert json.loads(result["messages"][0].content)["error"] == "MissingToolCalls"

    from langchain_core.messages import AIMessage
    ai = AIMessage(content="", tool_calls=[{"name": "sync_echo", "args": {"value": "sync"}, "id": "call-sync", "type": "tool_call"}])
    result = await node({"messages": [ai]})
    assert result["messages"][0].content == "sync"


@pytest.mark.asyncio
async def test_messages_key_and_last_tool_calling_message_are_supported() -> None:
    adapter = _adapter_or_skip()
    node = adapter.GuardedToolNode(
        [FakeTool()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"echo": adapter.ToolGuard(capabilities={"read"})},
        messages_key="history",
    )
    from langchain_core.messages import AIMessage
    old = AIMessage(content="", tool_calls=[{"name": "echo", "args": {"value": "old"}, "id": "old", "type": "tool_call"}])
    new = AIMessage(content="", tool_calls=[{"name": "echo", "args": {"value": "new"}, "id": "new", "type": "tool_call"}])
    result = await node({"history": [old, new]})
    assert result["messages"][0].tool_call_id == "new"
    assert json.loads(result["messages"][0].content) == {"value": "new"}


@pytest.mark.asyncio
async def test_tool_error_message_is_safe_summary() -> None:
    adapter = _adapter_or_skip()
    node = adapter.GuardedToolNode(
        [BrokenTool()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"broken": adapter.ToolGuard(capabilities={"read"})},
    )
    from langchain_core.messages import AIMessage
    ai = AIMessage(content="", tool_calls=[{"name": "broken", "args": {}, "id": "call-broken", "type": "tool_call"}])
    result = await node({"messages": [ai]})
    content = result["messages"][0].content
    assert "secret-token" not in content
    assert json.loads(content)["error"] == "RuntimeError"


@pytest.mark.asyncio
async def test_multi_tool_calls_preserve_input_order_and_ids() -> None:
    adapter = _adapter_or_skip()

    class Multi:
        def __init__(self, name, calls):
            self.name = name
            self.calls = calls

        async def ainvoke(self, args):
            self.calls.append(args["value"])
            await asyncio.sleep(args.get("delay", 0))
            return {"value": args["value"]}

    calls: list[str] = []
    node = adapter.GuardedToolNode(
        [Multi("one", calls), Multi("two", calls), Multi("three", calls)],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={name: adapter.ToolGuard(capabilities={"read"}) for name in ("one", "two", "three")},
        max_concurrency=2,
    )
    from langchain_core.messages import AIMessage
    ai = AIMessage(content="", tool_calls=[
        {"name": "one", "args": {"value": "1", "delay": 0.03}, "id": "id-1", "type": "tool_call"},
        {"name": "two", "args": {"value": "2", "delay": 0.0}, "id": "id-2", "type": "tool_call"},
        {"name": "three", "args": {"value": "3", "delay": 0.0}, "id": "id-3", "type": "tool_call"},
    ])
    result = await node({"messages": [ai]})
    assert [m.tool_call_id for m in result["messages"]] == ["id-1", "id-2", "id-3"]
    assert [json.loads(m.content) for m in result["messages"]] == [{"value": "1"}, {"value": "2"}, {"value": "3"}]
    assert calls == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_pending_prepare_projection_has_no_placeholder_messages() -> None:
    adapter = _adapter_or_skip()

    class PendingTool:
        name = "review"

        async def ainvoke(self, args):
            raise AssertionError("pending tool must not run before approval")

    class DirectTool:
        name = "direct"

        def __init__(self):
            self.calls = 0

        async def ainvoke(self, args):
            self.calls += 1
            return {"value": args["value"]}

    direct = DirectTool()
    node = adapter.GuardedToolNode(
        [direct, PendingTool()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={
            "direct": adapter.ToolGuard(capabilities={"read"}),
            "review": adapter.ToolGuard(capabilities={"write"}, approval_required=True),
        },
    )
    from langchain_core.messages import AIMessage

    ai = AIMessage(content="", tool_calls=[
        {"name": "direct", "args": {"value": "safe"}, "id": "direct-1", "type": "tool_call"},
        {"name": "review", "args": {"value": "change"}, "id": "review-1", "type": "tool_call"},
    ])
    prepared = await node.prepare({"messages": [ai]}, {"run_id": "run-pending"})

    assert "messages" not in prepared
    context = prepared["_agentguard_prepared"]
    assert [item["tool_call_id"] for item in context["pending"]] == ["review-1"]
    assert context["immediate"]["0"]["tool_call_id"] == "direct-1"
    assert "ApprovalRequired" not in json.dumps(prepared)
    assert direct.calls == 1


@pytest.mark.asyncio
async def test_no_pending_prepare_returns_final_messages_directly() -> None:
    adapter = _adapter_or_skip()
    node = adapter.GuardedToolNode(
        [FakeTool()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"echo": adapter.ToolGuard(capabilities={"read"})},
    )
    from langchain_core.messages import AIMessage

    ai = AIMessage(content="", tool_calls=[
        {"name": "echo", "args": {"value": "ok"}, "id": "direct-only", "type": "tool_call"},
    ])
    result = await node.prepare({"messages": [ai]}, {"run_id": "run-direct"})

    assert "_agentguard_prepared" not in result
    assert [message.tool_call_id for message in result["messages"]] == ["direct-only"]


@pytest.mark.asyncio
async def test_legacy_call_without_approval_remains_compatible() -> None:
    adapter = _adapter_or_skip()
    tool = FakeTool()
    node = adapter.GuardedToolNode(
        [tool],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"echo": adapter.ToolGuard(capabilities={"read"})},
    )
    from langchain_core.messages import AIMessage

    ai = AIMessage(content="", tool_calls=[
        {"name": "echo", "args": {"value": "legacy"}, "id": "legacy-1", "type": "tool_call"},
    ])
    result = await node({"messages": [ai]}, {"run_id": "run-legacy"})

    assert [message.tool_call_id for message in result["messages"]] == ["legacy-1"]
    assert json.loads(result["messages"][0].content) == {"value": "legacy"}


@pytest.mark.asyncio
async def test_malformed_duplicate_unknown_and_missing_guard_are_isolated() -> None:
    adapter = _adapter_or_skip()
    invoked: list[str] = []

    class Known:
        name = "known"

        async def ainvoke(self, args):
            invoked.append(args["value"])
            return args["value"]

    node = adapter.GuardedToolNode(
        [Known()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={},
    )
    result = await node({"messages": [FakeAIMessage([
        {"name": "known", "args": {"value": "a"}, "id": "dup"},
        {"name": "known", "args": {"value": "b"}, "id": "dup"},
        {"name": "missing", "args": {}, "id": "m"},
        {"name": "known", "args": "bad", "id": "bad-args"},
        {"name": "known", "args": {}, "id": None},
    ])]})
    messages = result["messages"]
    assert len(messages) == 5
    payloads = [json.loads(message.content) for message in messages]
    assert [payload["error"] for payload in payloads] == [
        "DuplicateToolCallId", "DuplicateToolCallId", "UnknownTool", "InvalidToolCall", "PermissionDenied"
    ]
    assert messages[-1].tool_call_id == "agentguard-invalid-call-4"
    assert payloads[-1]["tool_call_id_valid"] is False
    assert invoked == []


def test_max_concurrency_is_validated_at_node_construction() -> None:
    adapter = _adapter_or_skip()
    for value in (0, -1, 1.5, "2", True):
        with pytest.raises(ValueError, match="max_concurrency"):
            adapter.GuardedToolNode(
                [FakeTool()],
                runtime=Runtime(ToolExecutor(ToolRegistry())),
                guards={"echo": adapter.ToolGuard(capabilities={"read"})},
                max_concurrency=value,
            )


@pytest.mark.asyncio
async def test_unknown_tool_precedes_missing_guard_and_permission_policy_denial_is_safe() -> None:
    adapter = _adapter_or_skip()
    from langchain_core.messages import AIMessage
    node = adapter.GuardedToolNode(
        [FakeTool()],
        runtime=Runtime(
            ToolExecutor(ToolRegistry()),
            permission_policy=PermissionPolicy(allowed={"read"}),
        ),
        guards={"echo": adapter.ToolGuard(capabilities={"write"})},
    )
    ai = AIMessage(content="", tool_calls=[
        {"name": "not-registered", "args": {}, "id": "unknown", "type": "tool_call"},
        {"name": "echo", "args": {"value": "x"}, "id": "denied", "type": "tool_call"},
    ])
    result = await node({"messages": [ai]})
    assert [json.loads(message.content)["error"] for message in result["messages"]] == ["UnknownTool", "PermissionDenied"]


@pytest.mark.asyncio
async def test_timeout_retry_and_exception_results_are_structured_per_call() -> None:
    adapter = _adapter_or_skip()
    attempts = 0

    class Slow:
        name = "slow"
        async def ainvoke(self, args):
            await asyncio.sleep(0.03)
            return "late"

    class Flaky:
        name = "flaky"
        async def ainvoke(self, args):
            nonlocal attempts
            attempts += 1
            raise ConnectionError("secret-argument")

    class Explodes:
        name = "explode"
        async def ainvoke(self, args):
            raise RuntimeError("private stack detail")

    executor = ToolExecutor(ToolRegistry(), default_timeout=0.01, retry_policy=RetryPolicy(max_attempts=2, initial_delay=0))
    node = adapter.GuardedToolNode(
        [Slow(), Flaky(), Explodes()], runtime=Runtime(executor),
        guards={
            "slow": adapter.ToolGuard(capabilities={"read"}, timeout=0.005),
            "flaky": adapter.ToolGuard(capabilities={"read"}, retry_safety=RetrySafety.SAFE),
            "explode": adapter.ToolGuard(capabilities={"read"}),
        },
    )
    result = await node({"messages": [FakeAIMessage([
        {"name": "slow", "args": {}, "id": "slow"},
        {"name": "flaky", "args": {}, "id": "flaky"},
        {"name": "explode", "args": {}, "id": "explode"},
    ])]})
    payloads = [json.loads(message.content) for message in result["messages"]]
    assert payloads[0]["failure_kind"] == "timeout"
    assert payloads[1]["failure_kind"] == "transient" and payloads[1]["attempts"] == 2
    assert payloads[2]["error"] == "RuntimeError"
    assert attempts == 2
    assert "secret-argument" not in result["messages"][1].content
    assert "private stack detail" not in result["messages"][2].content


@pytest.mark.asyncio
async def test_individual_cancel_isolated_from_siblings() -> None:
    adapter = _adapter_or_skip()

    class MaybeCancel:
        name = "maybe"
        async def ainvoke(self, args):
            if args["cancel"]:
                raise asyncio.CancelledError
            await asyncio.sleep(0.01)
            return "ok"

    node = adapter.GuardedToolNode(
        [MaybeCancel()], runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"maybe": adapter.ToolGuard(capabilities={"read"})},
    )
    result = await node({"messages": [FakeAIMessage([
        {"name": "maybe", "args": {"cancel": True}, "id": "cancel"},
        {"name": "maybe", "args": {"cancel": False}, "id": "ok"},
    ])]})
    assert json.loads(result["messages"][0].content)["failure_kind"] == "cancelled"
    assert result["messages"][1].content == "ok"
