import json

import pytest

from agentguard import (
    CallTool,
    CheckpointStore,
    EventType,
    Finish,
    InMemoryEventSink,
    RunState,
    RunStatus,
    Runtime,
    SimulatedCrash,
)
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


class ResultRouter:
    async def next_action(self, state: RunState):
        return (
            CallTool("echo", {"value": state.step})
            if state.step < 2
            else Finish("done")
        )


@pytest.mark.asyncio
async def test_crash_before_checkpoint_then_explicit_resume(tmp_path) -> None:
    calls = 0
    hook_calls = 0

    async def echo(value: int) -> int:
        nonlocal calls
        calls += 1
        return value

    def crash_on_second_tool(boundary: str) -> None:
        nonlocal hook_calls
        if boundary == "after_tool_before_checkpoint":
            hook_calls += 1
            if hook_calls == 2:
                raise SimulatedCrash(boundary)

    path = tmp_path / "checkpoints" / "run-recovery.json"
    sink = InMemoryEventSink()
    runtime = Runtime(
        ToolExecutor(ToolRegistry({"echo": echo})),
        event_sink=sink,
        checkpoint_store=CheckpointStore(path.parent),
        checkpoint_path=path,
        crash_hook=crash_on_second_tool,
    )

    with pytest.raises(SimulatedCrash):
        await runtime.run(ResultRouter(), RunState("run-recovery"))

    previous = path.read_bytes()
    saved = json.loads(previous)
    assert saved["state"]["step"] == 1
    assert calls == 2

    resumed = Runtime(
        ToolExecutor(ToolRegistry({"echo": echo})),
        event_sink=sink,
        checkpoint_store=CheckpointStore(path.parent),
    )
    result = await resumed.resume(path, ResultRouter())

    assert result.status is RunStatus.COMPLETED
    assert result.run_id == "run-recovery"
    assert calls == 3
    assert path.exists()
    assert any(event.event_type is EventType.RESUME_STARTED for event in sink.events)
    assert any(
        event.event_type is EventType.RUN_STARTED
        and event.data.get("resume_attempt") == 1
        for event in sink.events
    )
    assert any(
        event.data.get("duplicate_possible") is True for event in sink.events
    )
    assert path.read_bytes() != previous


@pytest.mark.asyncio
async def test_corrupt_checkpoint_rejected_before_tool_side_effect(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    calls = 0

    async def dangerous() -> None:
        nonlocal calls
        calls += 1

    runtime = Runtime(ToolExecutor(ToolRegistry({"dangerous": dangerous})))
    with pytest.raises(Exception):
        await runtime.resume(path, ResultRouter())
    assert calls == 0
    assert path.read_text(encoding="utf-8") == "{"
