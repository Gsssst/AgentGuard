import pytest
from typing import TypedDict

langgraph = pytest.importorskip("langgraph", reason="install agentguard[langgraph] for LangGraph integration tests")
messages = pytest.importorskip("langchain_core.messages", reason="install agentguard[langgraph] for LangChain messages")
graph_api = pytest.importorskip("langgraph.graph", reason="install agentguard[langgraph] for LangGraph graph tests")

from agentguard import Runtime
from agentguard.integrations.langgraph import GuardedToolNode, ToolGuard
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


class EchoTool:
    name = "echo"

    async def ainvoke(self, args):
        return args["value"]


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
