import pytest

from agentguard import CallTool, ToolResultStatus
from agentguard import Finish, RunState
from agentguard.runtime.router import ScriptedRouter
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


def add(a: int, b: int) -> int:
    return a + b


async def multiply(a: int, b: int) -> int:
    return a * b


@pytest.mark.asyncio
async def test_sync_and_async_tools_share_one_async_execution_entrypoint() -> None:
    executor = ToolExecutor(
        ToolRegistry(
            {
                "add": add,
                "multiply": multiply,
            }
        )
    )

    sync_result = await executor.execute(CallTool("add", {"a": 2, "b": 3}))
    async_result = await executor.execute(CallTool("multiply", {"a": 2, "b": 3}))

    assert sync_result.status is ToolResultStatus.SUCCESS
    assert sync_result.value == 5
    assert async_result.status is ToolResultStatus.SUCCESS
    assert async_result.value == 6


@pytest.mark.asyncio
async def test_tool_exception_becomes_failed_tool_result() -> None:
    def broken() -> None:
        raise ValueError("broken input")

    result = await ToolExecutor(ToolRegistry({"broken": broken})).execute(
        CallTool("broken", {})
    )

    assert result.status is ToolResultStatus.FAILED
    assert result.error_type == "ValueError"
    assert result.error_message == "broken input"


@pytest.mark.asyncio
async def test_unknown_tool_becomes_failed_tool_result() -> None:
    result = await ToolExecutor(ToolRegistry()).execute(CallTool("missing", {}))

    assert result.status is ToolResultStatus.FAILED
    assert result.error_type == "UnknownTool"


@pytest.mark.asyncio
async def test_scripted_router_uses_state_step_to_select_one_action() -> None:
    router = ScriptedRouter(
        [CallTool("add", {"a": 1, "b": 1}), Finish("done")]
    )

    assert isinstance(await router.next_action(RunState("run-001", step=0)), CallTool)
    assert isinstance(await router.next_action(RunState("run-001", step=1)), Finish)
