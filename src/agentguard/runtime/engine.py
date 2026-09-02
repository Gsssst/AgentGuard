"""The deterministic Runtime loop and explicit independent batch execution."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Iterable
from typing import Callable
from typing import Any

from agentguard.domain.actions import Action, CallTool, Finish
from agentguard.domain.runtime import RunPause, RunResult
from agentguard.domain.results import FailureKind, ToolResult, ToolResultStatus
from agentguard.domain.state import RunState, RunStatus, StopReason
from agentguard.events.model import EventType, RuntimeEvent
from agentguard.events.sinks import EventSink, InMemoryEventSink
from agentguard.checkpoint import Checkpoint, CheckpointLifecycle, CheckpointStore

from .router import Router
from .loop_guard import LoopGuard
from .tool import ToolExecutor
from .permission import ApprovalDecision, PermissionDecisionKind, PermissionPolicy, action_digest, redact
from .resources import ResourceLockManager, ResourceLockTimeout


class SimulatedCrash(RuntimeError):
    """Deterministic fault injected at a named Runtime boundary."""


CrashHook = Callable[[str], None]


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

            self._emit(
                EventType.ACTION_PROPOSED,
                state,
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
                    self._emit(EventType.TOOL_STARTED, state, tool_name=action.tool_name)
                    tool_result = await self.executor.execute(
                        action,
                        on_event=lambda event_type, data: self._emit(event_type, state, **data),
                    )
            except ResourceLockTimeout as exc:
                self._emit(
                    EventType.RESOURCE_LOCK_TIMEOUT,
                    state,
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
                    tool_name=tool_result.tool_name,
                    value=tool_result.value,
                    attempts=tool_result.attempts,
                )
            elif tool_result.status is ToolResultStatus.TIMED_OUT:
                self._emit(
                    EventType.TOOL_TIMED_OUT,
                    state,
                    tool_name=tool_result.tool_name,
                    attempts=tool_result.attempts,
                    timeout_seconds=tool_result.timeout_seconds,
                    timeout_source=tool_result.timeout_source,
                )
            elif tool_result.status is ToolResultStatus.CANCELLED:
                self._emit(
                    EventType.TOOL_CANCELLED,
                    state,
                    tool_name=tool_result.tool_name,
                    attempts=tool_result.attempts,
                )
            else:
                self._emit(
                    EventType.TOOL_FAILED,
                    state,
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

    async def execute_batch(
        self,
        actions: Iterable[CallTool],
        *,
        batch_id: str = "batch",
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
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ValueError("batch_id must be a non-empty string")
        self._emit_batch_event(EventType.BATCH_STARTED, batch_id, size=len(batch))

        async def execute_one(action: CallTool) -> ToolResult:
            tool = self.executor.get_tool(action.tool_name)
            if self.permission_policy is not None:
                capabilities = tool.capabilities if tool is not None else frozenset()
                decision = self.permission_policy.decide(capabilities)
                if decision.kind is PermissionDecisionKind.DENY:
                    return ToolResult(
                        tool_name=action.tool_name,
                        status=ToolResultStatus.FAILED,
                        error_type="PermissionDenied",
                        error_message=str(decision.denial),
                        failure_kind=FailureKind.PERMANENT,
                        attempts=0,
                    )
                if decision.kind is PermissionDecisionKind.APPROVAL_REQUIRED:
                    return ToolResult(
                        tool_name=action.tool_name,
                        status=ToolResultStatus.FAILED,
                        error_type="ApprovalRequired",
                        error_message="batch Actions require approval and cannot pause a batch",
                        failure_kind=FailureKind.PERMANENT,
                        attempts=0,
                    )
            resources = tool.resources if tool is not None else {}
            try:
                assert self.lock_manager is not None
                async with self.lock_manager.hold(resources, timeout=self.lock_timeout):
                    return await self.executor.execute(action)
            except ResourceLockTimeout as exc:
                self._emit_batch_event(
                    EventType.RESOURCE_LOCK_TIMEOUT,
                    batch_id,
                    tool_name=action.tool_name,
                    resources=sorted(resources),
                    error_message=str(exc),
                )
                return ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.FAILED,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    failure_kind=FailureKind.RESOURCE_LOCK_TIMEOUT,
                    attempts=0,
                )

        results = tuple(await asyncio.gather(*(execute_one(action) for action in batch)))
        self._emit_batch_event(
            EventType.BATCH_FINISHED,
            batch_id,
            size=len(results),
            failed=sum(result.status is not ToolResultStatus.SUCCESS for result in results),
        )
        return results

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

    def _emit(self, event_type: EventType, state: RunState, **data: Any) -> None:
        assert self.event_sink is not None
        self._event_sequence += 1
        data.setdefault("sequence", self._event_sequence)
        data.setdefault("resume_attempt", self.resume_attempt)
        if self.duplicate_possible:
            data.setdefault("duplicate_possible", True)
        self.event_sink.emit(
            RuntimeEvent(
                event_type=event_type,
                run_id=state.run_id,
                step=state.step,
                data=data,
            )
        )

    def _emit_batch_event(self, event_type: EventType, batch_id: str, **data: Any) -> None:
        assert self.event_sink is not None
        self._event_sequence += 1
        data.setdefault("sequence", self._event_sequence)
        self.event_sink.emit(
            RuntimeEvent(
                event_type=event_type,
                run_id=batch_id,
                step=0,
                data=data,
            )
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
