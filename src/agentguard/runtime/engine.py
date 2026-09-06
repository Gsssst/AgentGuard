"""The deterministic Runtime loop and explicit independent batch execution."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Iterable, Mapping
from typing import Callable
from typing import Any
from uuid import UUID, uuid4, uuid5

from agentguard.domain.actions import Action, CallTool, Finish
from agentguard.domain.runtime import RunPause, RunResult
from agentguard.domain.results import FailureKind, ToolResult, ToolResultStatus
from agentguard.domain.state import RunState, RunStatus, StopReason
from agentguard.events.contract import EventCorrelation
from agentguard.events.model import EventType, RuntimeEvent
from agentguard.events.normalize import normalize_runtime_event
from agentguard.events.sinks import EventSink, InMemoryEventSink
from agentguard.checkpoint import Checkpoint, CheckpointLifecycle, CheckpointStore

from .router import Router
from .loop_guard import LoopGuard
from .tool import Tool, ToolExecutor
from .policy import classify_exception
from .permission import ApprovalDecision, PermissionDecisionKind, PermissionPolicy, action_digest, redact
from .resources import ResourceLockManager, ResourceLockTimeout


class SimulatedCrash(RuntimeError):
    """Deterministic fault injected at a named Runtime boundary."""


CrashHook = Callable[[str], None]


_CALL_ID_NAMESPACE = UUID("8cd38f9e-6f71-4d88-9a8d-2c7083a517ce")


def _validate_identifier(value: Any, *, name: str) -> str:
    """Validate a public correlation coordinate without coercing caller data."""

    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > 256 or any(ord(character) < 32 for character in value):
        raise ValueError(f"{name} must be a valid identifier")
    return value


def _validate_step(step: Any) -> int:
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise ValueError("step must be a non-negative integer")
    return step


@dataclass
class Runtime:
    """Drive one Router and one ToolExecutor until a terminal outcome."""

    executor: ToolExecutor
    max_steps: int = 10
    event_sink: EventSink | None = None
    loop_guard: LoopGuard | None = None
    checkpoint_store: CheckpointStore | None = None
    checkpoint_path: str | Path | None = None
    crash_hook: CrashHook | None = None
    resume_attempt: int = 0
    duplicate_possible: bool = False
    permission_policy: PermissionPolicy | None = None
    lock_manager: ResourceLockManager | None = None
    lock_timeout: float | None = 5.0
    _event_sequence: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.event_sink is None:
            self.event_sink = InMemoryEventSink()
        if self.loop_guard is None:
            self.loop_guard = LoopGuard()
        if self.checkpoint_path is not None:
            self.checkpoint_path = Path(self.checkpoint_path)
        if self.checkpoint_store is None and self.checkpoint_path is not None:
            self.checkpoint_store = CheckpointStore(Path(self.checkpoint_path).parent)
        if self.lock_timeout is not None and self.lock_timeout < 0:
            raise ValueError("lock_timeout cannot be negative")
        if self.lock_manager is None:
            self.lock_manager = ResourceLockManager()

    async def run(
        self,
        router: Router,
        state: RunState | None = None,
        *,
        _pending_action: CallTool | None = None,
        _pending_capabilities: frozenset[str] = frozenset(),
        _skip_permission_once: bool = False,
    ) -> RunResult | RunPause:
        """Run one state-driven, sequential Action loop."""

        state = state or RunState(run_id="run-001")
        if self.resume_attempt == 0:
            self._event_sequence = 0
        self._emit(EventType.RUN_STARTED, state)

        while state.status is RunStatus.RUNNING:
            if state.step >= self.max_steps:
                return self._finish(state, RunStatus.FAILED, StopReason.STEP_BUDGET_EXCEEDED)

            if _pending_action is not None:
                action = _pending_action
                _pending_action = None
            else:
                try:
                    action = await router.next_action(state)
                except Exception:
                    # Router failures are treated as invalid decisions at this
                    # stage; later phases may introduce a dedicated reason.
                    return self._finish(state, RunStatus.FAILED, StopReason.INVALID_ACTION)

            if not isinstance(action, (CallTool, Finish)):
                return self._finish(state, RunStatus.FAILED, StopReason.INVALID_ACTION)

            correlation = (
                self._make_correlation(run_id=state.run_id, step=state.step)
                if isinstance(action, CallTool)
                else EventCorrelation()
            )
            self._emit(
                EventType.ACTION_PROPOSED,
                state,
                correlation=correlation,
                action_type=type(action).__name__,
                **(
                    {"tool_name": action.tool_name, "arguments": redact(action.arguments)}
                    if isinstance(action, CallTool)
                    else {"reason": action.reason}
                ),
            )

            if isinstance(action, Finish):
                state.record(action)
                state.step += 1
                return self._finish(state, RunStatus.COMPLETED, StopReason.COMPLETED)

            if self.permission_policy is not None and not _skip_permission_once:
                tool = self.executor.get_tool(action.tool_name)
                capabilities = tool.capabilities if tool is not None else frozenset()
                decision = self.permission_policy.decide(capabilities)
                if decision.kind is PermissionDecisionKind.DENY:
                    self._emit(
                        EventType.PERMISSION_DENIED,
                        state,
                        correlation=correlation,
                        tool_name=action.tool_name,
                        required_capabilities=sorted(decision.required_capabilities),
                        forbidden_capabilities=sorted(decision.forbidden_capabilities),
                        decision=decision.kind.value,
                    )
                    return self._finish(state, RunStatus.FAILED, StopReason.PERMISSION_DENIED)
                if decision.kind is PermissionDecisionKind.APPROVAL_REQUIRED:
                    digest = action_digest(
                        action,
                        capabilities=capabilities,
                        run_id=state.run_id,
                        step=state.step,
                    )
                    state.status = RunStatus.WAITING_APPROVAL
                    self._emit(
                        EventType.APPROVAL_REQUESTED,
                        state,
                        correlation=correlation,
                        tool_name=action.tool_name,
                        required_capabilities=sorted(decision.required_capabilities),
                        decision=decision.kind.value,
                        action_digest=digest,
                        arguments=redact(action.arguments),
                        status=RunStatus.WAITING_APPROVAL.value,
                    )
                    self._save_checkpoint(
                        state,
                        CheckpointLifecycle.ACTIVE,
                        pending_action=action,
                        pending_capabilities=capabilities,
                        action_digest=digest,
                    )
                    return RunPause(
                        run_id=state.run_id,
                        status=RunStatus.WAITING_APPROVAL,
                        final_state=state,
                        pending_action=action,
                        action_digest=digest,
                    )

            _skip_permission_once = False

            assert self.loop_guard is not None
            loop_detected, signature, consecutive_count = self.loop_guard.observe(action)
            if loop_detected:
                self._emit(
                    EventType.LOOP_DETECTED,
                    state,
                    correlation=correlation,
                    signature=signature,
                    consecutive_count=consecutive_count,
                    threshold=self.loop_guard.threshold,
                )
                return self._finish(state, RunStatus.FAILED, StopReason.LOOP_DETECTED)

            try:
                assert self.lock_manager is not None
                tool = self.executor.get_tool(action.tool_name)
                resources = tool.resources if tool is not None else {}
                async with self.lock_manager.hold(resources, timeout=self.lock_timeout):
                    self._emit(
                        EventType.TOOL_STARTED,
                        state,
                        correlation=correlation,
                        tool_name=action.tool_name,
                    )
                    tool_result = await self.executor.execute(
                        action,
                        on_event=lambda event_type, data: self._emit(
                            event_type,
                            state,
                            correlation=correlation,
                            **data,
                        ),
                    )
            except ResourceLockTimeout as exc:
                self._emit(
                    EventType.RESOURCE_LOCK_TIMEOUT,
                    state,
                    correlation=correlation,
                    tool_name=action.tool_name,
                    resources=sorted(resources),
                    error_message=str(exc),
                )
                tool_result = ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.FAILED,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    failure_kind=FailureKind.RESOURCE_LOCK_TIMEOUT,
                    attempts=0,
                )
            state.record(action, tool_result)
            state.step += 1

            if tool_result.status is ToolResultStatus.SUCCESS:
                self._emit(
                    EventType.TOOL_SUCCEEDED,
                    state,
                    correlation=correlation,
                    tool_name=tool_result.tool_name,
                    value=tool_result.value,
                    attempts=tool_result.attempts,
                )
            elif tool_result.status is ToolResultStatus.TIMED_OUT:
                self._emit(
                    EventType.TOOL_TIMED_OUT,
                    state,
                    correlation=correlation,
                    tool_name=tool_result.tool_name,
                    attempts=tool_result.attempts,
                    timeout_seconds=tool_result.timeout_seconds,
                    timeout_source=tool_result.timeout_source,
                )
            elif tool_result.status is ToolResultStatus.CANCELLED:
                self._emit(
                    EventType.TOOL_CANCELLED,
                    state,
                    correlation=correlation,
                    tool_name=tool_result.tool_name,
                    attempts=tool_result.attempts,
                )
            else:
                self._emit(
                    EventType.TOOL_FAILED,
                    state,
                    correlation=correlation,
                    tool_name=tool_result.tool_name,
                    error_type=tool_result.error_type,
                    error_message=tool_result.error_message,
                    failure_kind=(
                        tool_result.failure_kind.value
                        if tool_result.failure_kind is not None
                        else None
                    ),
                    attempts=tool_result.attempts,
                )

            if self.crash_hook is not None:
                self.crash_hook("after_tool_before_checkpoint")
            self._save_checkpoint(state, CheckpointLifecycle.ACTIVE)

            if tool_result.error_type == "UnknownTool":
                return self._finish(state, RunStatus.FAILED, StopReason.INVALID_ACTION)
            if tool_result.status is ToolResultStatus.TIMED_OUT:
                continue
            if tool_result.status is not ToolResultStatus.SUCCESS:
                return self._finish(state, RunStatus.FAILED, StopReason.TOOL_FAILED)

        # The loop only exits through a terminal result today, but retaining a
        # defensive fallback prevents returning a non-terminal RunResult if
        # future status values are added.
        return self._finish(state, RunStatus.FAILED, StopReason.INVALID_ACTION)

    async def resume(
        self,
        checkpoint_path: str | Path,
        router: Router,
        approval: ApprovalDecision | None = None,
    ) -> RunResult | RunPause:
        """Explicitly restore a checkpoint, then continue the same loop."""

        path = Path(checkpoint_path)
        store = self.checkpoint_store or CheckpointStore(path.parent)
        checkpoint = store.load(path)
        # Validation completes before any event, Router, or Tool side effect.
        self.checkpoint_store = store
        self.checkpoint_path = path
        self.max_steps = checkpoint.max_steps
        self.resume_attempt = checkpoint.resume_attempt + 1
        self.duplicate_possible = True
        self._event_sequence = checkpoint.event_position
        if checkpoint.lifecycle in (CheckpointLifecycle.COMPLETED, CheckpointLifecycle.FAILED):
            raise ValueError("cannot resume a terminal checkpoint")
        approval_granted = False
        approval_denied = False
        approval_tool_name: str | None = None
        approval_capabilities: frozenset[str] = frozenset()
        approval_expected_digest: str | None = None
        if checkpoint.state.status is RunStatus.WAITING_APPROVAL:
            if checkpoint.pending_action is None or checkpoint.action_digest is None:
                raise ValueError("waiting checkpoint is missing pending approval metadata")
            if approval is None:
                raise ValueError("approval decision is required to resume a waiting checkpoint")
            tool = self.executor.get_tool(checkpoint.pending_action.tool_name)
            if tool is None:
                raise ValueError("pending approval Tool is no longer registered")
            expected = action_digest(
                checkpoint.pending_action,
                capabilities=tool.capabilities,
                run_id=checkpoint.run_id,
                step=checkpoint.state.step,
            )
            if expected != checkpoint.action_digest or approval.action_digest != expected:
                raise ValueError("approval action digest does not match pending Action")
            pending_action = checkpoint.pending_action
            pending_capabilities = checkpoint.pending_capabilities
            approval_granted = approval.approved
            approval_denied = not approval.approved
            approval_tool_name = checkpoint.pending_action.tool_name
            approval_capabilities = checkpoint.pending_capabilities
            approval_expected_digest = expected
        else:
            pending_action = None
            pending_capabilities = frozenset()
        approval_correlation = (
            self._make_correlation(
                run_id=checkpoint.run_id,
                step=checkpoint.state.step,
            )
            if pending_action is not None
            else EventCorrelation()
        )
        self._emit(
            EventType.RESUME_STARTED,
            checkpoint.state,
            resume_attempt=self.resume_attempt,
            duplicate_possible=True,
            checkpoint_path=str(path),
        )
        if approval_denied:
            checkpoint.state.status = RunStatus.FAILED
            self._emit(
                EventType.APPROVAL_DENIED,
                checkpoint.state,
                correlation=approval_correlation,
                tool_name=approval_tool_name,
                required_capabilities=sorted(approval_capabilities),
                action_digest=approval_expected_digest,
                actor=approval.actor if approval is not None else None,
                reason=approval.reason if approval is not None else None,
            )
            return self._finish(checkpoint.state, RunStatus.FAILED, StopReason.PERMISSION_DENIED)
        if approval_granted:
            checkpoint.state.status = RunStatus.RUNNING
            self._emit(
                EventType.APPROVAL_GRANTED,
                checkpoint.state,
                correlation=approval_correlation,
                tool_name=approval_tool_name,
                required_capabilities=sorted(approval_capabilities),
                action_digest=approval_expected_digest,
                actor=approval.actor if approval is not None else None,
                reason=approval.reason if approval is not None else None,
            )
        return await self.run(
            router,
            checkpoint.state,
            _pending_action=pending_action,
            _pending_capabilities=pending_capabilities,
            _skip_permission_once=pending_action is not None,
        )

    async def execute_explicit_tool(
        self,
        action: CallTool,
        tool: Tool,
        *,
        run_id: str = "adapter-run",
        step: int = 0,
        approval: ApprovalDecision | None = None,
        call_id: str | None = None,
        tool_call_id: str | None = None,
        batch_id: str | None = None,
    ) -> ToolResult:
        """Execute an adapter-owned Tool through this Runtime's controls.

        The supplied Tool is intentionally not inserted into the Runtime's
        registry. This is the bridge used by framework adapters that maintain
        their own tool collection while reusing AgentGuard policy and evidence.
        """

        if not isinstance(action, CallTool):
            raise TypeError("action must be a CallTool")
        if not isinstance(tool, Tool):
            raise TypeError("tool must be a Tool")
        if tool.name != action.tool_name:
            raise ValueError("tool name must match action.tool_name")
        run_id = _validate_identifier(run_id, name="run_id")
        step = _validate_step(step)
        correlation = self._make_correlation(
            run_id=run_id,
            step=step,
            call_id=call_id,
            tool_call_id=tool_call_id,
            batch_id=batch_id,
        )

        if approval is not None and not isinstance(approval, ApprovalDecision):
            raise TypeError("approval must be an ApprovalDecision")

        self._emit_external(
            EventType.ACTION_PROPOSED,
            run_id,
            step,
            correlation=correlation,
            action_type="CallTool",
            tool_name=tool.name,
            arguments=redact(action.arguments),
        )
        if self.permission_policy is not None:
            decision = self.permission_policy.decide(tool.capabilities)
            if decision.kind is PermissionDecisionKind.DENY:
                self._emit_external(
                    EventType.PERMISSION_DENIED,
                    run_id,
                    step,
                    correlation=correlation,
                    tool_name=tool.name,
                    required_capabilities=sorted(decision.required_capabilities),
                    forbidden_capabilities=sorted(decision.forbidden_capabilities),
                    decision=decision.kind.value,
                )
                return ToolResult(
                    tool_name=tool.name,
                    status=ToolResultStatus.FAILED,
                    error_type="PermissionDenied",
                    error_message=str(decision.denial),
                    failure_kind=FailureKind.PERMANENT,
                    attempts=0,
                )
            if decision.kind is PermissionDecisionKind.APPROVAL_REQUIRED:
                expected_digest = action_digest(
                    action,
                    capabilities=tool.capabilities,
                    run_id=run_id,
                    step=step,
                )
                if approval is None:
                    self._emit_external(
                        EventType.APPROVAL_REQUESTED,
                        run_id,
                        step,
                        correlation=correlation,
                        tool_name=tool.name,
                        required_capabilities=sorted(decision.required_capabilities),
                        decision=decision.kind.value,
                        action_digest=expected_digest,
                        arguments=redact(action.arguments),
                        status=RunStatus.WAITING_APPROVAL.value,
                    )
                    return ToolResult(
                        tool_name=tool.name,
                        status=ToolResultStatus.FAILED,
                        error_type="ApprovalRequired",
                        error_message="approval was not granted",
                        failure_kind=FailureKind.PERMANENT,
                        attempts=0,
                    )

        if approval is not None:
            expected_digest = action_digest(
                action,
                capabilities=tool.capabilities,
                run_id=run_id,
                step=step,
            )
            if not approval.approved:
                self._emit_external(
                    EventType.APPROVAL_DENIED,
                    run_id,
                    step,
                    correlation=correlation,
                    tool_name=tool.name,
                    required_capabilities=sorted(tool.capabilities),
                    action_digest=expected_digest,
                    actor=approval.actor,
                    reason=approval.reason,
                )
                return ToolResult(
                    tool_name=tool.name,
                    status=ToolResultStatus.FAILED,
                    error_type="PermissionDenied",
                    error_message="approval was not granted",
                    failure_kind=FailureKind.PERMANENT,
                    attempts=0,
                )
            if approval.action_digest != expected_digest:
                self._emit_external(
                    EventType.APPROVAL_DENIED,
                    run_id,
                    step,
                    correlation=correlation,
                    tool_name=tool.name,
                    required_capabilities=sorted(tool.capabilities),
                    action_digest=expected_digest,
                    actor=approval.actor,
                    reason="approval digest mismatch",
                )
                return ToolResult(
                    tool_name=tool.name,
                    status=ToolResultStatus.FAILED,
                    error_type="PermissionDenied",
                    error_message="approval digest does not match action",
                    failure_kind=FailureKind.PERMANENT,
                    attempts=0,
                )
            self._emit_external(
                EventType.APPROVAL_GRANTED,
                run_id,
                step,
                correlation=correlation,
                tool_name=tool.name,
                required_capabilities=sorted(tool.capabilities),
                action_digest=approval.action_digest,
                actor=approval.actor,
                reason=approval.reason,
            )

        resources = tool.resources
        try:
            assert self.lock_manager is not None
            async with self.lock_manager.hold(resources, timeout=self.lock_timeout):
                self._emit_external(
                    EventType.TOOL_STARTED,
                    run_id,
                    step,
                    correlation=correlation,
                    tool_name=tool.name,
                )
                result = await self.executor.execute_explicit(
                    action,
                    tool,
                    on_event=lambda event_type, data: self._emit_external(
                        event_type,
                        run_id,
                        step,
                        correlation=correlation,
                        **data,
                    ),
                )
        except ResourceLockTimeout as exc:
            self._emit_external(
                EventType.RESOURCE_LOCK_TIMEOUT,
                run_id,
                step,
                correlation=correlation,
                tool_name=tool.name,
                resources=sorted(resources),
                error_message=str(exc),
            )
            result = ToolResult(
                tool_name=tool.name,
                status=ToolResultStatus.FAILED,
                error_type=type(exc).__name__,
                error_message=str(exc),
                failure_kind=FailureKind.RESOURCE_LOCK_TIMEOUT,
                attempts=0,
            )

        if result.status is ToolResultStatus.SUCCESS:
            self._emit_external(EventType.TOOL_SUCCEEDED, run_id, step, correlation=correlation, tool_name=result.tool_name, value=result.value, attempts=result.attempts)
        elif result.status is ToolResultStatus.TIMED_OUT:
            self._emit_external(EventType.TOOL_TIMED_OUT, run_id, step, correlation=correlation, tool_name=result.tool_name, attempts=result.attempts, timeout_seconds=result.timeout_seconds, timeout_source=result.timeout_source)
        elif result.status is ToolResultStatus.CANCELLED:
            self._emit_external(EventType.TOOL_CANCELLED, run_id, step, correlation=correlation, tool_name=result.tool_name, attempts=result.attempts)
        else:
            self._emit_external(
                EventType.TOOL_FAILED,
                run_id,
                step,
                correlation=correlation,
                tool_name=result.tool_name,
                error_type=result.error_type,
                error_message=result.error_message,
                failure_kind=result.failure_kind.value if result.failure_kind is not None else None,
                attempts=result.attempts,
            )
        return result

    async def execute_batch(
        self,
        actions: Iterable[CallTool],
        *,
        batch_id: str = "batch",
        max_concurrency: int | None = None,
        run_id: str | None = None,
    ) -> tuple[ToolResult, ...]:
        """Execute independent Tool Actions concurrently.

        Results retain input order. Tool failures and lock timeouts are
        isolated to their own result and do not cancel unrelated Actions.
        """

        try:
            batch = tuple(actions)
        except TypeError as exc:
            raise TypeError("actions must be an iterable of CallTool values") from exc
        if not batch:
            return ()
        if any(not isinstance(action, CallTool) for action in batch):
            raise TypeError("execute_batch accepts only CallTool actions")
        batch_id = _validate_identifier(batch_id, name="batch_id")
        run_id = (
            f"batch-run-{uuid4().hex}"
            if run_id is None
            else _validate_identifier(run_id, name="run_id")
        )
        self._validate_max_concurrency(max_concurrency)
        self._emit_batch_event(
            EventType.BATCH_STARTED,
            run_id=run_id,
            batch_id=batch_id,
            size=len(batch),
        )

        async def execute_one(index: int, action: CallTool) -> ToolResult:
            correlation = self._make_correlation(
                run_id=run_id,
                step=index,
                batch_id=batch_id,
                batch_index=index,
            )
            tool = self.executor.get_tool(action.tool_name)
            if tool is not None:
                return await self.execute_explicit_tool(
                    action,
                    tool,
                    run_id=run_id,
                    step=index,
                    call_id=correlation.call_id,
                    batch_id=batch_id,
                )

            self._emit_external(
                EventType.ACTION_PROPOSED,
                run_id,
                index,
                correlation=correlation,
                action_type="CallTool",
                tool_name=action.tool_name,
                arguments=redact(action.arguments),
            )
            if self.permission_policy is not None:
                decision = self.permission_policy.decide(frozenset())
                if decision.kind is PermissionDecisionKind.DENY:
                    self._emit_external(
                        EventType.PERMISSION_DENIED,
                        run_id,
                        index,
                        correlation=correlation,
                        tool_name=action.tool_name,
                        required_capabilities=[],
                        forbidden_capabilities=[],
                        decision=decision.kind.value,
                    )
                    return ToolResult(
                        tool_name=action.tool_name,
                        status=ToolResultStatus.FAILED,
                        error_type="PermissionDenied",
                        error_message=str(decision.denial),
                        failure_kind=FailureKind.PERMANENT,
                        attempts=0,
                    )
            self._emit_external(
                EventType.TOOL_STARTED,
                run_id,
                index,
                correlation=correlation,
                tool_name=action.tool_name,
            )
            result = await self.executor.execute(action)
            self._emit_external(
                EventType.TOOL_FAILED,
                run_id,
                index,
                correlation=correlation,
                tool_name=result.tool_name,
                error_type=result.error_type,
                error_message=result.error_message,
                failure_kind=result.failure_kind.value if result.failure_kind else None,
                attempts=result.attempts,
            )
            return result

        semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency is not None else None

        async def bounded(index: int, action: CallTool) -> ToolResult:
            correlation = self._make_correlation(
                run_id=run_id,
                step=index,
                batch_id=batch_id,
                batch_index=index,
            )
            try:
                if semaphore is None:
                    return await execute_one(index, action)
                async with semaphore:
                    return await execute_one(index, action)
            except asyncio.CancelledError:
                result = ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.CANCELLED,
                    error_type="CancelledError",
                    error_message="tool execution was cancelled",
                    failure_kind=FailureKind.CANCELLED,
                    attempts=0,
                )
                self._emit_external(
                    EventType.TOOL_CANCELLED,
                    run_id,
                    index,
                    correlation=correlation,
                    tool_name=action.tool_name,
                    attempts=0,
                )
                return result
            except Exception as exc:
                result = ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.FAILED,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    failure_kind=classify_exception(exc),
                    attempts=0,
                )
                self._emit_external(
                    EventType.TOOL_FAILED,
                    run_id,
                    index,
                    correlation=correlation,
                    tool_name=action.tool_name,
                    error_type=result.error_type,
                    error_message=result.error_message,
                    failure_kind=result.failure_kind.value if result.failure_kind else None,
                    attempts=0,
                )
                return result

        results = tuple(
            await asyncio.gather(
                *(bounded(index, action) for index, action in enumerate(batch))
            )
        )
        self._emit_batch_event(
            EventType.BATCH_FINISHED,
            run_id=run_id,
            batch_id=batch_id,
            size=len(results),
            failed=sum(result.status is not ToolResultStatus.SUCCESS for result in results),
        )
        return results

    async def execute_explicit_batch(
        self,
        items: Iterable[tuple[CallTool, Tool]],
        *,
        run_id: str = "adapter-run",
        max_concurrency: int | None = None,
        approval_context: Mapping[int, ApprovalDecision] | None = None,
        step_indices: Mapping[int, int] | None = None,
        correlation_contexts: Mapping[int, EventCorrelation] | None = None,
        batch_id: str | None = None,
        emit_batch_lifecycle: bool = True,
    ) -> tuple[ToolResult, ...]:
        """Execute adapter-owned Tools through Runtime controls.

        Tools are supplied directly and never inserted into the Runtime
        registry. Results preserve input order while individual exceptions and
        cancellations are isolated to their own item.
        """

        try:
            batch = tuple(items)
        except TypeError as exc:
            raise TypeError("items must be an iterable of (CallTool, Tool) pairs") from exc
        for item in batch:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("items must contain (CallTool, Tool) pairs")
            action, tool = item
            if not isinstance(action, CallTool):
                raise TypeError("batch actions must be CallTool values")
            if not isinstance(tool, Tool):
                raise TypeError("batch tools must be AgentGuard Tool values")
            if tool.name != action.tool_name:
                raise ValueError("tool name must match action.tool_name")
        run_id = _validate_identifier(run_id, name="run_id")
        if approval_context is not None:
            if not isinstance(approval_context, Mapping):
                raise TypeError("approval_context must be a mapping of input index to ApprovalDecision")
            if any(
                isinstance(index, bool) or not isinstance(index, int) or index < 0
                for index in approval_context
            ):
                raise TypeError("approval_context keys must be non-negative integers")
            if any(not isinstance(decision, ApprovalDecision) for decision in approval_context.values()):
                raise TypeError("approval_context values must be ApprovalDecision values")
        if step_indices is not None and (
            not isinstance(step_indices, Mapping)
            or any(
                isinstance(key, bool)
                or not isinstance(key, int)
                or key < 0
                or isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                for key, value in step_indices.items()
            )
        ):
            raise TypeError("step_indices must map batch positions to non-negative input indexes")
        if step_indices is not None and len(set(step_indices.values())) != len(step_indices):
            raise ValueError("step_indices values must be unique")
        if correlation_contexts is not None:
            if not isinstance(correlation_contexts, Mapping):
                raise TypeError("correlation_contexts must map input indexes to EventCorrelation values")
            if any(
                isinstance(index, bool) or not isinstance(index, int) or index < 0
                for index in correlation_contexts
            ):
                raise TypeError("correlation_contexts keys must be non-negative integers")
            if any(
                not isinstance(correlation, EventCorrelation)
                for correlation in correlation_contexts.values()
            ):
                raise TypeError("correlation_contexts values must be EventCorrelation values")
        if not isinstance(emit_batch_lifecycle, bool):
            raise TypeError("emit_batch_lifecycle must be a boolean")
        self._validate_max_concurrency(max_concurrency)
        if not batch:
            return ()

        batch_positions = set(range(len(batch)))
        for name, mapping in (
            ("approval_context", approval_context),
            ("step_indices", step_indices),
            ("correlation_contexts", correlation_contexts),
        ):
            if mapping is not None and not set(mapping).issubset(batch_positions):
                raise ValueError(f"{name} contains an out-of-range input index")

        supplied_batch_ids = {
            correlation.batch_id
            for correlation in (correlation_contexts or {}).values()
            if correlation.batch_id is not None
        }
        if len(supplied_batch_ids) > 1:
            raise ValueError("correlation_contexts must share one batch_id")
        if batch_id is None:
            batch_id = (
                next(iter(supplied_batch_ids))
                if supplied_batch_ids
                else f"batch-{uuid4().hex}"
            )
        else:
            batch_id = _validate_identifier(batch_id, name="batch_id")
        if supplied_batch_ids and supplied_batch_ids != {batch_id}:
            raise ValueError("correlation batch_id must match batch_id")

        if emit_batch_lifecycle:
            self._emit_batch_event(
                EventType.BATCH_STARTED,
                run_id=run_id,
                batch_id=batch_id,
                size=len(batch),
            )
        semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency is not None else None

        async def execute_one(index: int, action: CallTool, tool: Tool) -> ToolResult:
            step = step_indices.get(index, index) if step_indices else index
            supplied = (
                correlation_contexts.get(index)
                if correlation_contexts is not None
                else None
            )
            correlation = self._make_correlation(
                run_id=run_id,
                step=step,
                call_id=supplied.call_id if supplied is not None else None,
                tool_call_id=supplied.tool_call_id if supplied is not None else None,
                batch_id=batch_id,
                batch_index=step,
            )
            try:
                if semaphore is None:
                    return await self.execute_explicit_tool(
                        action,
                        tool,
                        run_id=run_id,
                        step=step,
                        approval=approval_context.get(index) if approval_context else None,
                        call_id=correlation.call_id,
                        tool_call_id=correlation.tool_call_id,
                        batch_id=batch_id,
                    )
                async with semaphore:
                    return await self.execute_explicit_tool(
                        action,
                        tool,
                        run_id=run_id,
                        step=step,
                        approval=approval_context.get(index) if approval_context else None,
                        call_id=correlation.call_id,
                        tool_call_id=correlation.tool_call_id,
                        batch_id=batch_id,
                    )
            except asyncio.CancelledError:
                self._emit_external(
                    EventType.TOOL_CANCELLED,
                    run_id,
                    step,
                    correlation=correlation,
                    tool_name=action.tool_name,
                    attempts=0,
                )
                return ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.CANCELLED,
                    error_type="CancelledError",
                    error_message="tool execution was cancelled",
                    failure_kind=FailureKind.CANCELLED,
                    attempts=0,
                )
            except Exception as exc:
                result = ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.FAILED,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    failure_kind=classify_exception(exc),
                    attempts=0,
                )
                self._emit_external(
                    EventType.TOOL_FAILED,
                    run_id,
                    step,
                    correlation=correlation,
                    tool_name=action.tool_name,
                    error_type=result.error_type,
                    error_message=result.error_message,
                    failure_kind=result.failure_kind.value if result.failure_kind else None,
                    attempts=0,
                )
                return result

        results = tuple(
            await asyncio.gather(
                *(execute_one(index, action, tool) for index, (action, tool) in enumerate(batch))
            )
        )
        if emit_batch_lifecycle:
            self._emit_batch_event(
                EventType.BATCH_FINISHED,
                run_id=run_id,
                batch_id=batch_id,
                size=len(results),
                failed=sum(result.status is not ToolResultStatus.SUCCESS for result in results),
            )
        return results

    @staticmethod
    def _validate_max_concurrency(max_concurrency: int | None) -> None:
        if max_concurrency is not None and (
            isinstance(max_concurrency, bool)
            or not isinstance(max_concurrency, int)
            or max_concurrency <= 0
        ):
            raise ValueError("max_concurrency must be a positive integer")

    def _finish(self, state: RunState, status: RunStatus, reason: StopReason) -> RunResult:
        state.status = status
        self._emit(
            EventType.RUN_FINISHED,
            state,
            status=status.value,
            stop_reason=reason.value,
        )
        lifecycle = (
            CheckpointLifecycle.COMPLETED
            if status is RunStatus.COMPLETED
            else CheckpointLifecycle.FAILED
        )
        self._save_checkpoint(state, lifecycle)
        return RunResult(
            run_id=state.run_id,
            status=status,
            stop_reason=reason,
            final_state=state,
        )

    @staticmethod
    def _make_correlation(
        *,
        run_id: str,
        step: int,
        call_id: str | None = None,
        tool_call_id: str | None = None,
        batch_id: str | None = None,
        batch_index: int | None = None,
    ) -> EventCorrelation:
        """Build one immutable logical-call identity from non-secret coordinates."""

        run_id = _validate_identifier(run_id, name="run_id")
        step = _validate_step(step)
        if batch_index is not None:
            batch_index = _validate_step(batch_index)
        if call_id is None:
            coordinate = (
                f"batch:{batch_id}:index:{batch_index}"
                if batch_id is not None and batch_index is not None
                else f"step:{step}"
            )
            call_id = str(uuid5(_CALL_ID_NAMESPACE, f"run:{run_id}:{coordinate}"))
        return EventCorrelation(
            call_id=call_id,
            tool_call_id=tool_call_id,
            batch_id=batch_id,
        )

    def _emit_source(
        self,
        event_type: EventType,
        *,
        run_id: str,
        step: int,
        correlation: EventCorrelation,
        data: Mapping[str, Any],
        validate_contract: bool = False,
    ) -> None:
        """Emit one source event with Runtime-owned sequence and correlation."""

        if not isinstance(event_type, EventType):
            raise TypeError("event_type must be an EventType")
        run_id = _validate_identifier(run_id, name="run_id")
        step = _validate_step(step)
        if not isinstance(correlation, EventCorrelation):
            raise TypeError("correlation must be an EventCorrelation")
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        if "sequence" in data or {"call_id", "tool_call_id", "batch_id"} & set(data):
            raise ValueError("sequence and correlation fields are Runtime-owned")

        event_data = dict(data)
        next_sequence = self._event_sequence + 1
        event_data["sequence"] = next_sequence
        event_data.setdefault("resume_attempt", self.resume_attempt)
        if self.duplicate_possible:
            event_data.setdefault("duplicate_possible", True)
        if correlation.call_id is not None:
            event_data["call_id"] = correlation.call_id
        if correlation.tool_call_id is not None:
            event_data["tool_call_id"] = correlation.tool_call_id
        if correlation.batch_id is not None:
            event_data["batch_id"] = correlation.batch_id

        event = RuntimeEvent(
            event_type=event_type,
            run_id=run_id,
            step=step,
            data=event_data,
        )
        if validate_contract:
            normalize_runtime_event(event)
        self._event_sequence = next_sequence
        assert self.event_sink is not None
        self.event_sink.emit(event)

    def emit_framework_event(
        self,
        event_type: EventType,
        *,
        run_id: str,
        step: int,
        correlation: EventCorrelation,
        data: Mapping[str, Any],
    ) -> None:
        """Safely emit a framework-owned fact through the strict v1 boundary."""

        self._emit_source(
            event_type,
            run_id=run_id,
            step=step,
            correlation=correlation,
            data=data,
            validate_contract=True,
        )

    def _emit(
        self,
        event_type: EventType,
        state: RunState,
        *,
        correlation: EventCorrelation = EventCorrelation(),
        **data: Any,
    ) -> None:
        self._emit_source(
            event_type,
            run_id=state.run_id,
            step=state.step,
            correlation=correlation,
            data=data,
        )

    def _emit_batch_event(
        self,
        event_type: EventType,
        *,
        run_id: str,
        batch_id: str,
        **data: Any,
    ) -> None:
        self._emit_source(
            event_type,
            run_id=run_id,
            step=0,
            correlation=EventCorrelation(batch_id=batch_id),
            data=data,
        )

    def _emit_external(
        self,
        event_type: EventType,
        run_id: str,
        step: int,
        *,
        correlation: EventCorrelation,
        **data: Any,
    ) -> None:
        self._emit_source(
            event_type,
            run_id=run_id,
            step=step,
            correlation=correlation,
            data=data,
        )

    def _save_checkpoint(
        self,
        state: RunState,
        lifecycle: CheckpointLifecycle,
        *,
        pending_action: CallTool | None = None,
        pending_capabilities: frozenset[str] = frozenset(),
        action_digest: str | None = None,
    ) -> None:
        if self.checkpoint_store is None:
            return
        checkpoint = Checkpoint(
            run_id=state.run_id,
            state=state,
            max_steps=self.max_steps,
            event_position=self._event_sequence + (1 if lifecycle is CheckpointLifecycle.ACTIVE else 0),
            resume_attempt=self.resume_attempt,
            lifecycle=lifecycle,
            pending_action=pending_action,
            pending_capabilities=pending_capabilities,
            action_digest=action_digest,
            duplicate_possible=self.duplicate_possible,
        )
        path = self.checkpoint_store.save(checkpoint, self.checkpoint_path)
        self.checkpoint_path = path
        if lifecycle is CheckpointLifecycle.ACTIVE:
            self._emit(
                EventType.CHECKPOINT_WRITTEN,
                state,
                checkpoint_path=str(path),
                lifecycle=lifecycle.value,
            )
