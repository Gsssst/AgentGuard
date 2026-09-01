import pytest

from agentguard import (
    CallTool,
    Finish,
    RunState,
    RunStatus,
    Runtime,
    StopReason,
    ToolResultStatus,
    EventType,
    InMemoryEventSink,
)
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


class ResultDrivenRouter:
    async def next_action(self, state: RunState):
        if state.step == 0:
            return CallTool("echo", {"text": "hello"})
        return Finish("echo_done")


class EndlessRouter:
    async def next_action(self, state: RunState):
        return CallTool("echo", {"text": state.step})


class InvalidRouter:
    async def next_action(self, state: RunState):
        return {"type": "tool_call", "tool_name": "echo"}


class TimeoutFallbackRouter:
    async def next_action(self, state: RunState):
        if state.step == 0:
            return CallTool("slow", {})
        if state.last_result.status is ToolResultStatus.TIMED_OUT:
            return CallTool("fallback", {})
        return Finish("fallback_succeeded")


@pytest.mark.asyncio
async def test_runtime_completes_echo_then_finish() -> None:
    async def echo(text: str) -> str:
        return text

    sink = InMemoryEventSink()
    runtime = Runtime(
        ToolExecutor(ToolRegistry({"echo": echo})),
        max_steps=3,
        event_sink=sink,
    )
    result = await runtime.run(ResultDrivenRouter(), RunState("run-success"))

    assert result.status is RunStatus.COMPLETED
    assert result.stop_reason is StopReason.COMPLETED
    assert result.final_state.step == 2
    assert result.final_state.last_result.status is ToolResultStatus.SUCCESS
    assert [event.event_type for event in sink.events] == [
        EventType.RUN_STARTED,
        EventType.ACTION_PROPOSED,
        EventType.TOOL_STARTED,
        EventType.TOOL_ATTEMPT_STARTED,
        EventType.TOOL_SUCCEEDED,
        EventType.ACTION_PROPOSED,
        EventType.RUN_FINISHED,
    ]


@pytest.mark.asyncio
async def test_runtime_rejects_unknown_tool_as_invalid_action() -> None:
    runtime = Runtime(ToolExecutor(ToolRegistry()), max_steps=3)
    result = await runtime.run(
        type("UnknownToolRouter", (), {"next_action": lambda self, state: _unknown_tool()})(),
        RunState("run-unknown-tool"),
    )

    assert result.status is RunStatus.FAILED
    assert result.stop_reason is StopReason.INVALID_ACTION


async def _unknown_tool():
    return CallTool("missing", {})


@pytest.mark.asyncio
async def test_runtime_converts_tool_exception_to_tool_failed() -> None:
    def broken() -> None:
        raise ValueError("broken")

    sink = InMemoryEventSink()
    runtime = Runtime(
        ToolExecutor(ToolRegistry({"broken": broken})),
        max_steps=3,
        event_sink=sink,
    )
    result = await runtime.run(
        type("BrokenRouter", (), {"next_action": lambda self, state: _broken_action()})(),
        RunState("run-tool-failed"),
    )

    assert result.status is RunStatus.FAILED
    assert result.stop_reason is StopReason.TOOL_FAILED
    assert result.final_state.last_result.error_type == "ValueError"
    assert EventType.TOOL_FAILED in [event.event_type for event in sink.events]
    assert sink.events[-1].event_type is EventType.RUN_FINISHED


async def _broken_action():
    return CallTool("broken", {})


@pytest.mark.asyncio
async def test_runtime_rejects_unsupported_action_object() -> None:
    runtime = Runtime(ToolExecutor(ToolRegistry()), max_steps=3)
    result = await runtime.run(InvalidRouter(), RunState("run-invalid"))

    assert result.status is RunStatus.FAILED
    assert result.stop_reason is StopReason.INVALID_ACTION


@pytest.mark.asyncio
async def test_runtime_bounds_router_that_never_finishes() -> None:
    async def echo(text: int) -> int:
        return text

    runtime = Runtime(ToolExecutor(ToolRegistry({"echo": echo})), max_steps=2)
    result = await runtime.run(EndlessRouter(), RunState("run-budget"))

    assert result.status is RunStatus.FAILED
    assert result.stop_reason is StopReason.STEP_BUDGET_EXCEEDED
    assert result.final_state.step == 2


@pytest.mark.asyncio
async def test_loop_guard_stops_before_third_repeated_tool_execution() -> None:
    calls = 0

    async def echo(value: int) -> int:
        nonlocal calls
        calls += 1
        return value

    class RepeatingRouter:
        async def next_action(self, state: RunState):
            return CallTool("echo", {"value": 1})

    sink = InMemoryEventSink()
    result = await Runtime(
        ToolExecutor(ToolRegistry({"echo": echo})),
        max_steps=10,
        event_sink=sink,
    ).run(RepeatingRouter(), RunState("run-loop"))

    assert result.status is RunStatus.FAILED
    assert result.stop_reason is StopReason.LOOP_DETECTED
    assert calls == 2
    assert sink.events[-2].event_type is EventType.LOOP_DETECTED
    assert sink.events[-1].event_type is EventType.RUN_FINISHED


@pytest.mark.asyncio
async def test_timeout_is_an_observation_router_can_handle_with_fallback() -> None:
    async def slow() -> None:
        import asyncio

        await asyncio.sleep(10)

    async def fallback() -> str:
        return "recovered"

    registry = ToolRegistry()
    registry.register("slow", slow, timeout=0.001)
    registry.register("fallback", fallback)
    sink = InMemoryEventSink()
    result = await Runtime(
        ToolExecutor(registry),
        max_steps=4,
        event_sink=sink,
    ).run(TimeoutFallbackRouter(), RunState("run-timeout-fallback"))

    assert result.status is RunStatus.COMPLETED
    assert result.stop_reason is StopReason.COMPLETED
    assert result.final_state.last_result.value == "recovered"
    assert EventType.TOOL_TIMED_OUT in [event.event_type for event in sink.events]
