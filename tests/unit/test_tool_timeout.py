import asyncio
import threading

import pytest

from agentguard import CallTool, FailureKind, ToolResultStatus
from agentguard.runtime.policy import RetrySafety
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


@pytest.mark.asyncio
async def test_async_tool_timeout_returns_timed_out_result() -> None:
    cancelled = asyncio.Event()

    async def slow() -> None:
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    registry = ToolRegistry()
    registry.register("slow", slow, timeout=0.01, retry_safety=RetrySafety.SAFE)

    result = await ToolExecutor(registry, default_timeout=1.0).execute(CallTool("slow", {}))

    assert result.status is ToolResultStatus.TIMED_OUT
    assert result.failure_kind is FailureKind.TIMEOUT
    assert result.timeout_seconds == 0.01
    assert result.timeout_source == "tool"
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_runtime_default_timeout_applies_when_tool_has_no_timeout() -> None:
    async def slow() -> None:
        await asyncio.sleep(10)

    result = await ToolExecutor(
        ToolRegistry({"slow": slow}),
        default_timeout=0.01,
    ).execute(CallTool("slow", {}))

    assert result.status is ToolResultStatus.TIMED_OUT
    assert result.timeout_seconds == 0.01
    assert result.timeout_source == "runtime"


@pytest.mark.asyncio
async def test_sync_tool_timeout_returns_but_worker_may_finish_later() -> None:
    finished = threading.Event()

    def slow_sync() -> str:
        import time

        time.sleep(0.05)
        finished.set()
        return "finished"

    result = await ToolExecutor(
        ToolRegistry({"slow_sync": slow_sync}),
        default_timeout=0.001,
    ).execute(CallTool("slow_sync", {}))

    assert result.status is ToolResultStatus.TIMED_OUT
    assert result.failure_kind is FailureKind.TIMEOUT
    # The Runtime has already returned, but the adapted sync callable can
    # still complete in its worker thread afterwards.
    assert finished.wait(timeout=0.2)


@pytest.mark.asyncio
async def test_timeout_validation_rejects_non_positive_values() -> None:
    with pytest.raises(ValueError):
        ToolExecutor(ToolRegistry(), default_timeout=0)

    registry = ToolRegistry()
    with pytest.raises(ValueError):
        registry.register("slow", lambda: None, timeout=0)


@pytest.mark.asyncio
async def test_tool_raised_timeout_error_is_not_misreported_as_runtime_deadline() -> None:
    async def raises_timeout_error() -> None:
        raise TimeoutError("upstream service timed out")

    result = await ToolExecutor(
        ToolRegistry({"upstream": raises_timeout_error}),
        default_timeout=1.0,
    ).execute(CallTool("upstream", {}))

    assert result.status is ToolResultStatus.FAILED
    assert result.failure_kind is FailureKind.TRANSIENT
    assert result.timeout_seconds is None
    assert result.error_message == "upstream service timed out"


@pytest.mark.asyncio
async def test_timeout_returns_even_when_async_tool_suppresses_cancellation() -> None:
    cancellation_seen = asyncio.Event()
    release = asyncio.Event()

    async def uncooperative() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancellation_seen.set()
            await release.wait()

    result = await asyncio.wait_for(
        ToolExecutor(
            ToolRegistry({"uncooperative": uncooperative}),
            default_timeout=0.001,
        ).execute(CallTool("uncooperative", {})),
        timeout=0.1,
    )

    assert result.status is ToolResultStatus.TIMED_OUT
    assert cancellation_seen.is_set()
    release.set()
    await asyncio.sleep(0)
