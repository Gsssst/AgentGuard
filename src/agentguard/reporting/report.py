"""Build reliability summaries from terminal results and event evidence."""

from dataclasses import dataclass
from typing import Any, Iterable

from agentguard.domain.runtime import RunResult
from agentguard.events.model import EventType, RuntimeEvent


@dataclass(frozen=True)
class ReliabilityReport:
    run_id: str
    status: str
    stop_reason: str
    steps: int
    tool_calls: int
    failed_tool_calls: int
    retry_count: int
    loop_detected: bool
    events: tuple[dict[str, Any], ...]
    evidence_consistent: bool
    checkpoint_writes: int = 0
    checkpoint_successes: int = 0
    recovery_attempts: int = 0
    recovery_success: bool = False
    duplicate_possible_tool_executions: int = 0
    crash_to_recovery_steps: int | None = None
    final_state_correct: bool | None = None
    permission_denials: int = 0
    approval_requests: int = 0
    approval_grants: int = 0
    approval_denials: int = 0
    waiting_runs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "failed_tool_calls": self.failed_tool_calls,
            "retry_count": self.retry_count,
            "loop_detected": self.loop_detected,
            "events": list(self.events),
            "evidence_consistent": self.evidence_consistent,
            "checkpoint_writes": self.checkpoint_writes,
            "checkpoint_successes": self.checkpoint_successes,
            "recovery_attempts": self.recovery_attempts,
            "recovery_success": self.recovery_success,
            "duplicate_possible_tool_executions": self.duplicate_possible_tool_executions,
            "crash_to_recovery_steps": self.crash_to_recovery_steps,
            "final_state_correct": self.final_state_correct,
            "permission_denials": self.permission_denials,
            "approval_requests": self.approval_requests,
            "approval_grants": self.approval_grants,
            "approval_denials": self.approval_denials,
            "waiting_runs": self.waiting_runs,
        }


def build_report(result: RunResult, events: Iterable[RuntimeEvent]) -> ReliabilityReport:
    """Project a terminal result and event stream into one report."""

    event_list = tuple(events)
    event_dicts = tuple(event.to_dict() for event in event_list)
    finished = [event for event in event_list if event.event_type is EventType.RUN_FINISHED]
    finished_data = finished[-1].data if finished else None

    evidence_consistent = bool(finished_data)
    if finished_data:
        evidence_consistent = evidence_consistent and (
            finished[-1].run_id == result.run_id
            and finished_data.get("status") == result.status.value
            and finished_data.get("stop_reason") == result.stop_reason.value
        )

    tool_calls = sum(event.event_type is EventType.TOOL_STARTED for event in event_list)
    failed_tool_calls = sum(
        event.event_type in (EventType.TOOL_FAILED, EventType.TOOL_TIMED_OUT, EventType.TOOL_CANCELLED)
        for event in event_list
    )
    retry_count = sum(event.event_type is EventType.RETRY_SCHEDULED for event in event_list)
    loop_detected = any(event.event_type is EventType.LOOP_DETECTED for event in event_list)
    checkpoint_writes = sum(event.event_type is EventType.CHECKPOINT_WRITTEN for event in event_list)
    recovery_attempts = max(
        (int(event.data.get("resume_attempt", 0)) for event in event_list if event.event_type is EventType.RESUME_STARTED),
        default=0,
    )
    recovery_success = recovery_attempts > 0 and result.status.value == "completed" and evidence_consistent
    duplicate_possible_tool_executions = sum(
        event.event_type is EventType.TOOL_STARTED and event.data.get("duplicate_possible") is True
        for event in event_list
    )
    resume_event = next((event for event in event_list if event.event_type is EventType.RESUME_STARTED), None)
    crash_to_recovery_steps = resume_event.step if resume_event is not None else None
    permission_denials = sum(event.event_type is EventType.PERMISSION_DENIED for event in event_list)
    approval_requests = sum(event.event_type is EventType.APPROVAL_REQUESTED for event in event_list)
    approval_grants = sum(event.event_type is EventType.APPROVAL_GRANTED for event in event_list)
    approval_denials = sum(event.event_type is EventType.APPROVAL_DENIED for event in event_list)
    waiting_runs = sum(
        event.event_type is EventType.APPROVAL_REQUESTED
        and event.data.get("status") == "waiting_approval"
        for event in event_list
    )

    return ReliabilityReport(
        run_id=result.run_id,
        status=result.status.value,
        stop_reason=result.stop_reason.value,
        steps=result.final_state.step,
        tool_calls=tool_calls,
        failed_tool_calls=failed_tool_calls,
        retry_count=retry_count,
        loop_detected=loop_detected,
        events=event_dicts,
        evidence_consistent=evidence_consistent,
        checkpoint_writes=checkpoint_writes,
        checkpoint_successes=checkpoint_writes,
        recovery_attempts=recovery_attempts,
        recovery_success=recovery_success,
        duplicate_possible_tool_executions=duplicate_possible_tool_executions,
        crash_to_recovery_steps=crash_to_recovery_steps,
        permission_denials=permission_denials,
        approval_requests=approval_requests,
        approval_grants=approval_grants,
        approval_denials=approval_denials,
        waiting_runs=waiting_runs,
    )
