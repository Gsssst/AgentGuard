"""The deterministic, single-action-per-turn Runtime loop."""

from dataclasses import dataclass
from typing import Any

from agentguard.domain.actions import Action, CallTool, Finish
from agentguard.domain.runtime import RunResult
from agentguard.domain.results import ToolResultStatus
from agentguard.domain.state import RunState, RunStatus, StopReason
from agentguard.events.model import EventType, RuntimeEvent
from agentguard.events.sinks import EventSink, InMemoryEventSink

from .router import Router
from .tool import ToolExecutor


@dataclass
class Runtime:
    """Drive one Router and one ToolExecutor until a terminal outcome."""

    executor: ToolExecutor
    max_steps: int = 10
    event_sink: EventSink | None = None

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.event_sink is None:
            self.event_sink = InMemoryEventSink()

    async def run(self, router: Router, state: RunState | None = None) -> RunResult:
        """Run one state-driven, sequential Action loop."""

        state = state or RunState(run_id="run-001")
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

    def _finish(self, state: RunState, status: RunStatus, reason: StopReason) -> RunResult:
        state.status = status
        self._emit(
            EventType.RUN_FINISHED,
            state,
            status=status.value,
            stop_reason=reason.value,
        )
        return RunResult(
            run_id=state.run_id,
            status=status,
            stop_reason=reason,
            final_state=state,
        )

    def _emit(self, event_type: EventType, state: RunState, **data: Any) -> None:
        assert self.event_sink is not None
        self.event_sink.emit(
            RuntimeEvent(
                event_type=event_type,
                run_id=state.run_id,
                step=state.step,
                data=data,
            )
        )
