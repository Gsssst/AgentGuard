import asyncio

import pytest

from agentguard import CallTool, FailureKind, RunStatus, Runtime, ToolResultStatus
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


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
