"""AgentGuard public package."""

from .domain.actions import Action, CallTool, Finish
from .domain.results import FailureKind, ToolResult, ToolResultStatus
from .domain.runtime import RunResult
from .domain.state import RunState, RunStatus, StopReason
from .runtime.engine import Runtime
from .runtime.policy import RetryPolicy, RetrySafety
from .runtime.loop_guard import LoopGuard, action_signature
from .reporting import ReliabilityReport, build_report
from .events import EventType, InMemoryEventSink, JsonlEventSink, RuntimeEvent

__all__ = [
    "Action",
    "CallTool",
    "Finish",
    "FailureKind",
    "RunResult",
    "RunState",
    "RunStatus",
    "StopReason",
    "ToolResult",
    "ToolResultStatus",
    "Runtime",
    "EventType",
    "InMemoryEventSink",
    "JsonlEventSink",
    "RuntimeEvent",
    "RetryPolicy",
    "RetrySafety",
    "LoopGuard",
    "action_signature",
    "ReliabilityReport",
    "build_report",
]
