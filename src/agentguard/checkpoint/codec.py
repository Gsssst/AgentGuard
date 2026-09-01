"""Explicit JSON encoding and strict decoding for checkpoints."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from agentguard.domain.actions import Action, CallTool, Finish
from agentguard.domain.results import FailureKind, ToolResult, ToolResultStatus
from agentguard.domain.state import HistoryEntry, RunState, RunStatus
from agentguard.runtime.permission import ApprovalDecision, normalize_capabilities

from .model import (
    Checkpoint,
    CheckpointCorruptError,
    CheckpointSerializationError,
    CheckpointValidationError,
    CheckpointLifecycle,
    UnsupportedCheckpointVersionError,
)

SUPPORTED_SCHEMA_VERSION = 1
_MISSING = object()


def _json_value(value: Any, *, field: str) -> Any:
    """Validate and return a JSON-compatible value without coercion."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_value(item, field=field) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CheckpointSerializationError(f"{field} mapping keys must be strings")
            result[key] = _json_value(item, field=field)
        return result
    raise CheckpointSerializationError(f"{field} contains a non-JSON-compatible value")


def _encode_action(action: Action | None) -> dict[str, Any] | None:
    if action is None:
        return None
    if isinstance(action, CallTool):
        return {
            "action_type": "call_tool",
            "tool_name": action.tool_name,
            "arguments": _json_value(action.arguments, field="action.arguments"),
        }
    if isinstance(action, Finish):
        return {"action_type": "finish", "reason": action.reason}
    raise CheckpointSerializationError(f"unsupported action type: {type(action).__name__}")


def _decode_action(raw: Any, *, field: str) -> Action | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise CheckpointValidationError(f"{field} must be an object or null")
    action_type = raw.get("action_type", _MISSING)
    if action_type == "call_tool":
        _require(raw, "tool_name", field)
        _require(raw, "arguments", field)
        if not isinstance(raw["arguments"], dict):
            raise CheckpointValidationError(f"{field}.arguments must be an object")
        return CallTool(raw["tool_name"], dict(raw["arguments"]))
    if action_type == "finish":
        _require(raw, "reason", field)
        return Finish(raw["reason"])
    raise CheckpointValidationError(f"{field}.action_type is unsupported")


def _encode_result(result: ToolResult | None, *, field: str = "tool_result") -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "tool_name": result.tool_name,
        "status": result.status.value,
        "value": _json_value(result.value, field=f"{field}.value"),
        "error_type": result.error_type,
        "error_message": result.error_message,
        "failure_kind": result.failure_kind.value if result.failure_kind is not None else None,
        "timeout_seconds": result.timeout_seconds,
        "timeout_source": result.timeout_source,
        "attempts": result.attempts,
    }


def _decode_result(raw: Any, *, field: str = "tool_result") -> ToolResult | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise CheckpointValidationError(f"{field} must be an object or null")
    for key in ("tool_name", "status", "value", "error_type", "error_message", "failure_kind", "timeout_seconds", "timeout_source", "attempts"):
        _require(raw, key, field)
    try:
        status = ToolResultStatus(raw["status"])
    except (TypeError, ValueError) as exc:
        raise CheckpointValidationError(f"{field}.status is unsupported") from exc
    failure_kind = raw["failure_kind"]
    if failure_kind is not None:
        try:
            failure_kind = FailureKind(failure_kind)
        except (TypeError, ValueError) as exc:
            raise CheckpointValidationError(f"{field}.failure_kind is unsupported") from exc
    try:
        return ToolResult(
            tool_name=raw["tool_name"],
            status=status,
            value=raw["value"],
            error_type=raw["error_type"],
            error_message=raw["error_message"],
            failure_kind=failure_kind,
            timeout_seconds=raw["timeout_seconds"],
            timeout_source=raw["timeout_source"],
            attempts=raw["attempts"],
        )
    except (TypeError, ValueError) as exc:
        raise CheckpointValidationError(f"invalid {field}: {exc}") from exc


def _encode_state(state: RunState) -> dict[str, Any]:
    return {
        "run_id": state.run_id,
        "step": state.step,
        "status": state.status.value,
        "history_limit": state.history_limit,
        "last_result": _encode_result(state.last_result, field="state.last_result"),
        "recent_history": [
            {
                "action": _encode_action(entry.action),
                "result": _encode_result(entry.result, field="state.recent_history.result"),
            }
            for entry in state.recent_history
        ],
    }


def _decode_state(raw: Any) -> RunState:
    if not isinstance(raw, dict):
        raise CheckpointValidationError("state must be an object")
    for key in ("run_id", "step", "status", "history_limit", "last_result", "recent_history"):
        _require(raw, key, "state")
    try:
        status = RunStatus(raw["status"])
    except (TypeError, ValueError) as exc:
        raise CheckpointValidationError("state.status is unsupported") from exc
    history = raw["recent_history"]
    if not isinstance(history, list):
        raise CheckpointValidationError("state.recent_history must be an array")
    entries: list[HistoryEntry] = []
    for index, item in enumerate(history):
        if not isinstance(item, dict):
            raise CheckpointValidationError(f"state.recent_history[{index}] must be an object")
        _require(item, "action", f"state.recent_history[{index}]")
        _require(item, "result", f"state.recent_history[{index}]")
        action = _decode_action(item["action"], field=f"state.recent_history[{index}].action")
        if action is None:
            raise CheckpointValidationError("history action cannot be null")
        entries.append(
            HistoryEntry(
                action=action,
                result=_decode_result(item["result"], field=f"state.recent_history[{index}].result"),
            )
        )
    try:
        return RunState(
            run_id=raw["run_id"],
            step=raw["step"],
            status=status,
            last_result=_decode_result(raw["last_result"], field="state.last_result"),
            recent_history=entries,
            history_limit=raw["history_limit"],
        )
    except (TypeError, ValueError) as exc:
        raise CheckpointValidationError(f"invalid state: {exc}") from exc


def _require(raw: dict[str, Any], key: str, field: str) -> None:
    if key not in raw:
        raise CheckpointValidationError(f"{field}.{key} is required")


def encode_checkpoint(checkpoint: Checkpoint) -> dict[str, Any]:
    """Project a Checkpoint into explicit JSON-compatible primitives."""

    if checkpoint.schema_version != SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedCheckpointVersionError(checkpoint.schema_version)
    return {
        "schema_version": checkpoint.schema_version,
        "lifecycle": checkpoint.lifecycle.value,
        "run_id": checkpoint.run_id,
        "state": _encode_state(checkpoint.state),
        "runtime": {"max_steps": checkpoint.max_steps},
        "event_position": checkpoint.event_position,
        "resume_attempt": checkpoint.resume_attempt,
        "pending_action": _encode_action(checkpoint.pending_action),
        "pending_result": _encode_result(checkpoint.pending_result, field="pending_result"),
        "pending_capabilities": sorted(checkpoint.pending_capabilities),
        "action_digest": checkpoint.action_digest,
        "approval_decision": _encode_approval_decision(checkpoint.approval_decision),
        "duplicate_possible": checkpoint.duplicate_possible,
    }


def _encode_approval_decision(decision: ApprovalDecision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "approved": decision.approved,
        "actor": decision.actor,
        "reason": decision.reason,
        "action_digest": decision.action_digest,
    }


def _decode_approval_decision(raw: Any, *, field: str) -> ApprovalDecision | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise CheckpointValidationError(f"{field} must be an object or null")
    for key in ("approved", "actor", "reason", "action_digest"):
        _require(raw, key, field)
    try:
        return ApprovalDecision(
            approved=raw["approved"],
            actor=raw["actor"],
            reason=raw["reason"],
            action_digest=raw["action_digest"],
        )
    except (TypeError, ValueError) as exc:
        raise CheckpointValidationError(f"invalid {field}: {exc}") from exc


def decode_checkpoint(raw: Any) -> Checkpoint:
    """Strictly validate raw JSON data before constructing domain objects."""

    if not isinstance(raw, dict):
        raise CheckpointValidationError("checkpoint must be an object")
    for key in (
        "schema_version", "lifecycle", "run_id", "state", "runtime",
        "event_position", "resume_attempt", "pending_action", "pending_result", "duplicate_possible",
    ):
        _require(raw, key, "checkpoint")
    version = raw["schema_version"]
    if version != SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedCheckpointVersionError(version)
    try:
        lifecycle = CheckpointLifecycle(raw["lifecycle"])
    except (TypeError, ValueError) as exc:
        raise CheckpointValidationError("checkpoint.lifecycle is unsupported") from exc
    runtime = raw["runtime"]
    if not isinstance(runtime, dict):
        raise CheckpointValidationError("checkpoint.runtime must be an object")
    _require(runtime, "max_steps", "checkpoint.runtime")
    state = _decode_state(raw["state"])
    try:
        return Checkpoint(
            run_id=raw["run_id"],
            state=state,
            max_steps=runtime["max_steps"],
            event_position=raw["event_position"],
            resume_attempt=raw["resume_attempt"],
            lifecycle=lifecycle,
            pending_action=_decode_action(raw["pending_action"], field="checkpoint.pending_action"),
            pending_result=_decode_result(raw["pending_result"], field="checkpoint.pending_result"),
            pending_capabilities=raw.get("pending_capabilities", []),
            action_digest=raw.get("action_digest"),
            approval_decision=_decode_approval_decision(
                raw.get("approval_decision"), field="checkpoint.approval_decision"
            ),
            duplicate_possible=raw["duplicate_possible"],
            schema_version=version,
        )
    except UnsupportedCheckpointVersionError:
        raise
    except (TypeError, ValueError, CheckpointValidationError) as exc:
        if isinstance(exc, CheckpointValidationError):
            raise
        raise CheckpointValidationError(f"invalid checkpoint: {exc}") from exc


def dumps_checkpoint(checkpoint: Checkpoint) -> str:
    try:
        return json.dumps(encode_checkpoint(checkpoint), ensure_ascii=False, sort_keys=True) + "\n"
    except (TypeError, ValueError) as exc:
        raise CheckpointSerializationError(str(exc)) from exc


def loads_checkpoint(text: str) -> Checkpoint:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CheckpointCorruptError(str(exc)) from exc
    return decode_checkpoint(raw)
