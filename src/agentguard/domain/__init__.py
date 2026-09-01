"""Typed domain objects for an AgentGuard run."""

from .actions import Action, CallTool, Finish
from .results import FailureKind, ToolResult, ToolResultStatus
from .runtime import RunResult
from .state import HistoryEntry, RunState, RunStatus, StopReason

__all__ = [
    "Action",
    "CallTool",
    "Finish",
    "FailureKind",
    "HistoryEntry",
    "RunResult",
    "RunState",
    "RunStatus",
    "StopReason",
    "ToolResult",
    "ToolResultStatus",
]
