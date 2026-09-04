import pytest
from typing import TypedDict
from importlib.metadata import version

langgraph = pytest.importorskip("langgraph", reason="install agentguard[langgraph] for LangGraph integration tests")
messages = pytest.importorskip("langchain_core.messages", reason="install agentguard[langgraph] for LangChain messages")
graph_api = pytest.importorskip("langgraph.graph", reason="install agentguard[langgraph] for LangGraph graph tests")


def test_public_interrupt_resume_api_is_available_when_extra_is_installed() -> None:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command, interrupt

    assert callable(interrupt)
    assert callable(Command)
    assert callable(MemorySaver)


def test_locally_verified_optional_versions_are_bounded() -> None:
    assert version("langgraph") == "0.6.11"
    assert version("langchain-core") == "0.3.86"

from agentguard import Runtime
from agentguard.integrations.langgraph import GuardedToolNode, ToolGuard
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


class EchoTool:
    name = "echo"

    async def ainvoke(self, args):
        return args["value"]


class UpperTool:
    name = "upper"

    async def ainvoke(self, args):
        return args["value"].upper()


@pytest.mark.asyncio
async def test_real_langchain_message_round_trip() -> None:
    node = GuardedToolNode(
        [EchoTool()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={"echo": ToolGuard(capabilities={"read"})},
    )
    ai = messages.AIMessage(
        content="",
        tool_calls=[{"name": "echo", "args": {"value": "hello"}, "id": "call-real", "type": "tool_call"}],
    )
    class State(TypedDict):
        messages: list

    graph = graph_api.StateGraph(State)
    graph.add_node("tools", node)
    graph.set_entry_point("tools")
    graph.set_finish_point("tools")
    compiled = graph.compile()
    result = await compiled.ainvoke({"messages": [ai]})
    assert result["messages"][0].tool_call_id == "call-real"
    assert result["messages"][0].content == "hello"


@pytest.mark.asyncio
async def test_real_langgraph_multiple_tool_calls_preserve_ids_and_order() -> None:
    node = GuardedToolNode(
        [EchoTool(), UpperTool()],
        runtime=Runtime(ToolExecutor(ToolRegistry())),
        guards={
            "echo": ToolGuard(capabilities={"read"}),
            "upper": ToolGuard(capabilities={"read"}),
        },
        max_concurrency=2,
    )
    ai = messages.AIMessage(
        content="",
        tool_calls=[
            {"name": "echo", "args": {"value": "first"}, "id": "call-1", "type": "tool_call"},
            {"name": "upper", "args": {"value": "second"}, "id": "call-2", "type": "tool_call"},
        ],
    )

    class State(TypedDict):
        messages: list

    graph = graph_api.StateGraph(State)
    graph.add_node("tools", node)
    graph.set_entry_point("tools")
    graph.set_finish_point("tools")
    result = await graph.compile().ainvoke({"messages": [ai]})
    assert [message.tool_call_id for message in result["messages"]] == ["call-1", "call-2"]
    assert [message.content for message in result["messages"]] == ["first", "SECOND"]
