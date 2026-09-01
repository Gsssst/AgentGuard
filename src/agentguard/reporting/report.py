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
    )
