from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import subprocess
import sys
from threading import Barrier
from types import MappingProxyType

import pytest

from agentguard.events.collector import EventCollector, RunSummaryStatus
from agentguard.events.model import EventType, RuntimeEvent
from agentguard.events.normalize import normalize_runtime_event


def _event(
    event_type: EventType,
    run_id: str = "run-1",
    *,
    timestamp: str = "2026-09-06T00:00:00Z",
    **data: object,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_type=event_type,
        run_id=run_id,
        step=0,
        timestamp=timestamp,
        data=dict(data),
    )


def _call_event(
    event_type: EventType,
    run_id: str = "run-1",
    *,
    timestamp: str = "2026-09-06T00:00:00Z",
    **data: object,
) -> RuntimeEvent:
    return _event(
        event_type,
        run_id,
        timestamp=timestamp,
        call_id=f"call-{run_id}",
        **data,
    )


def test_concurrent_acceptance_allocates_contiguous_sequences_per_run() -> None:
    collector = EventCollector()
    workers = 8
    per_run = 40
    barrier = Barrier(workers)

    def emit_range(worker: int) -> None:
        barrier.wait()
        for index in range(worker, per_run * 2, workers):
            run_id = "run-a" if index < per_run else "run-b"
            result = collector.accept(_event(EventType.RUN_STARTED, run_id))
            assert result.is_accepted

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(emit_range, range(workers)))

    for run_id in ("run-a", "run-b"):
        events = collector.get_events(run_id)
        summary = collector.get_run(run_id)
        assert [event.sequence for event in events] == list(range(1, per_run + 1))
        assert summary is not None
        assert summary.last_sequence == per_run
        assert summary.event_count == per_run


def test_arrival_order_wins_and_identical_events_are_not_deduplicated() -> None:
    received = iter(
        [
            datetime(2026, 9, 6, 1, 0, tzinfo=UTC),
            datetime(2026, 9, 6, 1, 1, tzinfo=UTC),
            datetime(2026, 9, 6, 1, 2, tzinfo=UTC),
        ]
    )
    collector = EventCollector(clock=lambda: next(received))

    later = _event(
        EventType.RUN_STARTED,
        timestamp="2026-09-06T10:00:00Z",
        sequence=99,
    )
    earlier = _event(
        EventType.RUN_STARTED,
        timestamp="2026-09-06T09:00:00Z",
        sequence=1,
    )
    collector.emit(later)
    collector.emit(earlier)
    collector.emit(earlier)

    events = collector.get_events("run-1")
    assert [event.sequence for event in events] == [1, 2, 3]
    assert [event.occurred_at for event in events] == [
        "2026-09-06T10:00:00Z",
        "2026-09-06T09:00:00Z",
        "2026-09-06T09:00:00Z",
    ]
    assert [event.extensions["source_sequence"] for event in events] == [99, 1, 1]


@pytest.mark.parametrize(
    ("event", "expected_status"),
    [
        (
            _call_event(
                EventType.TOOL_FAILED,
                tool_name="write",
                error_type="RuntimeError",
                failure_kind="transient",
                attempts=2,
            ),
            RunSummaryStatus.RUNNING,
        ),
        (
            _call_event(
                EventType.TOOL_TIMED_OUT,
                tool_name="write",
                attempts=1,
                timeout_seconds=1.0,
                timeout_source="tool",
            ),
            RunSummaryStatus.RUNNING,
        ),
        (
            _call_event(
                EventType.PERMISSION_DENIED,
                tool_name="write",
                required_capabilities=[],
                forbidden_capabilities=["filesystem.write"],
                decision="denied",
            ),
            RunSummaryStatus.RUNNING,
        ),
        (
            _event(EventType.BATCH_FINISHED, batch_id="batch-1", size=2, failed=1),
            RunSummaryStatus.RUNNING,
        ),
    ],
)
def test_tool_and_batch_failures_do_not_terminate_run(
    event: RuntimeEvent,
    expected_status: RunSummaryStatus,
) -> None:
    collector = EventCollector()
    assert collector.accept(event).is_accepted
    assert collector.get_run("run-1").status is expected_status  # type: ignore[union-attr]


def test_approval_and_terminal_state_transitions_are_explicit() -> None:
    collector = EventCollector()
    collector.emit(_event(EventType.RUN_STARTED))
    collector.emit(
        _call_event(
            EventType.APPROVAL_REQUESTED,
            tool_name="write",
            required_capabilities=["filesystem.write"],
            decision="approval_required",
            action_digest="sha256:" + "a" * 64,
            arguments={"path": "safe.txt"},
        )
    )
    assert collector.get_run("run-1").status is RunSummaryStatus.WAITING_APPROVAL  # type: ignore[union-attr]

    collector.emit(
        _call_event(
            EventType.APPROVAL_GRANTED,
            tool_name="write",
            required_capabilities=["filesystem.write"],
            actor="operator",
            action_digest="sha256:" + "a" * 64,
        )
    )
    assert collector.get_run("run-1").status is RunSummaryStatus.RUNNING  # type: ignore[union-attr]

    collector.emit(
        _event(
            EventType.RUN_FINISHED,
            timestamp="2026-09-06T00:00:02Z",
            status="completed",
            stop_reason="finished",
        )
    )
    terminal = collector.get_run("run-1")
    assert terminal is not None
    assert terminal.status is RunSummaryStatus.COMPLETED
    assert terminal.duration_seconds == 2.0

    rejected = collector.accept(_event(EventType.RUN_STARTED))
    assert not rejected.is_accepted
    assert rejected.code == "run_already_terminal"
    assert collector.get_run("run-1") == terminal
    assert [item.sequence for item in collector.get_events("run-1")] == [1, 2, 3, 4]


def test_missing_start_and_late_start_have_truthful_timing_metadata() -> None:
    received = iter(
        [
            datetime(2026, 9, 6, 1, 0, tzinfo=UTC),
            datetime(2026, 9, 6, 1, 1, tzinfo=UTC),
            datetime(2026, 9, 6, 1, 2, tzinfo=UTC),
        ]
    )
    collector = EventCollector(clock=lambda: next(received))

    collector.emit(
        _call_event(
            EventType.TOOL_STARTED,
            timestamp="2026-09-06T00:00:01Z",
            tool_name="read",
        )
    )
    incomplete = collector.get_run("run-1")
    assert incomplete is not None
    assert incomplete.first_observed_at == "2026-09-06T01:00:00Z"
    assert incomplete.incomplete_start is True
    assert incomplete.started_at is None
    assert incomplete.duration_seconds is None

    collector.emit(_event(EventType.RUN_STARTED, timestamp="2026-09-06T00:00:00Z"))
    backfilled = collector.get_run("run-1")
    assert backfilled is not None
    assert backfilled.first_observed_at == incomplete.first_observed_at
    assert backfilled.incomplete_start is False
    assert backfilled.started_at == "2026-09-06T00:00:00Z"

    collector.emit(
        _event(
            EventType.RUN_FINISHED,
            timestamp="2026-09-06T00:00:03Z",
            status="failed",
            stop_reason="error",
        )
    )
    finished = collector.get_run("run-1")
    assert finished is not None
    assert finished.status is RunSummaryStatus.FAILED
    assert finished.duration_seconds == 3.0


def test_duplicate_nonterminal_start_does_not_reset_started_at() -> None:
    collector = EventCollector()
    collector.emit(_event(EventType.RUN_STARTED, timestamp="2026-09-06T00:00:00Z"))
    collector.emit(_event(EventType.RUN_STARTED, timestamp="2026-09-06T00:01:00Z"))
    summary = collector.get_run("run-1")
    assert summary is not None
    assert summary.started_at == "2026-09-06T00:00:00Z"
    assert summary.event_count == 2


def test_validation_and_internal_failures_are_safe_and_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "token=super-secret /Users/private/key.pem\nstack"

    def rejecting_normalizer(event: RuntimeEvent) -> object:
        raise RuntimeError(secret)

    collector = EventCollector(normalizer=rejecting_normalizer)
    assert collector.emit(_event(EventType.RUN_STARTED)) is None
    assert collector.accept(_event(EventType.RUN_STARTED)).is_accepted is False
    rendered = repr(collector.diagnostics())
    assert "super-secret" not in rendered
    assert "/Users/private" not in rendered
    assert "stack" not in rendered

    healthy = EventCollector()

    def broken_commit(*args: object, **kwargs: object) -> object:
        raise RuntimeError(secret)

    monkeypatch.setattr(healthy, "_commit", broken_commit)
    assert healthy.emit(_event(EventType.RUN_STARTED)) is None
    assert healthy.get_events("run-1") == ()
    assert "super-secret" not in repr(healthy.diagnostics())


def test_normalizer_can_reenter_read_api_without_deadlocking() -> None:
    collector: EventCollector

    def reentrant_normalizer(event: RuntimeEvent):  # type: ignore[no-untyped-def]
        assert collector.get_run(event.run_id) is None
        return normalize_runtime_event(event)

    collector = EventCollector(normalizer=reentrant_normalizer)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(collector.accept, _event(EventType.RUN_STARTED))
        assert future.result(timeout=1).is_accepted


def test_retention_limits_keep_truthful_total_and_range_metadata() -> None:
    collector = EventCollector(max_runs=2, max_events_per_run=3, max_diagnostics=2)
    for _ in range(5):
        assert collector.accept(_event(EventType.RUN_STARTED, "run-a")).is_accepted
    assert collector.accept(_event(EventType.RUN_STARTED, "run-b")).is_accepted

    events = collector.get_events("run-a")
    summary = collector.get_run("run-a")
    assert [event.sequence for event in events] == [3, 4, 5]
    assert summary is not None
    assert summary.event_count == 5
    assert summary.retained_event_count == 3
    assert summary.first_retained_sequence == 3
    assert summary.last_sequence == 5
    assert len(collector.list_runs()) == 2

    for run_id in ("run-c", "run-d", "run-e"):
        result = collector.accept(_event(EventType.RUN_STARTED, run_id))
        assert result.code == "run_capacity_reached"
    assert len(collector.diagnostics()) == 2
    assert collector.rejection_counts()["run_capacity_reached"] == 3


def test_terminal_identity_is_never_evicted_or_reused_at_capacity() -> None:
    collector = EventCollector(max_runs=2, max_events_per_run=3, max_diagnostics=3)
    collector.emit(_event(EventType.RUN_STARTED, "terminal"))
    collector.emit(
        _event(
            EventType.RUN_FINISHED,
            "terminal",
            status="completed",
            stop_reason="finished",
        )
    )
    terminal = collector.get_run("terminal")
    collector.emit(_event(EventType.RUN_STARTED, "active"))

    reused = collector.accept(_event(EventType.RUN_STARTED, "terminal"))
    overflow = collector.accept(_event(EventType.RUN_STARTED, "new-run"))
    assert reused.code == "run_already_terminal"
    assert overflow.code == "run_capacity_reached"
    assert reused.envelope is None and overflow.envelope is None
    assert collector.get_run("terminal") == terminal
    assert [event.sequence for event in collector.get_events("terminal")] == [1, 2]
    assert {summary.run_id for summary in collector.list_runs()} == {"terminal", "active"}


def test_public_snapshots_are_immutable_or_copy_safe() -> None:
    collector = EventCollector()
    collector.emit(_event(EventType.RUN_STARTED))
    collector.accept(object())  # type: ignore[arg-type]

    events = collector.get_events("run-1")
    summary = collector.get_run("run-1")
    diagnostics = collector.diagnostics()
    counts = collector.rejection_counts()
    assert isinstance(events, tuple)
    assert isinstance(diagnostics, tuple)
    assert isinstance(counts, MappingProxyType)
    assert summary is not None
    with pytest.raises(FrozenInstanceError):
        summary.event_count = 999  # type: ignore[misc]
    with pytest.raises(TypeError):
        events[0].payload["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        counts["collector_internal_error"] = 99  # type: ignore[index]
    assert collector.get_run("run-1").event_count == 1  # type: ignore[union-attr]
    assert sum(collector.rejection_counts().values()) == 1


@pytest.mark.parametrize(
    ("name", "value", "error"),
    [
        ("max_runs", True, TypeError),
        ("max_runs", 0, ValueError),
        ("max_events_per_run", -1, ValueError),
        ("max_diagnostics", 1.5, TypeError),
    ],
)
def test_invalid_limits_fail_fast(name: str, value: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        EventCollector(**{name: value})  # type: ignore[arg-type]


def test_public_event_exports_are_complete_and_unique() -> None:
    import agentguard
    import agentguard.events as events

    assert agentguard.EventCollector is events.EventCollector
    assert agentguard.EventEnvelope is events.EventEnvelope
    assert agentguard.RunSummary is events.RunSummary
    assert len(agentguard.__all__) == len(set(agentguard.__all__))
    assert len(events.__all__) == len(set(events.__all__))
    assert all(hasattr(agentguard, name) for name in agentguard.__all__)
    assert all(hasattr(events, name) for name in events.__all__)


def test_core_import_does_not_load_console_or_optional_frameworks() -> None:
    source_root = str(__file__).split("/tests/", 1)[0] + "/src"
    script = f"""
import builtins
import sys

sys.path.insert(0, {source_root!r})
blocked = ("fastapi", "langgraph", "langchain_core", "agentguard.integrations.langgraph", "agentguard.console")
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name.startswith(blocked):
        raise AssertionError(f"optional module loaded by core import: {{name}}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
import agentguard
from agentguard.events import EventCollector, EventEnvelope, normalize_runtime_event, safe_preview
assert agentguard.EventCollector is EventCollector
assert not any(name.startswith(blocked) for name in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
