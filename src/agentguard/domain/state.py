"""Current decision-making state for one AgentGuard run."""

from dataclasses import dataclass, field
from enum import StrEnum

from .actions import Action
from .results import ToolResult


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StopReason(StrEnum):
    COMPLETED = "completed"
    INVALID_ACTION = "invalid_action"
    STEP_BUDGET_EXCEEDED = "step_budget_exceeded"
    TOOL_FAILED = "tool_failed"
    LOOP_DETECTED = "loop_detected"


@dataclass(frozen=True)
class HistoryEntry:
    """One recent action and its optional observed Tool result."""

    action: Action
    result: ToolResult | None = None


@dataclass
class RunState:
    """Bounded state needed by a Router to choose the next Action."""

    run_id: str
    step: int = 0
    status: RunStatus = RunStatus.RUNNING
    last_result: ToolResult | None = None
    recent_history: list[HistoryEntry] = field(default_factory=list)
    history_limit: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if self.step < 0:
            raise ValueError("step cannot be negative")
        if self.history_limit <= 0:
            raise ValueError("history_limit must be positive")
        if not isinstance(self.status, RunStatus):
            raise TypeError("status must be a RunStatus")
        if len(self.recent_history) > self.history_limit:
            self.recent_history = self.recent_history[-self.history_limit :]

    def record(self, action: Action, result: ToolResult | None = None) -> None:
        """Append one observation while preserving the bounded window."""

        self.recent_history.append(HistoryEntry(action=action, result=result))
        self.recent_history = self.recent_history[-self.history_limit :]
        if result is not None:
            self.last_result = result
