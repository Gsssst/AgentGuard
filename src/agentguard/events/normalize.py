"""Explicit projection from legacy Runtime events to safe v1 facts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agentguard._safety import safe_preview

from .contract import (
    EVENT_STATUS_BY_TYPE,
    EventCorrelation,
    EventStatus,
    EventValidationCategory,
    EventValidationError,
    NormalizedEvent,
)
from .model import EventType, RuntimeEvent


_CORRELATION_FIELDS = frozenset({"call_id", "tool_call_id", "batch_id"})
_COMMON_FIELDS = frozenset({"sequence", "resume_attempt", "duplicate_possible"})


@dataclass(frozen=True, slots=True)
class _SourceSpec:
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    discarded: frozenset[str] = frozenset()

    @property
    def allowed(self) -> frozenset[str]:
        return self.required | self.optional | self.discarded | _CORRELATION_FIELDS | _COMMON_FIELDS


SOURCE_SPECS: Mapping[EventType, _SourceSpec] = {
    EventType.RUN_STARTED: _SourceSpec(frozenset()),
    EventType.ACTION_PROPOSED: _SourceSpec(
        frozenset({"action_type"}),
        frozenset({"tool_name", "arguments"}),
        frozenset({"reason"}),
    ),
    EventType.TOOL_STARTED: _SourceSpec(frozenset({"tool_name"})),
    EventType.TOOL_ATTEMPT_STARTED: _SourceSpec(
        frozenset({"tool_name", "attempt", "max_attempts", "retry_safety"}),
        frozenset({"timeout_seconds", "timeout_source"}),
    ),
    EventType.RETRY_SCHEDULED: _SourceSpec(
        frozenset({"tool_name", "completed_attempt", "next_attempt", "max_attempts", "delay_seconds"}),
        frozenset({"failure_kind"}),
    ),
    EventType.TOOL_SUCCEEDED: _SourceSpec(frozenset({"tool_name", "attempts", "value"})),
    EventType.TOOL_FAILED: _SourceSpec(
        frozenset({"tool_name", "error_type", "failure_kind", "attempts"}),
        discarded=frozenset({"error_message", "stack", "traceback"}),
    ),
    EventType.TOOL_TIMED_OUT: _SourceSpec(
        frozenset({"tool_name", "attempts", "timeout_seconds", "timeout_source"}),
        discarded=frozenset({"error_message", "stack", "traceback"}),
    ),
    EventType.TOOL_CANCELLED: _SourceSpec(
        frozenset({"tool_name", "attempts"}),
        discarded=frozenset({"error_message", "stack", "traceback"}),
    ),
    EventType.LOOP_DETECTED: _SourceSpec(
        frozenset({"consecutive_count", "threshold"}),
        discarded=frozenset({"signature"}),
    ),
    EventType.CHECKPOINT_WRITTEN: _SourceSpec(
        frozenset({"lifecycle"}), discarded=frozenset({"checkpoint_path"})
    ),
    EventType.RESUME_STARTED: _SourceSpec(
        frozenset({"resume_attempt", "duplicate_possible"}),
        discarded=frozenset({"checkpoint_path"}),
    ),
    EventType.DUPLICATE_POSSIBLE: _SourceSpec(frozenset({"resume_attempt"})),
    EventType.RECOVERY_REJECTED: _SourceSpec(
        frozenset({"error_type"}), discarded=frozenset({"error_message", "checkpoint_path", "stack"})
    ),
    EventType.PERMISSION_DENIED: _SourceSpec(
        frozenset({"tool_name", "required_capabilities", "forbidden_capabilities", "decision"}),
        discarded=frozenset({"reason", "error_message"}),
    ),
    EventType.APPROVAL_REQUESTED: _SourceSpec(
        frozenset({"tool_name", "required_capabilities", "decision", "action_digest", "arguments"}),
        discarded=frozenset({"status", "reason"}),
    ),
    EventType.APPROVAL_GRANTED: _SourceSpec(
        frozenset({"tool_name", "required_capabilities", "actor", "action_digest"}),
        discarded=frozenset({"reason"}),
    ),
    EventType.APPROVAL_DENIED: _SourceSpec(
        frozenset({"tool_name", "required_capabilities", "actor", "action_digest"}),
        discarded=frozenset({"reason"}),
    ),
    EventType.RESOURCE_WAITING: _SourceSpec(frozenset({"tool_name", "resources"})),
    EventType.RESOURCE_LOCK_TIMEOUT: _SourceSpec(
        frozenset({"tool_name", "resources"}),
        frozenset({"failure_kind"}),
        frozenset({"error_message", "stack", "traceback"}),
    ),
    EventType.BATCH_STARTED: _SourceSpec(frozenset({"size"})),
    EventType.BATCH_FINISHED: _SourceSpec(frozenset({"size", "failed"})),
    EventType.RUN_FINISHED: _SourceSpec(frozenset({"status", "stop_reason"})),
}


_SAFE_SUMMARIES: Mapping[EventType, str] = {
    EventType.TOOL_FAILED: "tool execution failed",
    EventType.TOOL_TIMED_OUT: "tool execution timed out",
    EventType.TOOL_CANCELLED: "tool execution was cancelled",
    EventType.DUPLICATE_POSSIBLE: "tool execution may have been duplicated",
    EventType.RECOVERY_REJECTED: "checkpoint recovery was rejected",
    EventType.PERMISSION_DENIED: "tool permission was denied",
    EventType.APPROVAL_GRANTED: "tool approval was granted",
    EventType.APPROVAL_DENIED: "tool approval was denied",
    EventType.RESOURCE_LOCK_TIMEOUT: "resource lock acquisition timed out",
}


def _error(category: EventValidationCategory, field: str) -> EventValidationError:
    return EventValidationError(category, field=field)


def _check_source_shape(event_type: EventType, data: Mapping[str, Any]) -> None:
    spec = SOURCE_SPECS[event_type]
    missing = spec.required - set(data)
    if missing:
        raise _error(EventValidationCategory.MISSING_FIELD, "data")
    unknown = set(data) - spec.allowed
    if unknown:
        raise _error(EventValidationCategory.UNSUPPORTED_FIELD, "data")


def _copy_fields(data: Mapping[str, Any], *fields: str) -> dict[str, Any]:
    return {field: data[field] for field in fields if field in data and data[field] is not None}


def _bounded_label(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise _error(EventValidationCategory.INVALID_TYPE, field)
    if not value or value != value.strip() or any(ord(char) < 32 for char in value):
        raise _error(EventValidationCategory.INVALID_VALUE, field)
    return value[:512]


def _bounded_labels(value: Any, *, field: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _error(EventValidationCategory.INVALID_TYPE, field)
    return [_bounded_label(item, field=field) for item in value[:20]]


def _common_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if "resume_attempt" in data:
        payload["resume_attempt"] = data["resume_attempt"]
    if "duplicate_possible" in data:
        payload["duplicate_possible"] = data["duplicate_possible"]
    return payload


def _project_payload(event_type: EventType, data: Mapping[str, Any]) -> dict[str, Any]:
    payload = _common_payload(data)

    if event_type is EventType.RUN_STARTED:
        return payload
    if event_type is EventType.ACTION_PROPOSED:
        payload["action_type"] = data["action_type"]
        if data["action_type"] == "CallTool":
            if "tool_name" not in data or "arguments" not in data:
                raise _error(EventValidationCategory.MISSING_FIELD, "data")
            payload["tool_name"] = data["tool_name"]
            payload["arguments"] = safe_preview(data["arguments"]).to_dict()
        elif data["action_type"] == "Finish":
            if "reason" in data:
                payload["reason_present"] = True
        return payload
    if event_type is EventType.TOOL_STARTED:
        payload.update(_copy_fields(data, "tool_name"))
    elif event_type is EventType.TOOL_ATTEMPT_STARTED:
        payload.update(
            _copy_fields(
                data,
                "tool_name",
                "attempt",
                "max_attempts",
                "retry_safety",
                "timeout_seconds",
                "timeout_source",
            )
        )
    elif event_type is EventType.RETRY_SCHEDULED:
        payload.update(
            _copy_fields(
                data,
                "tool_name",
                "completed_attempt",
                "next_attempt",
                "max_attempts",
                "delay_seconds",
                "failure_kind",
            )
        )
    elif event_type is EventType.TOOL_SUCCEEDED:
        payload.update(_copy_fields(data, "tool_name", "attempts"))
        payload["result"] = safe_preview(data["value"]).to_dict()
    elif event_type is EventType.TOOL_FAILED:
        payload.update(_copy_fields(data, "tool_name", "error_type", "failure_kind", "attempts"))
        payload["safe_summary"] = _SAFE_SUMMARIES[event_type]
    elif event_type is EventType.TOOL_TIMED_OUT:
        payload.update(_copy_fields(data, "tool_name", "attempts", "timeout_seconds", "timeout_source"))
        payload["safe_summary"] = _SAFE_SUMMARIES[event_type]
    elif event_type is EventType.TOOL_CANCELLED:
        payload.update(_copy_fields(data, "tool_name", "attempts"))
        payload["safe_summary"] = _SAFE_SUMMARIES[event_type]
    elif event_type is EventType.LOOP_DETECTED:
        payload.update(_copy_fields(data, "consecutive_count", "threshold"))
    elif event_type is EventType.CHECKPOINT_WRITTEN:
        payload.update(_copy_fields(data, "lifecycle"))
    elif event_type is EventType.RESUME_STARTED:
        pass
    elif event_type is EventType.DUPLICATE_POSSIBLE:
        payload["safe_summary"] = _SAFE_SUMMARIES[event_type]
    elif event_type is EventType.RECOVERY_REJECTED:
        payload.update(_copy_fields(data, "error_type"))
        payload["safe_summary"] = _SAFE_SUMMARIES[event_type]
    elif event_type is EventType.PERMISSION_DENIED:
        payload.update(_copy_fields(data, "tool_name", "decision"))
        payload["required_capabilities"] = _bounded_labels(
            data["required_capabilities"], field="data.required_capabilities"
        )
        payload["forbidden_capabilities"] = _bounded_labels(
            data["forbidden_capabilities"], field="data.forbidden_capabilities"
        )
        payload["safe_summary"] = _SAFE_SUMMARIES[event_type]
    elif event_type is EventType.APPROVAL_REQUESTED:
        payload.update(_copy_fields(data, "tool_name", "decision", "action_digest"))
        payload["required_capabilities"] = _bounded_labels(
            data["required_capabilities"], field="data.required_capabilities"
        )
        payload["arguments"] = safe_preview(data["arguments"]).to_dict()
    elif event_type in {EventType.APPROVAL_GRANTED, EventType.APPROVAL_DENIED}:
        payload.update(_copy_fields(data, "tool_name", "action_digest"))
        payload["required_capabilities"] = _bounded_labels(
            data["required_capabilities"], field="data.required_capabilities"
        )
        payload["actor"] = _bounded_label(data["actor"], field="data.actor")
        payload["safe_summary"] = _SAFE_SUMMARIES[event_type]
    elif event_type is EventType.RESOURCE_WAITING:
        payload.update(_copy_fields(data, "tool_name"))
        payload["resources"] = _bounded_labels(data["resources"], field="data.resources")
    elif event_type is EventType.RESOURCE_LOCK_TIMEOUT:
        payload.update(_copy_fields(data, "tool_name"))
        payload["resources"] = _bounded_labels(data["resources"], field="data.resources")
        payload["failure_kind"] = data.get("failure_kind") or "resource_lock_timeout"
        payload["safe_summary"] = _SAFE_SUMMARIES[event_type]
    elif event_type in {EventType.BATCH_STARTED, EventType.BATCH_FINISHED}:
        payload.update(_copy_fields(data, "size", "failed"))
    elif event_type is EventType.RUN_FINISHED:
        payload.update(_copy_fields(data, "status", "stop_reason"))
    else:
        raise _error(EventValidationCategory.UNSUPPORTED_EVENT, "event_type")
    return payload


def _event_status(event_type: EventType, payload: Mapping[str, Any]) -> EventStatus:
    if event_type is EventType.RUN_FINISHED:
        try:
            status = EventStatus(payload["status"])
        except (KeyError, TypeError, ValueError) as exc:
            raise _error(EventValidationCategory.INVALID_STATUS, "data.status") from exc
        if status not in {EventStatus.COMPLETED, EventStatus.FAILED, EventStatus.CANCELLED}:
            raise _error(EventValidationCategory.INVALID_STATUS, "data.status")
        return status
    status = EVENT_STATUS_BY_TYPE[event_type]
    if status is None:
        raise _error(EventValidationCategory.INVALID_STATUS, "event_type")
    return status


def normalize_runtime_event(event: RuntimeEvent) -> NormalizedEvent:
    """Convert one legacy source fact without mutating or passing through data."""

    if not isinstance(event, RuntimeEvent):
        raise _error(EventValidationCategory.INVALID_TYPE, "event")
    if not isinstance(event.event_type, EventType) or event.event_type not in SOURCE_SPECS:
        raise _error(EventValidationCategory.UNSUPPORTED_EVENT, "event_type")
    data = dict(event.data)
    _check_source_shape(event.event_type, data)

    correlation = EventCorrelation(
        call_id=data.get("call_id"),
        tool_call_id=data.get("tool_call_id"),
        batch_id=data.get("batch_id"),
    )
    payload = _project_payload(event.event_type, data)
    extensions = {"source_sequence": data["sequence"]} if "sequence" in data else {}
    return NormalizedEvent(
        run_id=event.run_id,
        occurred_at=event.timestamp,
        event_type=event.event_type,
        status=_event_status(event.event_type, payload),
        step=event.step,
        correlation=correlation,
        payload=payload,
        extensions=extensions,
    )
