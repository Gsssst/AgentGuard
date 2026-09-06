"""Bounded, failure-isolated process-local event collection."""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from types import MappingProxyType

from .contract import (
    EventEnvelope,
    EventValidationError,
    NormalizedEvent,
    RunSummaryStatus,
    normalize_utc_timestamp,
)
from .model import EventType, RuntimeEvent
from .normalize import normalize_runtime_event


DEFAULT_MAX_RUNS = 1000
DEFAULT_MAX_EVENTS_PER_RUN = 1000
DEFAULT_MAX_DIAGNOSTICS = 200

_TERMINAL_STATUSES = frozenset(
    {
        RunSummaryStatus.COMPLETED,
        RunSummaryStatus.FAILED,
        RunSummaryStatus.CANCELLED,
    }
)
_RETURN_TO_RUNNING = frozenset(
    {
        EventType.APPROVAL_GRANTED,
        EventType.RESUME_STARTED,
        EventType.TOOL_STARTED,
    }
)


class CollectorDiagnosticCategory(StrEnum):
    """Closed, safe categories for failures excluded from the timeline."""

    VALIDATION = "validation"
    INTERNAL = "internal"
    STATE = "state"
    CAPACITY = "capacity"


@dataclass(frozen=True, slots=True, kw_only=True)
class CollectorDiagnostic:
    """Bounded diagnostic metadata that never retains the rejected payload."""

    code: str
    category: CollectorDiagnosticCategory
    received_at: str
    run_id: str | None = None
    source_type: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CollectionResult:
    """Typed result for explicit collection without changing EventSink.emit()."""

    is_accepted: bool
    envelope: EventEnvelope | None = None
    code: str | None = None
    category: CollectorDiagnosticCategory | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RunSummary:
    """Immutable live view of one observed run."""

    run_id: str
    status: RunSummaryStatus
    first_observed_at: str
    started_at: str | None
    finished_at: str | None
    duration_seconds: float | None
    event_count: int
    retained_event_count: int
    first_retained_sequence: int | None
    last_sequence: int
    incomplete_start: bool


@dataclass(slots=True)
class _RunRecord:
    events: deque[EventEnvelope]
    summary: RunSummary


Clock = Callable[[], datetime | str]
Normalizer = Callable[[RuntimeEvent], NormalizedEvent]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_label(value: object, *, maximum: int = 256) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = "".join(character for character in value if ord(character) >= 32).strip()
    return cleaned[:maximum] or None


def _source_labels(event: object) -> tuple[str | None, str | None]:
    if isinstance(event, RuntimeEvent):
        source_type = event.event_type.value if isinstance(event.event_type, EventType) else "runtime_event"
        return _safe_label(event.run_id), _safe_label(source_type)
    return None, _safe_label(type(event).__name__, maximum=128)


def _as_utc_timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collector clock must return an aware datetime")
        value = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return normalize_utc_timestamp(value, field="received_at")


def _elapsed_seconds(started_at: str, finished_at: str) -> float | None:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    duration = (finish - start).total_seconds()
    return duration if duration >= 0 else None


def _positive_limit(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


class EventCollector:
    """Collect Runtime events into atomic per-run timelines and summaries."""

    def __init__(
        self,
        *,
        max_runs: int = DEFAULT_MAX_RUNS,
        max_events_per_run: int = DEFAULT_MAX_EVENTS_PER_RUN,
        max_diagnostics: int = DEFAULT_MAX_DIAGNOSTICS,
        clock: Clock = _utc_now,
        normalizer: Normalizer = normalize_runtime_event,
    ) -> None:
        self._max_runs = _positive_limit(max_runs, name="max_runs")
        self._max_events_per_run = _positive_limit(
            max_events_per_run,
            name="max_events_per_run",
        )
        max_diagnostics = _positive_limit(max_diagnostics, name="max_diagnostics")
        self._clock = clock
        self._normalizer = normalizer
        self._lock = Lock()
        self._runs: dict[str, _RunRecord] = {}
        self._diagnostics: deque[CollectorDiagnostic] = deque(maxlen=max_diagnostics)
        self._rejection_counts: Counter[str] = Counter()

    def emit(self, event: RuntimeEvent) -> None:
        """EventSink-compatible fail-open entry point."""

        try:
            self.accept(event)
        except Exception:
            # This last boundary deliberately catches Exception, never BaseException.
            self._record_failure(
                code="collector_internal_error",
                category=CollectorDiagnosticCategory.INTERNAL,
                event=event,
                received_at=_as_utc_timestamp(_utc_now()),
            )

    def accept(self, event: RuntimeEvent) -> CollectionResult:
        """Validate and atomically accept one source fact without raising."""

        fallback_received_at = _as_utc_timestamp(_utc_now())
        try:
            received_at = _as_utc_timestamp(self._clock())
            fact = self._normalizer(event)
            if not isinstance(fact, NormalizedEvent):
                raise TypeError("normalizer must return NormalizedEvent")
            return self._commit(fact, received_at)
        except EventValidationError as error:
            return self._record_failure(
                code=error.category.value,
                category=CollectorDiagnosticCategory.VALIDATION,
                event=event,
                received_at=locals().get("received_at", fallback_received_at),
            )
        except Exception:
            return self._record_failure(
                code="collector_internal_error",
                category=CollectorDiagnosticCategory.INTERNAL,
                event=event,
                received_at=locals().get("received_at", fallback_received_at),
            )

    def _commit(self, fact: NormalizedEvent, received_at: str) -> CollectionResult:
        # The fact and clock value are complete before this minimal state transaction.
        with self._lock:
            record = self._runs.get(fact.run_id)
            if record is not None and record.summary.status in _TERMINAL_STATUSES:
                return self._reject_locked(
                    code="run_already_terminal",
                    category=CollectorDiagnosticCategory.STATE,
                    received_at=received_at,
                    run_id=fact.run_id,
                    source_type=fact.event_type.value,
                )
            if record is None and len(self._runs) >= self._max_runs:
                return self._reject_locked(
                    code="run_capacity_reached",
                    category=CollectorDiagnosticCategory.CAPACITY,
                    received_at=received_at,
                    run_id=fact.run_id,
                    source_type=fact.event_type.value,
                )

            sequence = 1 if record is None else record.summary.last_sequence + 1
            envelope = EventEnvelope.from_fact(fact, sequence=sequence, received_at=received_at)
            if record is None:
                record = _RunRecord(
                    events=deque(maxlen=self._max_events_per_run),
                    summary=self._initial_summary(envelope),
                )
                self._runs[fact.run_id] = record

            record.events.append(envelope)
            summary = self._advance_summary(record.summary, envelope)
            first_retained = record.events[0].sequence if record.events else None
            record.summary = replace(
                summary,
                retained_event_count=len(record.events),
                first_retained_sequence=first_retained,
            )
            return CollectionResult(is_accepted=True, envelope=envelope)

    def _initial_summary(self, envelope: EventEnvelope) -> RunSummary:
        is_start = envelope.event_type is EventType.RUN_STARTED
        return RunSummary(
            run_id=envelope.run_id,
            status=RunSummaryStatus.RUNNING,
            first_observed_at=envelope.received_at,
            started_at=envelope.occurred_at if is_start else None,
            finished_at=None,
            duration_seconds=None,
            event_count=0,
            retained_event_count=0,
            first_retained_sequence=None,
            last_sequence=0,
            incomplete_start=not is_start,
        )

    def _advance_summary(self, summary: RunSummary, envelope: EventEnvelope) -> RunSummary:
        status = summary.status
        started_at = summary.started_at
        incomplete_start = summary.incomplete_start
        finished_at = summary.finished_at
        duration_seconds = summary.duration_seconds

        if envelope.event_type is EventType.RUN_STARTED and started_at is None:
            started_at = envelope.occurred_at
            incomplete_start = False
        if envelope.event_type is EventType.APPROVAL_REQUESTED:
            status = RunSummaryStatus.WAITING_APPROVAL
        elif envelope.event_type in _RETURN_TO_RUNNING and status is RunSummaryStatus.WAITING_APPROVAL:
            status = RunSummaryStatus.RUNNING
        elif envelope.event_type is EventType.RUN_FINISHED:
            status = RunSummaryStatus(envelope.payload["status"])
            finished_at = envelope.occurred_at
            if started_at is not None:
                duration_seconds = _elapsed_seconds(started_at, finished_at)
                if duration_seconds is None:
                    self._append_diagnostic_locked(
                        code="invalid_run_duration",
                        category=CollectorDiagnosticCategory.STATE,
                        received_at=envelope.received_at,
                        run_id=envelope.run_id,
                        source_type=envelope.event_type.value,
                    )

        return replace(
            summary,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            event_count=summary.event_count + 1,
            last_sequence=envelope.sequence,
            incomplete_start=incomplete_start,
        )

    def _record_failure(
        self,
        *,
        code: str,
        category: CollectorDiagnosticCategory,
        event: object,
        received_at: str,
    ) -> CollectionResult:
        run_id, source_type = _source_labels(event)
        with self._lock:
            return self._reject_locked(
                code=code,
                category=category,
                received_at=received_at,
                run_id=run_id,
                source_type=source_type,
            )

    def _reject_locked(
        self,
        *,
        code: str,
        category: CollectorDiagnosticCategory,
        received_at: str,
        run_id: str | None,
        source_type: str | None,
    ) -> CollectionResult:
        self._append_diagnostic_locked(
            code=code,
            category=category,
            received_at=received_at,
            run_id=run_id,
            source_type=source_type,
        )
        self._rejection_counts[code] += 1
        return CollectionResult(is_accepted=False, code=code, category=category)

    def _append_diagnostic_locked(
        self,
        *,
        code: str,
        category: CollectorDiagnosticCategory,
        received_at: str,
        run_id: str | None,
        source_type: str | None,
    ) -> None:
        self._diagnostics.append(
            CollectorDiagnostic(
                code=code,
                category=category,
                received_at=received_at,
                run_id=run_id,
                source_type=source_type,
            )
        )

    def get_events(self, run_id: str) -> tuple[EventEnvelope, ...]:
        with self._lock:
            record = self._runs.get(run_id)
            return tuple(record.events) if record is not None else ()

    def get_run(self, run_id: str) -> RunSummary | None:
        with self._lock:
            record = self._runs.get(run_id)
            return record.summary if record is not None else None

    def list_runs(self) -> tuple[RunSummary, ...]:
        with self._lock:
            return tuple(record.summary for record in self._runs.values())

    def diagnostics(self) -> tuple[CollectorDiagnostic, ...]:
        with self._lock:
            return tuple(self._diagnostics)

    def rejection_counts(self) -> Mapping[str, int]:
        with self._lock:
            return MappingProxyType(dict(self._rejection_counts))
