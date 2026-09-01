"""AgentGuard public package."""

from .domain.actions import Action, CallTool, Finish
from .domain.results import FailureKind, ToolResult, ToolResultStatus
from .domain.runtime import RunResult
from .domain.state import RunState, RunStatus, StopReason
from .runtime.engine import Runtime, SimulatedCrash
from .runtime.policy import RetryPolicy, RetrySafety
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
    "LoopGuard",
    "action_signature",
    "ReliabilityReport",
    "build_report",
]
