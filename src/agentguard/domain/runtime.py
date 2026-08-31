"""Terminal result for a Runtime execution."""

from dataclasses import dataclass

from .state import RunState, RunStatus, StopReason


@dataclass(frozen=True)
class RunResult:
    """Final status, reason, and state returned by the Runtime."""

    run_id: str
    status: RunStatus
    stop_reason: StopReason
    final_state: RunState

    def __post_init__(self) -> None:
        if self.run_id != self.final_state.run_id:
            raise ValueError("run_id must match final_state.run_id")
        if self.status is RunStatus.RUNNING:
            raise ValueError("RunResult must be terminal")
        if self.status is RunStatus.COMPLETED and self.stop_reason is not StopReason.COMPLETED:
            raise ValueError("completed runs must use the completed stop reason")
        if self.status is RunStatus.FAILED and self.stop_reason is StopReason.COMPLETED:
            raise ValueError("failed runs cannot use the completed stop reason")
