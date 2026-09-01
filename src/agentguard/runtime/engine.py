"""The deterministic, single-action-per-turn Runtime loop."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from typing import Any

from agentguard.domain.actions import Action, CallTool, Finish
from agentguard.domain.runtime import RunResult
from agentguard.domain.results import ToolResultStatus
from agentguard.domain.state import RunState, RunStatus, StopReason
from agentguard.events.model import EventType, RuntimeEvent
from agentguard.events.sinks import EventSink, InMemoryEventSink
from agentguard.checkpoint import Checkpoint, CheckpointLifecycle, CheckpointStore

from .router import Router
from .loop_guard import LoopGuard
from .tool import ToolExecutor


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

    async def run(self, router: Router, state: RunState | None = None) -> RunResult:
        """Run one state-driven, sequential Action loop."""

        state = state or RunState(run_id="run-001")
        if self.resume_attempt == 0:
            self._event_sequence = 0
        self._emit(EventType.RUN_STARTED, state)

        while state.status is RunStatus.RUNNING:
            if state.step >= self.max_steps:
                return self._finish(state, RunStatus.FAILED, StopReason.STEP_BUDGET_EXCEEDED)

            try:
                action: Any = await router.next_action(state)
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
                    {"tool_name": action.tool_name, "arguments": action.arguments}
                    if isinstance(action, CallTool)
                    else {"reason": action.reason}
                ),
            )

            if isinstance(action, Finish):
                state.record(action)
                state.step += 1
                return self._finish(state, RunStatus.COMPLETED, StopReason.COMPLETED)

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

            self._emit(EventType.TOOL_STARTED, state, tool_name=action.tool_name)
            tool_result = await self.executor.execute(
                action,
                on_event=lambda event_type, data: self._emit(event_type, state, **data),
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

    async def resume(self, checkpoint_path: str | Path, router: Router) -> RunResult:
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
        self._emit(
            EventType.RESUME_STARTED,
            checkpoint.state,
            resume_attempt=self.resume_attempt,
            duplicate_possible=True,
            checkpoint_path=str(path),
        )
        return await self.run(router, checkpoint.state)

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

    def _save_checkpoint(self, state: RunState, lifecycle: CheckpointLifecycle) -> None:
        if self.checkpoint_store is None:
            return
        checkpoint = Checkpoint(
            run_id=state.run_id,
            state=state,
            max_steps=self.max_steps,
            event_position=self._event_sequence + (1 if lifecycle is CheckpointLifecycle.ACTIVE else 0),
            resume_attempt=self.resume_attempt,
            lifecycle=lifecycle,
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
