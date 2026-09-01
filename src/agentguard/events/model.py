"""Structured facts emitted during one Runtime execution."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    RUN_STARTED = "run_started"
    ACTION_PROPOSED = "action_proposed"
    TOOL_STARTED = "tool_started"
    TOOL_ATTEMPT_STARTED = "tool_attempt_started"
    RETRY_SCHEDULED = "retry_scheduled"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    TOOL_TIMED_OUT = "tool_timed_out"
    TOOL_CANCELLED = "tool_cancelled"
    LOOP_DETECTED = "loop_detected"
    CHECKPOINT_WRITTEN = "checkpoint_written"
    RESUME_STARTED = "resume_started"
    DUPLICATE_POSSIBLE = "duplicate_possible"
    RECOVERY_REJECTED = "recovery_rejected"
    PERMISSION_DENIED = "permission_denied"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    RUN_FINISHED = "run_finished"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RuntimeEvent:
    """One JSON-serializable fact from an AgentGuard run."""

    event_type: EventType
    run_id: str
    step: int
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, EventType):
            raise TypeError("event_type must be an EventType")
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if self.step < 0:
            raise ValueError("step cannot be negative")
        if not isinstance(self.data, dict):
            raise TypeError("data must be a dictionary")
        object.__setattr__(self, "data", dict(self.data))

    def to_dict(self) -> dict[str, Any]:
        """Return the stable external representation used by JSONL."""

        return {
            "event_type": self.event_type.value,
            "run_id": self.run_id,
            "step": self.step,
            "timestamp": self.timestamp,
            "data": self.data,
        }
