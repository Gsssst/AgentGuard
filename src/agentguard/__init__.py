"""AgentGuard public package."""

from .domain.actions import Action, CallTool, Finish
from .domain.results import FailureKind, ToolResult, ToolResultStatus
from .domain.runtime import RunPause, RunResult
from .domain.state import RunState, RunStatus, StopReason
from .runtime.engine import Runtime, SimulatedCrash
from .runtime.policy import RetryPolicy, RetrySafety
from .runtime.permission import (
    ApprovalDecision,
    Capability,
    KNOWN_CAPABILITIES,
    PermissionDecision,
    PermissionDecisionKind,
    PermissionDenied,
    PermissionPolicy,
    PermissionOutcome,
    action_digest,
    canonicalize,
    compute_action_digest,
    redact,
    redact_arguments,
)
from .runtime.resources import ResourceAccess, ResourceLockManager, ResourceLockTimeout
from .runtime.loop_guard import LoopGuard, action_signature
from .reporting import ReliabilityReport, build_report
from .events import EventType, InMemoryEventSink, JsonlEventSink, RuntimeEvent
from .checkpoint import (
    Checkpoint,
    CheckpointCorruptError,
    CheckpointError,
    CheckpointLifecycle,
    CheckpointSerializationError,
    CheckpointStore,
    CheckpointValidationError,
    UnsupportedCheckpointVersionError,
    decode_checkpoint,
    dumps_checkpoint,
    encode_checkpoint,
    loads_checkpoint,
)
from .evaluation import DEFAULT_SCENARIOS, ScenarioDefinition, ScenarioInstance, ScenarioRegistry, run_all, run_scenario

__all__ = [
    "Action",
    "CallTool",
    "Checkpoint",
    "CheckpointCorruptError",
    "CheckpointError",
    "CheckpointLifecycle",
    "CheckpointSerializationError",
    "CheckpointStore",
    "CheckpointValidationError",
    "decode_checkpoint",
    "dumps_checkpoint",
    "encode_checkpoint",
    "loads_checkpoint",
    "DEFAULT_SCENARIOS",
    "ScenarioDefinition",
    "ScenarioInstance",
    "ScenarioRegistry",
    "run_all",
    "run_scenario",
    "Finish",
    "FailureKind",
    "RunResult",
    "RunPause",
    "RunState",
    "RunStatus",
    "StopReason",
    "ToolResult",
    "ToolResultStatus",
    "UnsupportedCheckpointVersionError",
    "Runtime",
    "SimulatedCrash",
    "EventType",
    "InMemoryEventSink",
    "JsonlEventSink",
    "RuntimeEvent",
    "RetryPolicy",
    "RetrySafety",
    "Capability",
    "KNOWN_CAPABILITIES",
    "PermissionPolicy",
    "PermissionDecision",
    "PermissionDecisionKind",
    "PermissionOutcome",
    "PermissionDenied",
    "ApprovalDecision",
    "ResourceAccess",
    "ResourceLockManager",
    "ResourceLockTimeout",
    "action_digest",
    "canonicalize",
    "compute_action_digest",
    "redact",
    "redact_arguments",
    "LoopGuard",
    "action_signature",
    "ReliabilityReport",
    "build_report",
]
