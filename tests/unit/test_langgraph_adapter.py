import importlib
import json
import subprocess
import sys

import pytest

from agentguard import PermissionPolicy, Runtime
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


def _adapter_or_skip():
    try:
        return importlib.import_module("agentguard.integrations.langgraph")
    except ImportError:
        pytest.skip("LangChain Core is not installed; adapter unit tests use fake message mode")


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
