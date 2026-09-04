import asyncio
import json

import pytest

from agentguard import PermissionPolicy, Runtime
from agentguard.integrations.approval import build_approval_batch, normalize_resume_decisions
from agentguard.runtime.tool import ToolExecutor, ToolRegistry
from agentguard.runtime.policy import RetryPolicy, RetrySafety
from agentguard.runtime.resources import ResourceAccess
from agentguard.domain.actions import CallTool

langgraph_adapter = pytest.importorskip(
    "agentguard.integrations.langgraph",
    reason="install agentguard[langgraph] for LangGraph approval unit tests",
    exc_type=ImportError,
)
GuardedToolNode = langgraph_adapter.GuardedToolNode
ToolGuard = langgraph_adapter.ToolGuard


class Tool:
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    async def ainvoke(self, args):
        self.calls.append((self.name, args))
        return {"name": self.name, "value": args.get("value")}


def test_approval_projection_is_redacted_and_stable():
    action = CallTool("write", {"nested": {"password": "secret", "value": "ok"}})
    pending = [(0, "call-1", action, {"write"}, {"doc": "write"})]
    first = build_approval_batch(pending, run_id="run-1")
    second = build_approval_batch(pending, run_id="run-1")
    assert first.batch_id == second.batch_id
    payload = first.to_dict()
    assert payload["payload_version"]
    assert payload["pending_count"] == 1
    assert payload["items"][0]["arguments"]["nested"]["password"] == "[REDACTED]"
    assert "secret" not in json.dumps(payload)
    assert first.items[0].action_digest


def test_resume_is_fail_closed_and_digest_mismatch_isolated():
    actions = [
        (0, "one", CallTool("write", {"value": 1}), {"write"}, {}),
        (1, "two", CallTool("write", {"value": 2}), {"write"}, {}),
    ]
    batch = build_approval_batch(actions, run_id="run-1")
    decisions = normalize_resume_decisions(
        {
            "one": {"approved": True, "action_digest": batch.items[0].action_digest},
            "two": {"approved": True, "action_digest": "sha256:tampered"},
            "unknown": {"approved": True, "action_digest": batch.items[0].action_digest},
        },
        batch,
    )
    assert decisions["one"].approved is True
    assert decisions["two"].approved is False
    assert decisions["two"].error == "digest_mismatch"

    missing = normalize_resume_decisions({}, batch)
    assert missing["one"].approved is False
    assert missing["one"].reason == "missing approval decision"
    malformed = normalize_resume_decisions(
        {"one": {"approved": True, "actor": "", "action_digest": batch.items[0].action_digest}},
        batch,
    )
    assert malformed["one"].approved is False
    assert malformed["one"].error == "malformed"


@pytest.mark.asyncio
async def test_prepare_then_approval_interrupts_once_and_preserves_order(monkeypatch):
    direct_calls, pending_calls = [], []
    direct = Tool("direct", direct_calls)
    pending = Tool("pending", pending_calls)
    runtime = Runtime(
        ToolExecutor(ToolRegistry()),
        permission_policy=PermissionPolicy(allowed={"read"}, approval_required={"write"}),
    )
    node = GuardedToolNode(
        [direct, pending], runtime=runtime,
        guards={
            "direct": ToolGuard(capabilities={"read"}),
            "pending": ToolGuard(capabilities={"write"}),
        },
    )
    from langchain_core.messages import AIMessage
    ai = AIMessage(content="", tool_calls=[
        {"name": "direct", "args": {"value": "a"}, "id": "direct-id", "type": "tool_call"},
        {"name": "pending", "args": {"value": "b"}, "id": "pending-id", "type": "tool_call"},
    ])
    prepared = await node.prepare({"messages": [ai]}, {"run_id": "run-1"})
    assert len(direct_calls) == 1
    assert pending_calls == []
    payloads = []
    import langgraph.types
    monkeypatch.setattr(langgraph.types, "interrupt", lambda payload: payloads.append(payload) or {
        "pending-id": {
            "approved": True,
            "action_digest": payload["items"][0]["action_digest"],
            "actor": "tester",
        }
    })
    result = await node.approval(prepared, {"run_id": "run-1"})
    assert len(payloads) == 1
    assert len(pending_calls) == 1
    assert [message.tool_call_id for message in result["messages"]] == ["direct-id", "pending-id"]
    assert [json.loads(message.content)["value"] for message in result["messages"]] == ["a", "b"]
    assert result["_agentguard_prepared"]["pending"] == []


@pytest.mark.asyncio
async def test_direct_failure_does_not_block_pending(monkeypatch):
    class Failing(Tool):
        async def ainvoke(self, args):
            self.calls.append(args)
            raise RuntimeError("boom")

    failed, approved = [], []
    runtime = Runtime(
        ToolExecutor(ToolRegistry()),
        permission_policy=PermissionPolicy(allowed={"read"}, approval_required={"write"}),
    )
    node = GuardedToolNode(
        [Failing("bad", failed), Tool("good", approved)], runtime=runtime,
        guards={"bad": ToolGuard(capabilities={"read"}), "good": ToolGuard(capabilities={"write"})},
    )
    from langchain_core.messages import AIMessage
    ai = AIMessage(content="", tool_calls=[
        {"name": "bad", "args": {}, "id": "bad-id", "type": "tool_call"},
        {"name": "good", "args": {}, "id": "good-id", "type": "tool_call"},
    ])
    prepared = await node.prepare({"messages": [ai]}, {"run_id": "run-1"})
    import langgraph.types
    monkeypatch.setattr(langgraph.types, "interrupt", lambda payload: {})
    result = await node.approval(prepared, {"run_id": "run-1"})
    assert len(result["messages"]) == 2
    assert json.loads(result["messages"][0].content)["error"] == "RuntimeError"
    assert json.loads(result["messages"][1].content)["error"] == "PermissionDenied"
    assert approved == []


@pytest.mark.asyncio
async def test_resume_argument_tamper_and_missing_tool_fail_closed(monkeypatch):
    calls = []
    tool = Tool("write", calls)
    runtime = Runtime(ToolExecutor(ToolRegistry()))
    node = GuardedToolNode(
        [tool], runtime=runtime,
        guards={"write": ToolGuard(capabilities={"write"}, approval_required=True)},
    )
    from langchain_core.messages import AIMessage
    ai = AIMessage(content="", tool_calls=[
        {"name": "write", "args": {"value": "original"}, "id": "call-1", "type": "tool_call"},
    ])
    prepared = await node.prepare({"messages": [ai]}, {"run_id": "run-1"})
    monkeypatch.setattr("langgraph.types.interrupt", lambda payload: {
        "call-1": {"approved": True, "action_digest": payload["items"][0]["action_digest"]}
    })
    prepared["_agentguard_prepared"]["pending"][0]["arguments"]["value"] = "tampered"
    tampered = await node.approval(prepared, {"run_id": "run-1"})
    assert json.loads(tampered["messages"][0].content)["error"] == "PermissionDenied"
    assert calls == []

    prepared = await node.prepare({"messages": [ai]}, {"run_id": "run-1"})
    node._tools.pop("write")
    missing = await node.approval(prepared, {"run_id": "run-1"})
    assert json.loads(missing["messages"][0].content)["error"] == "UnknownTool"
    assert calls == []


@pytest.mark.asyncio
async def test_nested_redaction_and_partial_decisions_keep_order(monkeypatch):
    calls = []
    write = Tool("write", calls)
    read = Tool("read", calls)
    runtime = Runtime(ToolExecutor(ToolRegistry()))
    node = GuardedToolNode(
        [write, read], runtime=runtime,
        guards={
            "write": ToolGuard(capabilities={"write"}, approval_required=True),
            "read": ToolGuard(capabilities={"read"}, approval_required=True),
        },
    )
    from langchain_core.messages import AIMessage
    ai = AIMessage(content="", tool_calls=[
        {"name": "write", "args": {"nested": {"password": "very-secret-password", "token": "very-secret-token"}, "value": "w"}, "id": "w", "type": "tool_call"},
        {"name": "read", "args": {"value": "r"}, "id": "r", "type": "tool_call"},
    ])
    prepared = await node.prepare({"messages": [ai]}, {"run_id": "run-1"})
    payload = prepared["_agentguard_prepared"]["batch"]
    serialized = json.dumps(payload)
    assert "very-secret-password" not in serialized and "very-secret-token" not in serialized
    assert payload["items"][0]["arguments"]["nested"]["password"] == "[REDACTED]"

    monkeypatch.setattr("langgraph.types.interrupt", lambda value: {
        "w": {"approved": True, "action_digest": value["items"][0]["action_digest"], "actor": "tester"},
        # Missing "r" deliberately exercises fail-closed partial approval.
    })
    result = await node.approval(prepared, {"run_id": "run-1"})
    assert [message.tool_call_id for message in result["messages"]] == ["w", "r"]
    assert json.loads(result["messages"][0].content)["value"] == "w"
    assert json.loads(result["messages"][1].content)["error"] == "PermissionDenied"
    assert [name for name, _ in calls] == ["write"]


@pytest.mark.asyncio
async def test_approved_timeout_retry_exhaustion_and_lock_conflict_are_structured(monkeypatch):
    attempts = {"retry": 0}
    calls = []

    class Slow(Tool):
        async def ainvoke(self, args):
            await asyncio.sleep(0.03)
            return "late"

    class Flaky(Tool):
        async def ainvoke(self, args):
            attempts["retry"] += 1
            raise ConnectionError("temporary")

    class Locked(Tool):
        async def ainvoke(self, args):
            calls.append(self.name)
            await asyncio.sleep(args.get("delay", 0))
            return self.name

    executor = ToolExecutor(
        ToolRegistry(),
        default_timeout=0.01,
        retry_policy=RetryPolicy(max_attempts=2, initial_delay=0),
    )
    runtime = Runtime(executor, lock_timeout=0.005)
    node = GuardedToolNode(
        [Slow("slow", []), Flaky("retry", []), Locked("lock-a", []), Locked("lock-b", [])],
        runtime=runtime,
        max_concurrency=2,
        guards={
            "slow": ToolGuard(capabilities={"read"}, timeout=0.005, approval_required=True),
            "retry": ToolGuard(capabilities={"read"}, retry_safety=RetrySafety.SAFE, approval_required=True),
            "lock-a": ToolGuard(capabilities={"write"}, resources={"shared": ResourceAccess.WRITE}, timeout=0.2, approval_required=True),
            "lock-b": ToolGuard(capabilities={"write"}, resources={"shared": ResourceAccess.WRITE}, timeout=0.2, approval_required=True),
        },
    )
    from langchain_core.messages import AIMessage
    ai = AIMessage(content="", tool_calls=[
        {"name": "slow", "args": {}, "id": "slow", "type": "tool_call"},
        {"name": "retry", "args": {}, "id": "retry", "type": "tool_call"},
        {"name": "lock-a", "args": {"delay": 0.03}, "id": "lock-a", "type": "tool_call"},
        {"name": "lock-b", "args": {}, "id": "lock-b", "type": "tool_call"},
    ])
    prepared = await node.prepare({"messages": [ai]}, {"run_id": "run-1"})
    monkeypatch.setattr("langgraph.types.interrupt", lambda value: {
        item["tool_call_id"]: {"approved": True, "action_digest": item["action_digest"]}
        for item in value["items"]
    })
    result = await node.approval(prepared, {"run_id": "run-1"})
    payloads = [json.loads(message.content) if message.content.startswith("{") else message.content for message in result["messages"]]
    assert payloads[0]["failure_kind"] == "timeout"
    assert payloads[1]["failure_kind"] == "transient"
    assert payloads[1]["attempts"] == 2
    assert {payloads[2] if isinstance(payloads[2], str) else payloads[2].get("failure_kind"), payloads[3] if isinstance(payloads[3], str) else payloads[3].get("failure_kind")} == {"lock-a", "resource_lock_timeout"}
    assert attempts["retry"] == 2
