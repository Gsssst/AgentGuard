import asyncio
from collections import defaultdict

import pytest

from agentguard import (
    ApprovalDecision,
    CallTool,
    CheckpointStore,
    EventType,
    FailureKind,
    Finish,
    InMemoryEventSink,
    PermissionPolicy,
    RunPause,
    RunState,
    RunStatus,
    Runtime,
    SimulatedCrash,
    ToolResultStatus,
    action_digest,
)
from agentguard.events.contract import EventCorrelation, EventValidationError
from agentguard.events.normalize import normalize_runtime_event
from agentguard.runtime.policy import RetryPolicy, RetrySafety
from agentguard.runtime.tool import Tool, ToolExecutor, ToolRegistry


def _normalized(sink: InMemoryEventSink):
    return tuple(normalize_runtime_event(event) for event in sink.events)


def _by_call_id(sink: InMemoryEventSink):
    grouped = defaultdict(list)
    for event, fact in zip(sink.events, _normalized(sink), strict=True):
        if fact.correlation.call_id is not None:
            grouped[fact.correlation.call_id].append((event, fact))
    return grouped


@pytest.mark.asyncio
async def test_retry_reuses_supplied_call_identity_and_keeps_secrets_out_of_v1() -> None:
    attempts = 0

    async def flaky(*, token: str) -> dict[str, str]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError(f"RAW-ERROR-SECRET:{token}")
        return {"api_token": "RAW-RESULT-SECRET", "value": "ok"}

    sink = InMemoryEventSink()
    runtime = Runtime(
        ToolExecutor(
            ToolRegistry(),
            retry_policy=RetryPolicy(max_attempts=2, initial_delay=0),
        ),
        event_sink=sink,
    )
    result = await runtime.execute_explicit_tool(
        CallTool("flaky", {"token": "RAW-ARGUMENT-SECRET"}),
        Tool("flaky", flaky, retry_safety=RetrySafety.SAFE),
        run_id="run-retry",
        step=4,
        call_id="internal-call-retry",
        tool_call_id="external-call-retry",
    )

    assert result.status is ToolResultStatus.SUCCESS
    assert result.attempts == 2
    facts = _normalized(sink)
    assert {fact.correlation.call_id for fact in facts} == {"internal-call-retry"}
    assert {fact.correlation.tool_call_id for fact in facts} == {"external-call-retry"}
    assert [fact.event_type for fact in facts].count(EventType.TOOL_ATTEMPT_STARTED) == 2
    retry = next(fact for fact in facts if fact.event_type is EventType.RETRY_SCHEDULED)
    assert retry.payload["completed_attempt"] == 1
    assert retry.payload["next_attempt"] == 2
    serialized = repr([fact.payload for fact in facts])
    assert "RAW-ARGUMENT-SECRET" not in serialized
    assert "RAW-ERROR-SECRET" not in serialized
    assert "RAW-RESULT-SECRET" not in serialized


@pytest.mark.asyncio
async def test_timeout_permission_and_explicit_approval_events_are_normalizable() -> None:
    never = asyncio.Event()

    async def slow() -> None:
        await never.wait()

    timeout_sink = InMemoryEventSink()
    timeout_runtime = Runtime(
        ToolExecutor(ToolRegistry(), default_timeout=0.001),
        event_sink=timeout_sink,
    )
    timed_out = await timeout_runtime.execute_explicit_tool(
        CallTool("slow", {}),
        Tool("slow", slow),
        run_id="run-timeout",
        call_id="call-timeout",
    )
    assert timed_out.status is ToolResultStatus.TIMED_OUT
    assert {fact.correlation.call_id for fact in _normalized(timeout_sink)} == {"call-timeout"}

    permission_sink = InMemoryEventSink()
    permission_runtime = Runtime(
        ToolExecutor(ToolRegistry()),
        event_sink=permission_sink,
        permission_policy=PermissionPolicy(allowed={"read"}),
    )
    denied = await permission_runtime.execute_explicit_tool(
        CallTool("write", {}),
        Tool("write", lambda: "unreachable", capabilities={"write"}),
        run_id="run-permission",
        call_id="call-permission",
    )
    assert denied.error_type == "PermissionDenied"
    assert next(
        fact for fact in _normalized(permission_sink)
        if fact.event_type is EventType.PERMISSION_DENIED
    ).correlation.call_id == "call-permission"

    approval_sink = InMemoryEventSink()
    approval_runtime = Runtime(ToolExecutor(ToolRegistry()), event_sink=approval_sink)
    action = CallTool("write", {"value": "approved"})
    tool = Tool("write", lambda value: value, capabilities={"write"})
    digest = action_digest(
        action,
        capabilities=tool.capabilities,
        run_id="run-approval",
        step=7,
    )
    granted = await approval_runtime.execute_explicit_tool(
        action,
        tool,
        run_id="run-approval",
        step=7,
        approval=ApprovalDecision(True, actor="tester", action_digest=digest),
        call_id="call-approval",
    )
    denied = await approval_runtime.execute_explicit_tool(
        action,
        tool,
        run_id="run-approval-denied",
        step=7,
        approval=ApprovalDecision(False, actor="tester", reason="RAW-DENIAL-SECRET"),
        call_id="call-approval-denied",
    )
    assert granted.status is ToolResultStatus.SUCCESS
    assert denied.error_type == "PermissionDenied"
    approval_facts = _normalized(approval_sink)
    assert any(fact.event_type is EventType.APPROVAL_GRANTED for fact in approval_facts)
    assert any(fact.event_type is EventType.APPROVAL_DENIED for fact in approval_facts)
    assert "RAW-DENIAL-SECRET" not in repr([fact.payload for fact in approval_facts])


@pytest.mark.asyncio
async def test_resource_lock_timeout_keeps_waiting_call_identity() -> None:
    holder_started = asyncio.Event()
    release_holder = asyncio.Event()
    waiting_calls = 0

    async def hold() -> str:
        holder_started.set()
        await release_holder.wait()
        return "held"

    async def waiting() -> str:
        nonlocal waiting_calls
        waiting_calls += 1
        return "unexpected"

    sink = InMemoryEventSink()
    runtime = Runtime(
        ToolExecutor(ToolRegistry()),
        event_sink=sink,
        lock_timeout=0,
    )
    holder = asyncio.create_task(
        runtime.execute_explicit_tool(
            CallTool("hold", {}),
            Tool("hold", hold, capabilities={"write"}, resources={"shared": "write"}),
            run_id="run-locks",
            call_id="call-holder",
        )
    )
    await holder_started.wait()
    blocked = await runtime.execute_explicit_tool(
        CallTool("waiting", {}),
        Tool("waiting", waiting, capabilities={"write"}, resources={"shared": "write"}),
        run_id="run-locks",
        step=1,
        call_id="call-waiting",
    )
    release_holder.set()
    await holder

    assert blocked.failure_kind is FailureKind.RESOURCE_LOCK_TIMEOUT
    assert waiting_calls == 0
    lock_timeout = next(
        fact for fact in _normalized(sink)
        if fact.event_type is EventType.RESOURCE_LOCK_TIMEOUT
    )
    assert lock_timeout.correlation.call_id == "call-waiting"


class _RecoveryRouter:
    async def next_action(self, state: RunState):
        return CallTool("echo", {"value": state.step}) if state.step < 2 else Finish("done")


@pytest.mark.asyncio
async def test_checkpoint_resume_recreates_pre_crash_logical_call_id(tmp_path) -> None:
    hook_calls = 0

    async def echo(value: int) -> int:
        return value

    def crash_on_second_tool(boundary: str) -> None:
        nonlocal hook_calls
        if boundary == "after_tool_before_checkpoint":
            hook_calls += 1
            if hook_calls == 2:
                raise SimulatedCrash(boundary)

    path = tmp_path / "checkpoints" / "stable-call.json"
    sink = InMemoryEventSink()
    crashing = Runtime(
        ToolExecutor(ToolRegistry({"echo": echo})),
        event_sink=sink,
        checkpoint_store=CheckpointStore(path.parent),
        checkpoint_path=path,
        crash_hook=crash_on_second_tool,
    )
    with pytest.raises(SimulatedCrash):
        await crashing.run(_RecoveryRouter(), RunState("run-stable-recovery"))

    before_resume = len(sink.events)
    replayed_source_call_id = next(
        event.data["call_id"]
        for event in reversed(sink.events)
        if event.event_type is EventType.TOOL_SUCCEEDED
    )
    resumed = Runtime(
        ToolExecutor(ToolRegistry({"echo": echo})),
        event_sink=sink,
        checkpoint_store=CheckpointStore(path.parent),
    )
    result = await resumed.resume(path, _RecoveryRouter())

    assert result.status is RunStatus.COMPLETED
    replayed_events = sink.events[before_resume:]
    assert any(
        event.data.get("call_id") == replayed_source_call_id
        and event.event_type is EventType.ACTION_PROPOSED
        for event in replayed_events
    )
    replayed_facts = [normalize_runtime_event(event) for event in replayed_events]
    assert any(fact.payload.get("resume_attempt") == 1 for fact in replayed_facts)
    assert any(fact.payload.get("duplicate_possible") is True for fact in replayed_facts)


@pytest.mark.asyncio
async def test_approval_checkpoint_resume_reuses_requested_call_id(tmp_path) -> None:
    class ApprovalRouter:
        async def next_action(self, state: RunState):
            return CallTool("send", {"value": "ok"}) if state.step == 0 else Finish("done")

    registry = ToolRegistry()
    registry.register("send", lambda value: value, capabilities={"external"})
    path = tmp_path / "approval.json"
    sink = InMemoryEventSink()
    runtime = Runtime(
        ToolExecutor(registry),
        event_sink=sink,
        checkpoint_store=CheckpointStore(path.parent),
        checkpoint_path=path,
        permission_policy=PermissionPolicy(approval_required={"external"}),
    )
    pause = await runtime.run(ApprovalRouter(), RunState("run-approval-resume"))
    assert isinstance(pause, RunPause)
    requested = next(
        fact for fact in _normalized(sink)
        if fact.event_type is EventType.APPROVAL_REQUESTED
    )

    resumed = Runtime(
        ToolExecutor(registry),
        event_sink=sink,
        checkpoint_store=CheckpointStore(path.parent),
        permission_policy=PermissionPolicy(approval_required={"external"}),
    )
    result = await resumed.resume(
        path,
        ApprovalRouter(),
        ApprovalDecision(True, actor="tester", action_digest=pause.action_digest),
    )
    assert result.status is RunStatus.COMPLETED
    grouped = _by_call_id(sink)
    lifecycle = [fact.event_type for _source, fact in grouped[requested.correlation.call_id]]
    assert EventType.APPROVAL_REQUESTED in lifecycle
    assert EventType.APPROVAL_GRANTED in lifecycle
    assert EventType.TOOL_SUCCEEDED in lifecycle


@pytest.mark.asyncio
async def test_registry_batch_separates_run_batch_and_member_identities() -> None:
    async def work(value: str) -> str:
        if value == "bad":
            raise RuntimeError("RAW-BATCH-ERROR")
        if value == "cancel":
            raise asyncio.CancelledError
        return value

    registry = ToolRegistry()
    registry.register("work", work)
    sink = InMemoryEventSink()
    runtime = Runtime(ToolExecutor(registry), event_sink=sink)
    results = await runtime.execute_batch(
        [
            CallTool("work", {"value": "bad"}),
            CallTool("work", {"value": "cancel"}),
            CallTool("work", {"value": "good"}),
        ],
        run_id="real-run-id",
        batch_id="separate-batch-id",
    )

    assert [result.status for result in results] == [
        ToolResultStatus.FAILED,
        ToolResultStatus.CANCELLED,
        ToolResultStatus.SUCCESS,
    ]
    facts = _normalized(sink)
    assert {fact.run_id for fact in facts} == {"real-run-id"}
    assert {fact.correlation.batch_id for fact in facts} == {"separate-batch-id"}
    grouped = _by_call_id(sink)
    assert len(grouped) == 3
    assert all(group for group in grouped.values())
    assert "RAW-BATCH-ERROR" not in repr([fact.payload for fact in facts])
    boundaries = [fact for fact in facts if fact.event_type in {EventType.BATCH_STARTED, EventType.BATCH_FINISHED}]
    assert [fact.event_type for fact in boundaries] == [EventType.BATCH_STARTED, EventType.BATCH_FINISHED]
    assert all(fact.correlation.call_id is None for fact in boundaries)


@pytest.mark.asyncio
async def test_explicit_subset_preserves_supplied_context_without_boundaries() -> None:
    sink = InMemoryEventSink()
    runtime = Runtime(ToolExecutor(ToolRegistry()), event_sink=sink)
    results = await runtime.execute_explicit_batch(
        [
            (CallTool("work", {"value": "first"}), Tool("work", lambda value: value)),
            (CallTool("work", {"value": "second"}), Tool("work", lambda value: value)),
        ],
        run_id="adapter-run-real",
        batch_id="adapter-batch-separate",
        step_indices={0: 3, 1: 8},
        correlation_contexts={
            0: EventCorrelation(
                call_id="internal-three",
                tool_call_id="external-three",
                batch_id="adapter-batch-separate",
            ),
            1: EventCorrelation(
                call_id="internal-eight",
                tool_call_id="external-eight",
                batch_id="adapter-batch-separate",
            ),
        },
        emit_batch_lifecycle=False,
    )

    assert [result.value for result in results] == ["first", "second"]
    facts = _normalized(sink)
    assert not any(
        fact.event_type in {EventType.BATCH_STARTED, EventType.BATCH_FINISHED}
        for fact in facts
    )
    assert {fact.run_id for fact in facts} == {"adapter-run-real"}
    assert {fact.correlation.batch_id for fact in facts} == {"adapter-batch-separate"}
    assert set(_by_call_id(sink)) == {"internal-three", "internal-eight"}
    assert {fact.correlation.tool_call_id for fact in facts} == {
        "external-three",
        "external-eight",
    }


def test_correlation_inputs_and_framework_event_seam_fail_closed() -> None:
    sink = InMemoryEventSink()
    runtime = Runtime(ToolExecutor(ToolRegistry()), event_sink=sink)
    tool = Tool("work", lambda: "ok")

    legacy = asyncio.run(runtime.execute_explicit_tool(CallTool("work", {}), tool))
    assert legacy.status is ToolResultStatus.SUCCESS
    assert len(_by_call_id(sink)) == 1

    for invalid in (True, "", " padded "):
        with pytest.raises((TypeError, ValueError, EventValidationError)):
            asyncio.run(
                runtime.execute_explicit_tool(
                    CallTool("work", {}),
                    tool,
                    call_id=invalid,  # type: ignore[arg-type]
                )
            )

    before = len(sink.events)
    with pytest.raises(EventValidationError):
        runtime.emit_framework_event(
            EventType.TOOL_FAILED,
            run_id="run-framework",
            step=0,
            correlation=EventCorrelation(),
            data={"tool_name": "work"},
        )
    assert len(sink.events) == before

    with pytest.raises(TypeError, match="raw exceptions"):
        runtime.emit_framework_event(
            EventType.TOOL_FAILED,
            run_id="run-framework",
            step=0,
            correlation=EventCorrelation(call_id="call-framework"),
            data={
                "tool_name": "work",
                "error_type": "RuntimeError",
                "error_message": RuntimeError("RAW-FRAMEWORK-SECRET"),
                "failure_kind": "permanent",
                "attempts": 1,
            },
        )
    assert len(sink.events) == before
