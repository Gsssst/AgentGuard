# ADR 002: Phase 1 Structured Events

**Status:** Accepted for Phase 1  
**Date:** 2026-08-31

## Decision

Represent important Runtime facts as typed `RuntimeEvent` values and send them through a small `EventSink` protocol. Phase 1 provides an in-memory sink for assertions and a JSONL sink for local run evidence.

## Rationale

An ordinary text log is useful for a human but difficult to query reliably. A structured event stream gives each event a stable type, run ID, step, timestamp, and serializable data payload. Keeping the sink separate from Runtime execution allows later SQLite, HTTP, or Control Plane sinks without changing Router or Tool semantics.

## Boundary

- `RunState` is current decision state.
- `RuntimeEvent` is an immutable fact about an execution transition.
- A future Checkpoint will be a resumable state snapshot; it is intentionally not implemented here.

## Evidence

`tests/unit/test_event_sinks.py` verifies in-memory ordering, JSONL parsing, Unicode data, and defensive data copying. Runtime integration tests verify event ordering for a successful run and event emission for Tool failure.
