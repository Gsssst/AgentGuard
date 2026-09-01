import pytest

from agentguard import CallTool, FailureKind, ToolResultStatus
from agentguard import Finish, RunState
from agentguard.runtime.router import ScriptedRouter
from agentguard.runtime.policy import RetryPolicy, RetrySafety
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
    assert result.failure_kind is FailureKind.PERMANENT


@pytest.mark.asyncio
async def test_scripted_router_uses_state_step_to_select_one_action() -> None:
    router = ScriptedRouter(
        [CallTool("add", {"a": 1, "b": 1}), Finish("done")]
    )

    assert isinstance(await router.next_action(RunState("run-001", step=0)), CallTool)
    assert isinstance(await router.next_action(RunState("run-001", step=1)), Finish)


def test_tool_metadata_defaults_to_unknown_retry_safety_and_inherited_timeout() -> None:
    registry = ToolRegistry({"add": add})
    tool = registry.get("add")

    assert tool is not None
    assert tool.timeout is None
    assert tool.retry_safety is RetrySafety.UNKNOWN


def test_tool_metadata_accepts_explicit_timeout_and_retry_safety() -> None:
    registry = ToolRegistry()
    registry.register("add", add, timeout=2.5, retry_safety=RetrySafety.SAFE)
    tool = registry.get("add")

    assert tool is not None
    assert tool.timeout == 2.5
    assert tool.retry_safety is RetrySafety.SAFE


@pytest.mark.asyncio
async def test_safe_transient_tool_retries_with_bounded_attempts() -> None:
    calls = 0
    events = []

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise ConnectionError("temporary outage")
        return "ok"

    registry = ToolRegistry()
    registry.register("flaky", flaky, retry_safety=RetrySafety.SAFE)
    executor = ToolExecutor(
        registry,
        retry_policy=RetryPolicy(max_attempts=3, initial_delay=0),
    )

    result = await executor.execute(
        CallTool("flaky", {}),
        on_event=lambda event_type, data: events.append((event_type, data)),
    )

    assert result.status is ToolResultStatus.SUCCESS
    assert result.value == "ok"
    assert calls == 2
    assert [event.value for event, _ in events] == [
        "tool_attempt_started",
        "retry_scheduled",
        "tool_attempt_started",
    ]
    assert events[1][1]["delay_seconds"] == 0


@pytest.mark.asyncio
async def test_unknown_retry_safety_does_not_retry_transient_failure() -> None:
    calls = 0

    async def flaky() -> None:
        nonlocal calls
        calls += 1
        raise ConnectionError("temporary outage")

    result = await ToolExecutor(
        ToolRegistry({"flaky": flaky}),
        retry_policy=RetryPolicy(max_attempts=3, initial_delay=0),
    ).execute(CallTool("flaky", {}))

    assert result.status is ToolResultStatus.FAILED
    assert result.failure_kind.value == "transient"
    assert calls == 1
