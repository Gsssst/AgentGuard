"""Strict, dependency-light public event contract for AgentGuard telemetry."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import json
import math
import re
from types import MappingProxyType
from typing import Any

from .model import EventType


EVENT_SCHEMA_VERSION = "agentguard.event.v1"
ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "sequence",
        "occurred_at",
        "received_at",
        "event_type",
        "status",
        "step",
        "call_id",
        "tool_call_id",
        "batch_id",
        "payload",
        "extensions",
    }
)


class EventStatus(StrEnum):
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class RunSummaryStatus(StrEnum):
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventValidationCategory(StrEnum):
    INVALID_SCHEMA = "invalid_schema"
    INVALID_TYPE = "invalid_type"
    MISSING_FIELD = "missing_field"
    UNSUPPORTED_FIELD = "unsupported_field"
    INVALID_VALUE = "invalid_value"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_STATUS = "invalid_status"
    INVALID_CORRELATION = "invalid_correlation"
    UNSUPPORTED_EVENT = "unsupported_event"


class EventValidationError(ValueError):
    """A stable, safe-to-diagnose event contract rejection."""

    def __init__(self, category: EventValidationCategory, *, field: str | None = None) -> None:
        self.category = category
        self.field = field
        suffix = f": {field}" if field is not None else ""
        super().__init__(f"{category.value}{suffix}")


def _invalid(category: EventValidationCategory, field: str) -> EventValidationError:
    return EventValidationError(category, field=field)


def _validate_identifier(value: Any, *, field: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise _invalid(EventValidationCategory.INVALID_TYPE, field)
    if not value or value != value.strip() or len(value) > 256 or any(ord(char) < 32 for char in value):
        raise _invalid(EventValidationCategory.INVALID_VALUE, field)
    return value


def normalize_utc_timestamp(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise _invalid(EventValidationCategory.INVALID_TYPE, field)
    if not value or value != value.strip():
        raise _invalid(EventValidationCategory.INVALID_TIMESTAMP, field)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise _invalid(EventValidationCategory.INVALID_TIMESTAMP, field) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _invalid(EventValidationCategory.INVALID_TIMESTAMP, field)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _freeze_json(value: Any, *, field: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _invalid(EventValidationCategory.INVALID_VALUE, field)
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _invalid(EventValidationCategory.INVALID_TYPE, field)
            frozen[key] = _freeze_json(item, field=field)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, field=field) for item in value)
    raise _invalid(EventValidationCategory.INVALID_TYPE, field)


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _string(value: Any, *, field: str, values: frozenset[str] | None = None) -> None:
    if not isinstance(value, str):
        raise _invalid(EventValidationCategory.INVALID_TYPE, field)
    if not value or value != value.strip() or len(value) > 512 or any(ord(char) < 32 for char in value):
        raise _invalid(EventValidationCategory.INVALID_VALUE, field)
    if values is not None and value not in values:
        raise _invalid(EventValidationCategory.INVALID_VALUE, field)


def _integer(value: Any, *, field: str, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(EventValidationCategory.INVALID_TYPE, field)
    if value < minimum:
        raise _invalid(EventValidationCategory.INVALID_VALUE, field)


def _number(value: Any, *, field: str, minimum: float = 0.0, positive: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(EventValidationCategory.INVALID_TYPE, field)
    if not math.isfinite(float(value)) or value < minimum or (positive and value == 0):
        raise _invalid(EventValidationCategory.INVALID_VALUE, field)


def _boolean(value: Any, *, field: str) -> None:
    if not isinstance(value, bool):
        raise _invalid(EventValidationCategory.INVALID_TYPE, field)


def _labels(value: Any, *, field: str) -> None:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _invalid(EventValidationCategory.INVALID_TYPE, field)
    if len(value) > 20:
        raise _invalid(EventValidationCategory.INVALID_VALUE, field)
    for item in value:
        _string(item, field=field)


def _preview(value: Any, *, field: str) -> None:
    if not isinstance(value, Mapping) or set(value) != {"value", "truncated"}:
        raise _invalid(EventValidationCategory.INVALID_TYPE, field)
    _boolean(value["truncated"], field=field)
    frozen = _freeze_json(value["value"], field=field)
    json.dumps(_thaw_json(frozen), allow_nan=False)


def _digest(value: Any, *, field: str) -> None:
    _string(value, field=field)
    if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise _invalid(EventValidationCategory.INVALID_VALUE, field)


FieldValidator = Callable[[Any], None]


def _validator(function: Callable[..., None], field: str, **kwargs: Any) -> FieldValidator:
    return lambda value: function(value, field=field, **kwargs)


STRING = lambda field: _validator(_string, field)
NONNEGATIVE_INT = lambda field: _validator(_integer, field, minimum=0)
POSITIVE_INT = lambda field: _validator(_integer, field, minimum=1)
NONNEGATIVE_NUMBER = lambda field: _validator(_number, field, minimum=0.0)
POSITIVE_NUMBER = lambda field: _validator(_number, field, minimum=0.0, positive=True)
BOOLEAN = lambda field: _validator(_boolean, field)
LABELS = lambda field: _validator(_labels, field)
PREVIEW = lambda field: _validator(_preview, field)
DIGEST = lambda field: _validator(_digest, field)


COMMON_PAYLOAD_VALIDATORS: Mapping[str, FieldValidator] = MappingProxyType(
    {
        "resume_attempt": NONNEGATIVE_INT("payload.resume_attempt"),
        "duplicate_possible": BOOLEAN("payload.duplicate_possible"),
    }
)


@dataclass(frozen=True, slots=True)
class PayloadSpec:
    required: frozenset[str]
    validators: Mapping[str, FieldValidator]
    optional: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "validators", MappingProxyType(dict(self.validators)))
        declared = self.required | self.optional | frozenset(COMMON_PAYLOAD_VALIDATORS)
        if set(self.validators) != self.required | self.optional:
            raise ValueError("payload validators must match event-specific fields")
        if self.required & self.optional or not declared:
            raise ValueError("invalid payload specification")

    def validate(self, payload: Mapping[str, Any]) -> None:
        keys = frozenset(payload)
        missing = self.required - keys
        if missing:
            raise _invalid(EventValidationCategory.MISSING_FIELD, "payload")
        unknown = keys - self.required - self.optional - frozenset(COMMON_PAYLOAD_VALIDATORS)
        if unknown:
            raise _invalid(EventValidationCategory.UNSUPPORTED_FIELD, "payload")
        for field, value in payload.items():
            validator = self.validators.get(field) or COMMON_PAYLOAD_VALIDATORS.get(field)
            if validator is None:
                raise _invalid(EventValidationCategory.UNSUPPORTED_FIELD, "payload")
            validator(value)


def _spec(required: Mapping[str, FieldValidator] = MappingProxyType({}), optional: Mapping[str, FieldValidator] = MappingProxyType({})) -> PayloadSpec:
    validators = {**required, **optional}
    return PayloadSpec(frozenset(required), validators, frozenset(optional))


PAYLOAD_SPECS: Mapping[EventType, PayloadSpec] = MappingProxyType(
    {
        EventType.RUN_STARTED: _spec(),
        EventType.ACTION_PROPOSED: _spec(
            {"action_type": STRING("payload.action_type")},
            {
                "tool_name": STRING("payload.tool_name"),
                "arguments": PREVIEW("payload.arguments"),
                "reason_present": BOOLEAN("payload.reason_present"),
            },
        ),
        EventType.TOOL_STARTED: _spec({"tool_name": STRING("payload.tool_name")}),
        EventType.TOOL_ATTEMPT_STARTED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "attempt": POSITIVE_INT("payload.attempt"),
                "max_attempts": POSITIVE_INT("payload.max_attempts"),
                "retry_safety": _validator(
                    _string,
                    "payload.retry_safety",
                    values=frozenset({"safe", "unsafe", "requires_idempotency_key", "unknown"}),
                ),
            },
            {
                "timeout_seconds": POSITIVE_NUMBER("payload.timeout_seconds"),
                "timeout_source": STRING("payload.timeout_source"),
            },
        ),
        EventType.RETRY_SCHEDULED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "completed_attempt": POSITIVE_INT("payload.completed_attempt"),
                "next_attempt": POSITIVE_INT("payload.next_attempt"),
                "max_attempts": POSITIVE_INT("payload.max_attempts"),
                "delay_seconds": NONNEGATIVE_NUMBER("payload.delay_seconds"),
            },
            {"failure_kind": STRING("payload.failure_kind")},
        ),
        EventType.TOOL_SUCCEEDED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "attempts": NONNEGATIVE_INT("payload.attempts"),
                "result": PREVIEW("payload.result"),
            }
        ),
        EventType.TOOL_FAILED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "error_type": STRING("payload.error_type"),
                "failure_kind": STRING("payload.failure_kind"),
                "attempts": NONNEGATIVE_INT("payload.attempts"),
                "safe_summary": STRING("payload.safe_summary"),
            }
        ),
        EventType.TOOL_TIMED_OUT: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "attempts": NONNEGATIVE_INT("payload.attempts"),
                "timeout_seconds": POSITIVE_NUMBER("payload.timeout_seconds"),
                "timeout_source": STRING("payload.timeout_source"),
                "safe_summary": STRING("payload.safe_summary"),
            }
        ),
        EventType.TOOL_CANCELLED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "attempts": NONNEGATIVE_INT("payload.attempts"),
                "safe_summary": STRING("payload.safe_summary"),
            }
        ),
        EventType.LOOP_DETECTED: _spec(
            {
                "consecutive_count": POSITIVE_INT("payload.consecutive_count"),
                "threshold": POSITIVE_INT("payload.threshold"),
            }
        ),
        EventType.CHECKPOINT_WRITTEN: _spec({"lifecycle": STRING("payload.lifecycle")}),
        EventType.RESUME_STARTED: _spec(
            {
                "resume_attempt": POSITIVE_INT("payload.resume_attempt"),
                "duplicate_possible": BOOLEAN("payload.duplicate_possible"),
            }
        ),
        EventType.DUPLICATE_POSSIBLE: _spec(
            {
                "resume_attempt": POSITIVE_INT("payload.resume_attempt"),
                "safe_summary": STRING("payload.safe_summary"),
            }
        ),
        EventType.RECOVERY_REJECTED: _spec(
            {"error_type": STRING("payload.error_type"), "safe_summary": STRING("payload.safe_summary")}
        ),
        EventType.PERMISSION_DENIED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "required_capabilities": LABELS("payload.required_capabilities"),
                "forbidden_capabilities": LABELS("payload.forbidden_capabilities"),
                "decision": STRING("payload.decision"),
                "safe_summary": STRING("payload.safe_summary"),
            }
        ),
        EventType.APPROVAL_REQUESTED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "required_capabilities": LABELS("payload.required_capabilities"),
                "decision": STRING("payload.decision"),
                "action_digest": DIGEST("payload.action_digest"),
                "arguments": PREVIEW("payload.arguments"),
            }
        ),
        EventType.APPROVAL_GRANTED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "required_capabilities": LABELS("payload.required_capabilities"),
                "actor": STRING("payload.actor"),
                "action_digest": DIGEST("payload.action_digest"),
                "safe_summary": STRING("payload.safe_summary"),
            }
        ),
        EventType.APPROVAL_DENIED: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "required_capabilities": LABELS("payload.required_capabilities"),
                "actor": STRING("payload.actor"),
                "action_digest": DIGEST("payload.action_digest"),
                "safe_summary": STRING("payload.safe_summary"),
            }
        ),
        EventType.RESOURCE_WAITING: _spec(
            {"tool_name": STRING("payload.tool_name"), "resources": LABELS("payload.resources")}
        ),
        EventType.RESOURCE_LOCK_TIMEOUT: _spec(
            {
                "tool_name": STRING("payload.tool_name"),
                "resources": LABELS("payload.resources"),
                "failure_kind": STRING("payload.failure_kind"),
                "safe_summary": STRING("payload.safe_summary"),
            }
        ),
        EventType.BATCH_STARTED: _spec({"size": POSITIVE_INT("payload.size")}),
        EventType.BATCH_FINISHED: _spec(
            {"size": POSITIVE_INT("payload.size"), "failed": NONNEGATIVE_INT("payload.failed")}
        ),
        EventType.RUN_FINISHED: _spec(
            {"status": STRING("payload.status"), "stop_reason": STRING("payload.stop_reason")}
        ),
    }
)


EVENT_STATUS_BY_TYPE: Mapping[EventType, EventStatus | None] = MappingProxyType(
    {
        EventType.RUN_STARTED: EventStatus.RUNNING,
        EventType.ACTION_PROPOSED: EventStatus.RUNNING,
        EventType.TOOL_STARTED: EventStatus.RUNNING,
        EventType.TOOL_ATTEMPT_STARTED: EventStatus.RUNNING,
        EventType.RETRY_SCHEDULED: EventStatus.WAITING,
        EventType.TOOL_SUCCEEDED: EventStatus.SUCCEEDED,
        EventType.TOOL_FAILED: EventStatus.FAILED,
        EventType.TOOL_TIMED_OUT: EventStatus.TIMED_OUT,
        EventType.TOOL_CANCELLED: EventStatus.CANCELLED,
        EventType.LOOP_DETECTED: EventStatus.FAILED,
        EventType.CHECKPOINT_WRITTEN: EventStatus.RUNNING,
        EventType.RESUME_STARTED: EventStatus.RUNNING,
        EventType.DUPLICATE_POSSIBLE: EventStatus.RUNNING,
        EventType.RECOVERY_REJECTED: EventStatus.FAILED,
        EventType.PERMISSION_DENIED: EventStatus.FAILED,
        EventType.APPROVAL_REQUESTED: EventStatus.WAITING,
        EventType.APPROVAL_GRANTED: EventStatus.SUCCEEDED,
        EventType.APPROVAL_DENIED: EventStatus.FAILED,
        EventType.RESOURCE_WAITING: EventStatus.WAITING,
        EventType.RESOURCE_LOCK_TIMEOUT: EventStatus.TIMED_OUT,
        EventType.BATCH_STARTED: EventStatus.RUNNING,
        EventType.BATCH_FINISHED: EventStatus.COMPLETED,
        EventType.RUN_FINISHED: None,
    }
)


CALL_EVENTS = frozenset(
    {
        EventType.TOOL_STARTED,
        EventType.TOOL_ATTEMPT_STARTED,
        EventType.RETRY_SCHEDULED,
        EventType.TOOL_SUCCEEDED,
        EventType.TOOL_FAILED,
        EventType.TOOL_TIMED_OUT,
        EventType.TOOL_CANCELLED,
        EventType.LOOP_DETECTED,
        EventType.PERMISSION_DENIED,
        EventType.APPROVAL_REQUESTED,
        EventType.APPROVAL_GRANTED,
        EventType.APPROVAL_DENIED,
        EventType.RESOURCE_WAITING,
        EventType.RESOURCE_LOCK_TIMEOUT,
    }
)
BATCH_EVENTS = frozenset({EventType.BATCH_STARTED, EventType.BATCH_FINISHED})


@dataclass(frozen=True, slots=True, kw_only=True)
class EventCorrelation:
    call_id: str | None = None
    tool_call_id: str | None = None
    batch_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "call_id", _validate_identifier(self.call_id, field="call_id", nullable=True))
        object.__setattr__(
            self,
            "tool_call_id",
            _validate_identifier(self.tool_call_id, field="tool_call_id", nullable=True),
        )
        object.__setattr__(self, "batch_id", _validate_identifier(self.batch_id, field="batch_id", nullable=True))
        if self.tool_call_id is not None and self.call_id is None:
            raise _invalid(EventValidationCategory.INVALID_CORRELATION, "tool_call_id")


def _validate_step(step: Any) -> int | None:
    if step is None:
        return None
    if isinstance(step, bool) or not isinstance(step, int):
        raise _invalid(EventValidationCategory.INVALID_TYPE, "step")
    if step < 0:
        raise _invalid(EventValidationCategory.INVALID_VALUE, "step")
    return step


def _validate_status(event_type: EventType, status: EventStatus, payload: Mapping[str, Any]) -> None:
    expected = EVENT_STATUS_BY_TYPE[event_type]
    if event_type is EventType.RUN_FINISHED:
        terminal = payload.get("status")
        try:
            expected = EventStatus(terminal)
        except (TypeError, ValueError) as exc:
            raise _invalid(EventValidationCategory.INVALID_STATUS, "payload.status") from exc
        if expected not in {EventStatus.COMPLETED, EventStatus.FAILED, EventStatus.CANCELLED}:
            raise _invalid(EventValidationCategory.INVALID_STATUS, "payload.status")
    if status is not expected:
        raise _invalid(EventValidationCategory.INVALID_STATUS, "status")


def _validate_correlation(event_type: EventType, correlation: EventCorrelation, payload: Mapping[str, Any]) -> None:
    requires_call = event_type in CALL_EVENTS or (
        event_type is EventType.ACTION_PROPOSED and payload.get("action_type") == "CallTool"
    )
    finish_action = event_type is EventType.ACTION_PROPOSED and payload.get("action_type") == "Finish"
    if requires_call and correlation.call_id is None:
        raise _invalid(EventValidationCategory.INVALID_CORRELATION, "call_id")
    if not requires_call and correlation.call_id is not None:
        raise _invalid(EventValidationCategory.INVALID_CORRELATION, "call_id")
    if finish_action and (correlation.tool_call_id is not None or correlation.batch_id is not None):
        raise _invalid(EventValidationCategory.INVALID_CORRELATION, "action_proposed")
    if event_type in BATCH_EVENTS:
        if correlation.batch_id is None or correlation.tool_call_id is not None:
            raise _invalid(EventValidationCategory.INVALID_CORRELATION, "batch_id")
    elif not requires_call and correlation.batch_id is not None:
        raise _invalid(EventValidationCategory.INVALID_CORRELATION, "batch_id")


def _validate_payload(event_type: EventType, payload: Mapping[str, Any]) -> None:
    PAYLOAD_SPECS[event_type].validate(payload)
    if event_type is EventType.ACTION_PROPOSED:
        action_type = payload["action_type"]
        if action_type == "CallTool":
            if "tool_name" not in payload or "arguments" not in payload or "reason_present" in payload:
                raise _invalid(EventValidationCategory.MISSING_FIELD, "payload")
        elif action_type == "Finish":
            if "tool_name" in payload or "arguments" in payload:
                raise _invalid(EventValidationCategory.UNSUPPORTED_FIELD, "payload")
        else:
            raise _invalid(EventValidationCategory.INVALID_VALUE, "payload.action_type")
    elif event_type is EventType.TOOL_ATTEMPT_STARTED:
        if payload["attempt"] > payload["max_attempts"]:
            raise _invalid(EventValidationCategory.INVALID_VALUE, "payload.attempt")
        if ("timeout_seconds" in payload) != ("timeout_source" in payload):
            raise _invalid(EventValidationCategory.MISSING_FIELD, "payload.timeout")
    elif event_type is EventType.RETRY_SCHEDULED:
        if payload["next_attempt"] != payload["completed_attempt"] + 1:
            raise _invalid(EventValidationCategory.INVALID_VALUE, "payload.next_attempt")
        if payload["next_attempt"] > payload["max_attempts"]:
            raise _invalid(EventValidationCategory.INVALID_VALUE, "payload.max_attempts")
    elif event_type is EventType.BATCH_FINISHED and payload["failed"] > payload["size"]:
        raise _invalid(EventValidationCategory.INVALID_VALUE, "payload.failed")
    elif event_type is EventType.RUN_FINISHED:
        if payload["status"] not in {"completed", "failed", "cancelled"}:
            raise _invalid(EventValidationCategory.INVALID_STATUS, "payload.status")


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedEvent:
    run_id: str
    occurred_at: str
    event_type: EventType
    status: EventStatus
    step: int | None
    correlation: EventCorrelation
    payload: Mapping[str, Any]
    extensions: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _validate_identifier(self.run_id, field="run_id"))
        object.__setattr__(self, "occurred_at", normalize_utc_timestamp(self.occurred_at, field="occurred_at"))
        if not isinstance(self.event_type, EventType):
            raise _invalid(EventValidationCategory.UNSUPPORTED_EVENT, "event_type")
        if not isinstance(self.status, EventStatus):
            raise _invalid(EventValidationCategory.INVALID_STATUS, "status")
        object.__setattr__(self, "step", _validate_step(self.step))
        if not isinstance(self.correlation, EventCorrelation):
            raise _invalid(EventValidationCategory.INVALID_TYPE, "correlation")
        if not isinstance(self.payload, Mapping) or not isinstance(self.extensions, Mapping):
            raise _invalid(EventValidationCategory.INVALID_TYPE, "payload")
        _validate_payload(self.event_type, self.payload)
        _validate_status(self.event_type, self.status, self.payload)
        _validate_correlation(self.event_type, self.correlation, self.payload)
        object.__setattr__(self, "payload", _freeze_json(self.payload, field="payload"))
        object.__setattr__(self, "extensions", _validated_extensions(self.extensions))


def _validated_extensions(extensions: Mapping[str, Any]) -> Mapping[str, Any]:
    unknown = set(extensions) - {"source_sequence"}
    if unknown:
        raise _invalid(EventValidationCategory.UNSUPPORTED_FIELD, "extensions")
    if "source_sequence" in extensions:
        _integer(extensions["source_sequence"], field="extensions.source_sequence", minimum=0)
    return _freeze_json(extensions, field="extensions")


@dataclass(frozen=True, slots=True, kw_only=True)
class EventEnvelope:
    schema_version: str
    run_id: str
    sequence: int
    occurred_at: str
    received_at: str
    event_type: EventType
    status: EventStatus
    step: int | None
    call_id: str | None
    tool_call_id: str | None
    batch_id: str | None
    payload: Mapping[str, Any]
    extensions: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise _invalid(EventValidationCategory.INVALID_SCHEMA, "schema_version")
        object.__setattr__(self, "run_id", _validate_identifier(self.run_id, field="run_id"))
        _integer(self.sequence, field="sequence", minimum=1)
        object.__setattr__(self, "occurred_at", normalize_utc_timestamp(self.occurred_at, field="occurred_at"))
        object.__setattr__(self, "received_at", normalize_utc_timestamp(self.received_at, field="received_at"))
        if not isinstance(self.event_type, EventType):
            raise _invalid(EventValidationCategory.UNSUPPORTED_EVENT, "event_type")
        if not isinstance(self.status, EventStatus):
            raise _invalid(EventValidationCategory.INVALID_STATUS, "status")
        object.__setattr__(self, "step", _validate_step(self.step))
        correlation = EventCorrelation(
            call_id=self.call_id,
            tool_call_id=self.tool_call_id,
            batch_id=self.batch_id,
        )
        if not isinstance(self.payload, Mapping) or not isinstance(self.extensions, Mapping):
            raise _invalid(EventValidationCategory.INVALID_TYPE, "payload")
        _validate_payload(self.event_type, self.payload)
        _validate_status(self.event_type, self.status, self.payload)
        _validate_correlation(self.event_type, correlation, self.payload)
        object.__setattr__(self, "payload", _freeze_json(self.payload, field="payload"))
        object.__setattr__(self, "extensions", _validated_extensions(self.extensions))

    @classmethod
    def from_fact(cls, fact: NormalizedEvent, *, sequence: int, received_at: str) -> "EventEnvelope":
        if not isinstance(fact, NormalizedEvent):
            raise _invalid(EventValidationCategory.INVALID_TYPE, "fact")
        return cls(
            schema_version=EVENT_SCHEMA_VERSION,
            run_id=fact.run_id,
            sequence=sequence,
            occurred_at=fact.occurred_at,
            received_at=received_at,
            event_type=fact.event_type,
            status=fact.status,
            step=fact.step,
            call_id=fact.correlation.call_id,
            tool_call_id=fact.correlation.tool_call_id,
            batch_id=fact.correlation.batch_id,
            payload=fact.payload,
            extensions=fact.extensions,
        )

    @classmethod
    def from_dict(cls, raw: Any) -> "EventEnvelope":
        if not isinstance(raw, Mapping):
            raise _invalid(EventValidationCategory.INVALID_TYPE, "envelope")
        missing = ENVELOPE_FIELDS - set(raw)
        if missing:
            raise _invalid(EventValidationCategory.MISSING_FIELD, "envelope")
        unknown = set(raw) - ENVELOPE_FIELDS
        if unknown:
            raise _invalid(EventValidationCategory.UNSUPPORTED_FIELD, "envelope")
        if raw["schema_version"] != EVENT_SCHEMA_VERSION:
            raise _invalid(EventValidationCategory.INVALID_SCHEMA, "schema_version")
        try:
            event_type = EventType(raw["event_type"])
        except (TypeError, ValueError) as exc:
            raise _invalid(EventValidationCategory.UNSUPPORTED_EVENT, "event_type") from exc
        try:
            status = EventStatus(raw["status"])
        except (TypeError, ValueError) as exc:
            raise _invalid(EventValidationCategory.INVALID_STATUS, "status") from exc
        return cls(
            schema_version=raw["schema_version"],
            run_id=raw["run_id"],
            sequence=raw["sequence"],
            occurred_at=raw["occurred_at"],
            received_at=raw["received_at"],
            event_type=event_type,
            status=status,
            step=raw["step"],
            call_id=raw["call_id"],
            tool_call_id=raw["tool_call_id"],
            batch_id=raw["batch_id"],
            payload=raw["payload"],
            extensions=raw["extensions"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "sequence": self.sequence,
            "occurred_at": self.occurred_at,
            "received_at": self.received_at,
            "event_type": self.event_type.value,
            "status": self.status.value,
            "step": self.step,
            "call_id": self.call_id,
            "tool_call_id": self.tool_call_id,
            "batch_id": self.batch_id,
            "payload": _thaw_json(self.payload),
            "extensions": _thaw_json(self.extensions),
        }
