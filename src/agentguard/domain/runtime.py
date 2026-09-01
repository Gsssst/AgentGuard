"""Terminal result for a Runtime execution."""

from dataclasses import dataclass

from .actions import CallTool
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
        if self.status in (RunStatus.RUNNING, RunStatus.WAITING_APPROVAL):
            raise ValueError("RunResult must be terminal")
        if self.status is RunStatus.COMPLETED and self.stop_reason is not StopReason.COMPLETED:
            raise ValueError("completed runs must use the completed stop reason")
        if self.status is RunStatus.FAILED and self.stop_reason is StopReason.COMPLETED:
            raise ValueError("failed runs cannot use the completed stop reason")


@dataclass(frozen=True)
class RunPause:
    """Non-terminal projection returned while approval is pending."""

    run_id: str
    status: RunStatus
    final_state: RunState
    pending_action: CallTool
    action_digest: str

    def __post_init__(self) -> None:
        if self.status is not RunStatus.WAITING_APPROVAL:
            raise ValueError("RunPause must use WAITING_APPROVAL status")
        if self.run_id != self.final_state.run_id:
            raise ValueError("run_id must match final_state.run_id")
        if not isinstance(self.pending_action, CallTool):
            raise TypeError("pending_action must be a CallTool")
        if not isinstance(self.action_digest, str) or not self.action_digest.strip():
            raise ValueError("action_digest must be a non-empty string")
