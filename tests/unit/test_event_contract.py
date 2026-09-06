import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from agentguard.events.contract import (
    EVENT_SCHEMA_VERSION,
    EVENT_STATUS_BY_TYPE,
    PAYLOAD_SPECS,
    EventEnvelope,
    EventStatus,
    EventValidationCategory,
    EventValidationError,
)
from agentguard.events.model import EventType, RuntimeEvent
from agentguard.events.normalize import normalize_runtime_event


NOW = "2026-09-06T09:00:00+08:00"
RECEIVED = "2026-09-06T01:00:01Z"
CALL_ID = "call-123"
BATCH_ID = "batch-123"
DIGEST = "sha256:" + "a" * 64


def _correlation(event_type: EventType) -> dict[str, object]:
    call_events = {
        EventType.ACTION_PROPOSED,
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
    if event_type in call_events:
        return {"call_id": CALL_ID, "tool_call_id": "external-123", "batch_id": None}
    if event_type in {EventType.BATCH_STARTED, EventType.BATCH_FINISHED}:
        return {"call_id": None, "tool_call_id": None, "batch_id": BATCH_ID}
    return {"call_id": None, "tool_call_id": None, "batch_id": None}


def _event_data(event_type: EventType) -> dict[str, object]:
    fixtures: dict[EventType, dict[str, object]] = {
        EventType.RUN_STARTED: {"resume_attempt": 0, "duplicate_possible": False},
        EventType.ACTION_PROPOSED: {
            "action_type": "CallTool",
            "tool_name": "echo",
            "arguments": {"value": 1, "api_token": "secret-value"},
        },
        EventType.TOOL_STARTED: {"tool_name": "echo"},
        EventType.TOOL_ATTEMPT_STARTED: {
            "tool_name": "echo",
            "attempt": 1,
            "max_attempts": 2,
            "retry_safety": "safe",
            "timeout_seconds": 1.5,
            "timeout_source": "tool",
        },
        EventType.RETRY_SCHEDULED: {
            "tool_name": "echo",
            "completed_attempt": 1,
            "next_attempt": 2,
            "max_attempts": 2,
            "delay_seconds": 0.1,
            "failure_kind": "transient",
        },
        EventType.TOOL_SUCCEEDED: {
            "tool_name": "echo",
            "attempts": 1,
            "value": {"password": "secret-value", "ok": True},
        },
        EventType.TOOL_FAILED: {
            "tool_name": "echo",
            "error_type": "RuntimeError",
            "error_message": "secret-value /Users/alice/key\nforged",
            "failure_kind": "permanent",
            "attempts": 1,
            "stack": "secret-stack",
        },
        EventType.TOOL_TIMED_OUT: {
            "tool_name": "echo",
            "attempts": 1,
            "timeout_seconds": 1.5,
            "timeout_source": "runtime",
            "error_message": "secret-timeout",
        },
        EventType.TOOL_CANCELLED: {
            "tool_name": "echo",
            "attempts": 1,
            "error_message": "secret-cancel",
        },
        EventType.LOOP_DETECTED: {
            "signature": '{"arguments":{"password":"secret-value"}}',
            "consecutive_count": 3,
            "threshold": 3,
        },
        EventType.CHECKPOINT_WRITTEN: {
            "lifecycle": "active",
            "checkpoint_path": "/Users/alice/private/checkpoint.json",
        },
        EventType.RESUME_STARTED: {
            "resume_attempt": 1,
            "duplicate_possible": True,
            "checkpoint_path": "/Users/alice/private/checkpoint.json",
        },
        EventType.DUPLICATE_POSSIBLE: {"resume_attempt": 1},
        EventType.RECOVERY_REJECTED: {
            "error_type": "CheckpointValidationError",
            "error_message": "secret-value /Users/alice/private",
        },
        EventType.PERMISSION_DENIED: {
            "tool_name": "delete",
            "required_capabilities": ["destructive"],
            "forbidden_capabilities": ["destructive"],
            "decision": "deny",
            "reason": "secret policy reason",
        },
        EventType.APPROVAL_REQUESTED: {
            "tool_name": "send",
            "required_capabilities": ["external"],
            "decision": "approval_required",
            "action_digest": DIGEST,
            "arguments": {"authorization": "secret-value", "recipient": "team"},
            "status": "waiting_approval",
        },
        EventType.APPROVAL_GRANTED: {
            "tool_name": "send",
            "required_capabilities": ["external"],
            "action_digest": DIGEST,
            "actor": "local_user",
            "reason": "secret-value approved",
        },
        EventType.APPROVAL_DENIED: {
            "tool_name": "send",
            "required_capabilities": ["external"],
            "action_digest": DIGEST,
            "actor": "local_user",
            "reason": "secret-value denied",
        },
        EventType.RESOURCE_WAITING: {"tool_name": "write", "resources": ["file:one"]},
        EventType.RESOURCE_LOCK_TIMEOUT: {
            "tool_name": "write",
            "resources": ["file:one"],
            "failure_kind": "resource_lock_timeout",
            "error_message": "secret-value /Users/alice/private",
        },
        EventType.BATCH_STARTED: {"size": 2},
        EventType.BATCH_FINISHED: {"size": 2, "failed": 1},
        EventType.RUN_FINISHED: {"status": "completed", "stop_reason": "completed"},
    }
    return {"sequence": 99, **_correlation(event_type), **fixtures[event_type]}


def _source(event_type: EventType) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=event_type,
        run_id="run-123",
        step=1,
        data=_event_data(event_type),
        timestamp=NOW,
    )


def _envelope(event_type: EventType) -> EventEnvelope:
    fact = normalize_runtime_event(_source(event_type))
    return EventEnvelope.from_fact(fact, sequence=1, received_at=RECEIVED)


def test_every_event_type_has_one_payload_spec_and_status_mapping() -> None:
    assert set(PAYLOAD_SPECS) == set(EventType)
    assert set(EVENT_STATUS_BY_TYPE) == set(EventType)


@pytest.mark.parametrize("event_type", list(EventType))
def test_every_legacy_event_normalizes_to_the_fixed_v1_shape(event_type: EventType) -> None:
    envelope = _envelope(event_type)
    raw = envelope.to_dict()

    assert set(raw) == {
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
    assert raw["schema_version"] == EVENT_SCHEMA_VERSION
    assert raw["occurred_at"] == "2026-09-06T01:00:00Z"
    assert raw["received_at"] == RECEIVED
    assert raw["extensions"] == {"source_sequence": 99}
    json.dumps(raw, allow_nan=False)


def test_arguments_and_results_are_bounded_redacted_previews() -> None:
    proposed = _envelope(EventType.ACTION_PROPOSED).to_dict()
    succeeded = _envelope(EventType.TOOL_SUCCEEDED).to_dict()

    assert proposed["payload"]["arguments"] == {
        "value": {"value": 1, "api_token": "[REDACTED]"},
        "truncated": False,
    }
    assert succeeded["payload"]["result"] == {
        "value": {"password": "[REDACTED]", "ok": True},
        "truncated": False,
    }


def test_failure_projection_discards_raw_messages_paths_signatures_reasons_and_unknown_text() -> None:
    encoded = json.dumps(
        [
            _envelope(event_type).to_dict()
            for event_type in (
                EventType.TOOL_FAILED,
                EventType.TOOL_TIMED_OUT,
                EventType.TOOL_CANCELLED,
                EventType.LOOP_DETECTED,
                EventType.CHECKPOINT_WRITTEN,
                EventType.RESUME_STARTED,
                EventType.RECOVERY_REJECTED,
                EventType.PERMISSION_DENIED,
                EventType.APPROVAL_GRANTED,
                EventType.APPROVAL_DENIED,
                EventType.RESOURCE_LOCK_TIMEOUT,
            )
        ],
        allow_nan=False,
    )

    for forbidden in ("secret-value", "/Users/alice", "forged", "secret-stack", "policy reason"):
        assert forbidden not in encoded
    assert "safe_summary" in encoded


@pytest.mark.parametrize(
    ("mutate", "category"),
    [
        (lambda raw: raw.__setitem__("schema_version", "agentguard.event.v2"), EventValidationCategory.INVALID_SCHEMA),
        (lambda raw: raw.pop("run_id"), EventValidationCategory.MISSING_FIELD),
        (lambda raw: raw.__setitem__("unexpected", True), EventValidationCategory.UNSUPPORTED_FIELD),
        (lambda raw: raw.__setitem__("sequence", True), EventValidationCategory.INVALID_TYPE),
        (lambda raw: raw.__setitem__("sequence", 0), EventValidationCategory.INVALID_VALUE),
        (lambda raw: raw.__setitem__("run_id", ""), EventValidationCategory.INVALID_VALUE),
        (lambda raw: raw.__setitem__("occurred_at", "2026-09-06T01:00:00"), EventValidationCategory.INVALID_TIMESTAMP),
        (lambda raw: raw.__setitem__("status", "invented"), EventValidationCategory.INVALID_STATUS),
    ],
)
def test_envelope_decoder_rejects_invalid_top_level_shapes(mutate, category: EventValidationCategory) -> None:
    raw = _envelope(EventType.RUN_STARTED).to_dict()
    mutate(raw)

    with pytest.raises(EventValidationError) as caught:
        EventEnvelope.from_dict(raw)
    assert caught.value.category is category


def test_payload_and_correlation_rules_are_strict() -> None:
    unknown = _source(EventType.TOOL_SUCCEEDED)
    unknown.data["surprise"] = "must not be copied"
    with pytest.raises(EventValidationError) as unsupported:
        normalize_runtime_event(unknown)
    assert unsupported.value.category is EventValidationCategory.UNSUPPORTED_FIELD

    missing_call = _source(EventType.TOOL_STARTED)
    missing_call.data["call_id"] = None
    with pytest.raises(EventValidationError) as correlation:
        normalize_runtime_event(missing_call)
    assert correlation.value.category is EventValidationCategory.INVALID_CORRELATION

    run_with_call = _source(EventType.RUN_STARTED)
    run_with_call.data["call_id"] = CALL_ID
    with pytest.raises(EventValidationError) as run_correlation:
        normalize_runtime_event(run_with_call)
    assert run_correlation.value.category is EventValidationCategory.INVALID_CORRELATION

    batch_without_id = _source(EventType.BATCH_STARTED)
    batch_without_id.data["batch_id"] = None
    with pytest.raises(EventValidationError) as batch_correlation:
        normalize_runtime_event(batch_without_id)
    assert batch_correlation.value.category is EventValidationCategory.INVALID_CORRELATION


def test_batch_finished_counts_and_run_terminal_status_are_validated() -> None:
    bad_batch = _source(EventType.BATCH_FINISHED)
    bad_batch.data["failed"] = 3
    with pytest.raises(EventValidationError) as batch_error:
        normalize_runtime_event(bad_batch)
    assert batch_error.value.category is EventValidationCategory.INVALID_VALUE

    running_finish = _source(EventType.RUN_FINISHED)
    running_finish.data["status"] = "running"
    with pytest.raises(EventValidationError) as run_error:
        normalize_runtime_event(running_finish)
    assert run_error.value.category is EventValidationCategory.INVALID_STATUS


def test_payload_and_extensions_are_detached_from_callers() -> None:
    envelope = _envelope(EventType.TOOL_SUCCEEDED)
    raw = envelope.to_dict()
    raw["payload"]["result"]["value"]["ok"] = False
    raw["extensions"]["source_sequence"] = 1000

    assert envelope.to_dict()["payload"]["result"]["value"]["ok"] is True
    assert envelope.to_dict()["extensions"] == {"source_sequence": 99}


def test_runtime_event_and_legacy_dict_shape_remain_unchanged() -> None:
    source = _source(EventType.RUN_STARTED)
    before = deepcopy(source.to_dict())

    normalize_runtime_event(source)

    assert source.to_dict() == before
    assert set(source.to_dict()) == {"event_type", "run_id", "step", "timestamp", "data"}
