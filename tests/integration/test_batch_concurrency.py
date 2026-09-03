import asyncio

import pytest

from agentguard import CallTool, FailureKind, RunStatus, Runtime, ToolResultStatus
from agentguard.runtime.tool import Tool, ToolExecutor, ToolRegistry


@pytest.mark.asyncio
async def test_non_conflicting_batch_actions_overlap_and_preserve_input_order() -> None:
    active = 0
    peak = 0

    async def read(resource: str) -> str:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return resource

    registry = ToolRegistry()
    registry.register(
        "read",
        read,
        capabilities={"read"},
        resources={"resource": "read"},
    )
    runtime = Runtime(ToolExecutor(registry), lock_timeout=0.2)
    results = await runtime.execute_batch(
        [CallTool("read", {"resource": "a"}), CallTool("read", {"resource": "b"})]
    )

    assert [result.value for result in results] == ["a", "b"]
    assert peak == 2


@pytest.mark.asyncio
async def test_conflicting_batch_actions_serialize() -> None:
    order: list[str] = []
    release = asyncio.Event()

    async def write(name: str) -> str:
        order.append(f"start:{name}")
        if name == "first":
            release.set()
            await asyncio.sleep(0.02)
        order.append(f"end:{name}")
        return name

    registry = ToolRegistry()
    registry.register(
        "write",
        write,
        capabilities={"write"},
        resources={"resource": "write"},
    )
    results = await Runtime(ToolExecutor(registry)).execute_batch(
        [CallTool("write", {"name": "first"}), CallTool("write", {"name": "second"})]
    )

    assert [result.value for result in results] == ["first", "second"]
    assert order == ["start:first", "end:first", "start:second", "end:second"]


@pytest.mark.asyncio
async def test_batch_failures_are_independent() -> None:
    async def work(name: str) -> str:
        if name == "bad":
            raise ValueError("bad input")
        await asyncio.sleep(0)
        return name

    registry = ToolRegistry()
    registry.register("work", work, capabilities={"write"})
    results = await Runtime(ToolExecutor(registry)).execute_batch(
        [CallTool("work", {"name": "bad"}), CallTool("work", {"name": "good"})]
    )

    assert results[0].status is ToolResultStatus.FAILED
    assert results[1].status is ToolResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_lock_timeout_does_not_invoke_waiting_tool() -> None:
    calls: list[str] = []
    release = asyncio.Event()

    async def hold() -> str:
        calls.append("hold")
        await release.wait()
        return "hold"

    async def waiting() -> str:
        calls.append("waiting")
        return "waiting"

    registry = ToolRegistry()
    registry.register("hold", hold, capabilities={"write"}, resources={"r": "write"})
    registry.register("waiting", waiting, capabilities={"write"}, resources={"r": "write"})
    runtime = Runtime(ToolExecutor(registry), lock_timeout=0.01)
    first = asyncio.create_task(runtime.execute_batch([CallTool("hold", {})]))
    await asyncio.sleep(0)
    second = await runtime.execute_batch([CallTool("waiting", {})])
    release.set()
    await first

    assert second[0].status is ToolResultStatus.FAILED
    assert second[0].failure_kind is FailureKind.RESOURCE_LOCK_TIMEOUT
    assert calls == ["hold"]


@pytest.mark.asyncio
async def test_explicit_batch_readers_share_but_writer_waits() -> None:
    active_readers = 0
    peak_readers = 0
    readers_released = asyncio.Event()

    async def read(value: str) -> str:
        nonlocal active_readers, peak_readers
        active_readers += 1
        peak_readers = max(peak_readers, active_readers)
        if active_readers == 2:
            readers_released.set()
        await asyncio.sleep(0.01)
        active_readers -= 1
        return value

    async def write() -> str:
        assert active_readers == 0
        return "write"

    runtime = Runtime(ToolExecutor(ToolRegistry()), lock_timeout=0.1)
    results = await runtime.execute_explicit_batch(
        [
            (CallTool("read", {"value": "a"}), Tool("read", read, capabilities={"read"}, resources={"r": "read"})),
            (CallTool("read", {"value": "b"}), Tool("read", read, capabilities={"read"}, resources={"r": "read"})),
            (CallTool("write", {}), Tool("write", write, capabilities={"write"}, resources={"r": "write"})),
        ],
        run_id="rw-batch",
    )

    assert readers_released.is_set()
    assert peak_readers == 2
    assert [result.value for result in results] == ["a", "b", "write"]


@pytest.mark.asyncio
async def test_multi_resource_lock_timeout_releases_partial_acquisition() -> None:
    hold_started = asyncio.Event()
    release_hold = asyncio.Event()
    waiting_calls = 0

    async def hold_b() -> str:
        hold_started.set()
        await release_hold.wait()
        return "held"

    async def needs_a_and_b() -> str:
        nonlocal waiting_calls
        waiting_calls += 1
        return "unexpected"

    async def write_a() -> str:
        return "a-available"

    runtime = Runtime(ToolExecutor(ToolRegistry()), lock_timeout=0.01)
    holder = asyncio.create_task(
        runtime.execute_explicit_batch(
            [(CallTool("hold", {}), Tool("hold", hold_b, capabilities={"write"}, resources={"b": "write"}))],
            run_id="holder",
        )
    )
    await hold_started.wait()
    blocked = await runtime.execute_explicit_batch(
        [(
            CallTool("blocked", {}),
            Tool("blocked", needs_a_and_b, capabilities={"write"}, resources={"a": "write", "b": "write"}),
        )],
        run_id="blocked",
    )
    probe = await runtime.execute_explicit_batch(
        [(CallTool("probe", {}), Tool("probe", write_a, capabilities={"write"}, resources={"a": "write"}))],
        run_id="probe",
    )
    release_hold.set()
    await holder

    assert blocked[0].failure_kind is FailureKind.RESOURCE_LOCK_TIMEOUT
    assert blocked[0].attempts == 0
    assert waiting_calls == 0
    assert probe[0].value == "a-available"
