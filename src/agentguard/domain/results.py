"""Normalized Tool execution results."""

from dataclasses import dataclass
from enum import StrEnum


class ToolResultStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolResult:
    """Serializable result passed from the Runtime back to the Router."""

    tool_name: str
    status: ToolResultStatus
    value: object | None = None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")
        if not isinstance(self.status, ToolResultStatus):
            raise TypeError("status must be a ToolResultStatus")
        if self.status is ToolResultStatus.SUCCESS and (
            self.error_type is not None or self.error_message is not None
        ):
            raise ValueError("successful results cannot contain error fields")
        if self.status is ToolResultStatus.FAILED and (
            self.error_type is None and self.error_message is None
        ):
            raise ValueError("failed results must describe an error")
