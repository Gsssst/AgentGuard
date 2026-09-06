"""Structured Runtime events, safe contracts, and process-local collection."""

from agentguard._safety import SafePreview, safe_preview

from .collector import (
    DEFAULT_MAX_DIAGNOSTICS,
    DEFAULT_MAX_EVENTS_PER_RUN,
    DEFAULT_MAX_RUNS,
    CollectionResult,
    CollectorDiagnostic,
    CollectorDiagnosticCategory,
    EventCollector,
    RunSummary,
)
from .contract import (
    EVENT_SCHEMA_VERSION,
    EventCorrelation,
    EventEnvelope,
    EventStatus,
    EventValidationCategory,
    EventValidationError,
    NormalizedEvent,
    RunSummaryStatus,
)
from .model import EventType, RuntimeEvent
from .normalize import normalize_runtime_event
from .sinks import EventSink, InMemoryEventSink, JsonlEventSink

__all__ = [
    "CollectionResult",
    "CollectorDiagnostic",
    "CollectorDiagnosticCategory",
    "DEFAULT_MAX_DIAGNOSTICS",
    "DEFAULT_MAX_EVENTS_PER_RUN",
    "DEFAULT_MAX_RUNS",
    "EVENT_SCHEMA_VERSION",
    "EventCollector",
    "EventCorrelation",
    "EventEnvelope",
    "EventSink",
    "EventStatus",
    "EventType",
    "EventValidationCategory",
    "EventValidationError",
    "InMemoryEventSink",
    "JsonlEventSink",
    "NormalizedEvent",
    "RunSummary",
    "RunSummaryStatus",
    "RuntimeEvent",
    "SafePreview",
    "normalize_runtime_event",
    "safe_preview",
]
