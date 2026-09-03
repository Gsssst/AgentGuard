import asyncio

import pytest

from agentguard import CallTool, FailureKind, PermissionPolicy, Runtime, ToolResultStatus
from agentguard.runtime.permission import Capability
from agentguard.runtime.policy import RetryPolicy, RetrySafety
from agentguard.runtime.tool import Tool, ToolExecutor, ToolRegistry


@pytest.mark.asyncio
async def test_explicit_tool_uses_runtime_controls_without_registry_mutation() -> None:
    calls = 0

    async def work(value: str) -> str:
        nonlocal calls
        calls += 1
        return value

    registry = ToolRegistry({"existing": lambda: "existing"})
    runtime = Runtime(ToolExecutor(registry), permission_policy=PermissionPolicy(allowed={"read"}))
    tool = Tool("adapter_work", work, capabilities={"read"})

    result = await runtime.execute_explicit_tool(CallTool("adapter_work", {"value": "ok"}), tool)

    assert result.status is ToolResultStatus.SUCCESS
    assert result.value == "ok"
    assert calls == 1
    assert runtime.executor.get_tool("adapter_work") is None
    assert runtime.executor.get_tool("existing") is not None


@pytest.mark.asyncio
async def test_explicit_tool_permission_denial_does_not_invoke() -> None:
    calls = 0

    def write() -> str:
        nonlocal calls
        calls += 1
        return "written"

    runtime = Runtime(ToolExecutor(ToolRegistry()), permission_policy=PermissionPolicy(allowed={"read"}))
    result = await runtime.execute_explicit_tool(CallTool("write", {}), Tool("write", write, capabilities={"write"}))

    assert result.error_type == "PermissionDenied"
    assert result.failure_kind is FailureKind.PERMANENT
    assert calls == 0


@pytest.mark.asyncio
async def test_explicit_tool_retries_and_reports_timeout() -> None:
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        raise ConnectionError("temporary")

    executor = ToolExecutor(ToolRegistry(), default_timeout=0.1, retry_policy=RetryPolicy(max_attempts=2, initial_delay=0))
    runtime = Runtime(executor)
    result = await runtime.execute_explicit_tool(CallTool("flaky", {}), Tool("flaky", flaky, retry_safety=RetrySafety.SAFE))

    assert result.status is ToolResultStatus.FAILED
    assert result.failure_kind is FailureKind.TRANSIENT
    assert result.attempts == 2
    assert calls == 2


@pytest.mark.asyncio
async def test_explicit_tool_lock_timeout_does_not_invoke() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    waiting_calls = 0

    async def hold() -> str:
        started.set()
        await release.wait()
        return "hold"

    async def waiting() -> str:
        nonlocal waiting_calls
        waiting_calls += 1
        return "waiting"

    runtime = Runtime(ToolExecutor(ToolRegistry()), lock_timeout=0.01)
    first = asyncio.create_task(runtime.execute_explicit_tool(CallTool("hold", {}), Tool("hold", hold, capabilities={"write"}, resources={"r": "write"})))
    await started.wait()
    result = await runtime.execute_explicit_tool(CallTool("waiting", {}), Tool("waiting", waiting, capabilities={"write"}, resources={"r": "write"}))
    release.set()
    await first

    assert result.failure_kind is FailureKind.RESOURCE_LOCK_TIMEOUT
    assert waiting_calls == 0


@pytest.mark.asyncio
async def test_explicit_batch_preserves_order_and_scopes_concurrency() -> None:
    active = 0
    peak = 0

    async def work(value: str) -> str:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return value

    runtime = Runtime(ToolExecutor(ToolRegistry()))
    items = [
        (CallTool("work", {"value": str(index)}), Tool("work", work, capabilities={"read"}))
        for index in range(5)
    ]
    results = await runtime.execute_explicit_batch(items, run_id="batch-run", max_concurrency=2)

    assert [result.value for result in results] == ["0", "1", "2", "3", "4"]
    assert peak == 2
    assert all(runtime.executor.get_tool("work") is None for _ in [0])


@pytest.mark.asyncio
async def test_explicit_batch_isolates_failure_and_cancellation() -> None:
    async def work(value: str) -> str:
        if value == "fail":
            raise RuntimeError("internal detail")
        if value == "cancel":
            raise asyncio.CancelledError
        return value

    runtime = Runtime(ToolExecutor(ToolRegistry()))
    tool = Tool("work", work, capabilities={"read"})
    results = await runtime.execute_explicit_batch(
        [
            (CallTool("work", {"value": "fail"}), tool),
            (CallTool("work", {"value": "cancel"}), tool),
            (CallTool("work", {"value": "ok"}), tool),
        ],
        run_id="batch-run",
    )

    assert results[0].status is ToolResultStatus.FAILED
    assert results[1].status is ToolResultStatus.CANCELLED
    assert results[1].failure_kind is FailureKind.CANCELLED
    assert results[2].status is ToolResultStatus.SUCCESS


@pytest.mark.asyncio
async def test_explicit_batch_timeout_and_retry_exhaustion_are_per_item() -> None:
    async def slow() -> str:
        await asyncio.sleep(0.05)
        return "late"

    async def flaky() -> str:
        raise ConnectionError("temporary")

    executor = ToolExecutor(
        ToolRegistry(),
        default_timeout=0.01,
        retry_policy=RetryPolicy(max_attempts=2, initial_delay=0),
    )
    runtime = Runtime(executor)
    results = await runtime.execute_explicit_batch(
        [
            (CallTool("slow", {}), Tool("slow", slow, capabilities={"read"})),
            (
                CallTool("flaky", {}),
                Tool("flaky", flaky, capabilities={"read"}, retry_safety=RetrySafety.SAFE),
            ),
        ],
        run_id="batch-run",
    )

    assert results[0].status is ToolResultStatus.TIMED_OUT
    assert results[0].failure_kind is FailureKind.TIMEOUT
    assert results[1].failure_kind is FailureKind.TRANSIENT
    assert results[1].attempts == 2


def test_batch_max_concurrency_rejects_invalid_values() -> None:
    runtime = Runtime(ToolExecutor(ToolRegistry()))
    for value in (0, -1, 1.5, "2", True):
        with pytest.raises(ValueError, match="max_concurrency"):
            runtime._validate_max_concurrency(value)  # type: ignore[arg-type]
