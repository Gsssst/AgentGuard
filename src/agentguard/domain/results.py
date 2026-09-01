"""Normalized Tool execution results."""

from dataclasses import dataclass
from enum import StrEnum


class ToolResultStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class FailureKind(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ToolResult:
    """Serializable result passed from the Runtime back to the Router."""

    tool_name: str
    status: ToolResultStatus
    value: object | None = None
    error_type: str | None = None
    error_message: str | None = None
    failure_kind: FailureKind | None = None
    timeout_seconds: float | None = None
    timeout_source: str | None = None
    attempts: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")
        if not isinstance(self.status, ToolResultStatus):
            raise TypeError("status must be a ToolResultStatus")
        if self.status is ToolResultStatus.SUCCESS:
            if (
                self.error_type is not None
                or self.error_message is not None
                or self.failure_kind is not None
                or self.timeout_seconds is not None
                or self.timeout_source is not None
            ):
                raise ValueError("successful results cannot contain error fields")
        elif self.error_type is None and self.error_message is None:
            raise ValueError("failed, timed-out, and cancelled results must describe an error")
        if self.status is ToolResultStatus.TIMED_OUT and self.failure_kind not in (None, FailureKind.TIMEOUT):
            raise ValueError("timed-out results must use the timeout failure kind")
        if self.status is ToolResultStatus.CANCELLED and self.failure_kind not in (None, FailureKind.CANCELLED):
            raise ValueError("cancelled results must use the cancelled failure kind")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.timeout_source is not None and self.timeout_seconds is None:
            raise ValueError("timeout_source requires timeout_seconds")
        if self.attempts < 0:
            raise ValueError("attempts cannot be negative")
