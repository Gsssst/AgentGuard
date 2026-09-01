"""Typed checkpoint contracts for local Runtime recovery."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agentguard.domain.actions import Action, CallTool
from agentguard.domain.results import ToolResult
from agentguard.domain.state import RunState
from agentguard.runtime.permission import ApprovalDecision, normalize_capabilities


class CheckpointError(Exception):
    """Base class for checkpoint persistence and validation failures."""


class CheckpointCorruptError(CheckpointError):
    """Checkpoint bytes are not valid JSON."""


class CheckpointValidationError(CheckpointError):
    """Checkpoint JSON has an invalid shape or value."""


class UnsupportedCheckpointVersionError(CheckpointError):
    """Checkpoint schema version is not supported by this runtime."""


class CheckpointSerializationError(CheckpointError):
    """A domain value cannot be represented by the checkpoint JSON codec."""


class CheckpointLifecycle(StrEnum):
    ACTIVE = "active"
    RECOVERABLE = "recoverable"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Checkpoint:
    """Minimal state required to explicitly resume one logical run."""

    run_id: str
    state: RunState
    max_steps: int
    event_position: int = 0
    resume_attempt: int = 0
    lifecycle: CheckpointLifecycle = CheckpointLifecycle.ACTIVE
    pending_action: Action | None = None
    pending_result: ToolResult | None = None
    pending_capabilities: frozenset[str] = frozenset()
    action_digest: str | None = None
    approval_decision: ApprovalDecision | None = None
    duplicate_possible: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise CheckpointValidationError("run_id must be a non-empty string")
        if not isinstance(self.state, RunState):
            raise CheckpointValidationError("state must be a RunState")
        if self.state.run_id != self.run_id:
            raise CheckpointValidationError("state.run_id must match run_id")
        if not isinstance(self.max_steps, int) or isinstance(self.max_steps, bool) or self.max_steps <= 0:
            raise CheckpointValidationError("max_steps must be a positive integer")
        for name, value in (("event_position", self.event_position), ("resume_attempt", self.resume_attempt)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise CheckpointValidationError(f"{name} must be a non-negative integer")
        if not isinstance(self.lifecycle, CheckpointLifecycle):
            raise CheckpointValidationError("lifecycle must be a CheckpointLifecycle")
        if not isinstance(self.duplicate_possible, bool):
            raise CheckpointValidationError("duplicate_possible must be a boolean")
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            raise CheckpointValidationError("schema_version must be an integer")
        if self.schema_version != 1:
            raise UnsupportedCheckpointVersionError(self.schema_version)
        try:
            self.pending_capabilities = normalize_capabilities(self.pending_capabilities)
        except (TypeError, ValueError) as exc:
            raise CheckpointValidationError(f"invalid pending_capabilities: {exc}") from exc
        if self.action_digest is not None and (
            not isinstance(self.action_digest, str) or not self.action_digest.strip()
        ):
            raise CheckpointValidationError("action_digest must be a non-empty string when provided")
        if self.pending_action is None:
            if self.pending_capabilities or self.action_digest is not None:
                raise CheckpointValidationError(
                    "pending_capabilities and action_digest require pending_action"
                )
        if self.state.status.value == "waiting_approval":
            if not isinstance(self.pending_action, CallTool) or self.action_digest is None:
                raise CheckpointValidationError(
                    "waiting approval checkpoints require pending_action and action_digest"
                )
            if not self.pending_capabilities:
                raise CheckpointValidationError(
                    "waiting approval checkpoints require pending_capabilities"
                )
            if self.approval_decision is not None:
                raise CheckpointValidationError(
                    "waiting approval checkpoints cannot contain an approval decision"
                )
        if self.approval_decision is not None and self.pending_action is None:
            raise CheckpointValidationError("approval_decision requires pending_action")
