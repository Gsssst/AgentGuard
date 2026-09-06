---
phase: 11-event-contract-and-collector
plan: 03
subsystem: events
tags: [python, threading, bounded-retention, event-collector, immutable-snapshots]

requires:
  - phase: 11-event-contract-and-collector
    plan: 01
    provides: strict agentguard.event.v1 normalization, immutable facts, and safe validation categories
  - phase: 11-event-contract-and-collector
    plan: 02
    provides: producer-owned run, call, tool-call, and batch correlation
provides:
  - atomic process-local event sequencing and explicit run-summary transitions
  - bounded per-run timelines, diagnostics, and run identity retention
  - dependency-light public Collector and v1 event contract exports
affects: [11-04-langgraph-observability, phase-12-history-api, phase-13-live-streaming, phase-14-console]

tech-stack:
  added: []
  patterns: [minimal threading.Lock transaction, bounded deque retention, frozen public snapshots, fail-open sink boundary]

key-files:
  created:
    - src/agentguard/events/collector.py
    - tests/unit/test_event_collector.py
  modified:
    - src/agentguard/events/__init__.py
    - src/agentguard/__init__.py

key-decisions:
  - "Normalize and timestamp source events before locking, then atomically perform terminal checks, sequence allocation, append, and immutable summary replacement."
  - "Retain every accepted run identity for the Collector lifetime and reject new runs at capacity instead of evicting terminal identities that could later be reused."
  - "Expose frozen values, tuples, and read-only mapping copies while keeping diagnostics outside the normal event stream."

patterns-established:
  - "Collector transaction: only trusted NormalizedEvent facts enter the lock-protected authoritative timeline."
  - "Truthful retention: total event count and retained sequence range remain explicit after bounded deque eviction."
  - "Fail-open observability: validation and internal Exceptions become bounded safe diagnostics and never propagate through EventSink.emit()."

requirements-completed: [OBS-03, OBS-04, COMPAT-01]

duration: 5 min
completed: 2026-09-06
---

# Phase 11 Plan 03: Event Collector Summary

**A thread-safe process-local Collector now turns normalized Runtime facts into contiguous v1 timelines and immutable run summaries while enforcing explicit memory, terminal-identity, and failure-isolation boundaries.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-09-06T07:27:39Z
- **Completed:** 2026-09-06T07:32:51Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added atomic per-run sequence allocation and explicit run-summary transitions for incomplete starts, late starts, approvals, recovery, nonterminal tool/batch failures, and terminal `run_finished` events.
- Bounded run identities, per-run event retention, and diagnostics while preserving total counts and retained sequence-range metadata.
- Kept validation and internal Collector failures out of the observed Agent through safe, fixed diagnostics that never retain exception text, stacks, or candidate payloads.
- Exposed immutable/copy-safe snapshots and dependency-light core imports without loading LangGraph, FastAPI, Console, or frontend modules.
- Added deterministic ThreadPoolExecutor/barrier, reentrant-normalizer, state-machine, capacity, immutability, and import-isolation evidence.

## Task Commits

Task 1 followed the required TDD RED/GREEN sequence; subsequent tasks were committed atomically:

1. **Task 1 RED: Define Collector concurrency, transition, timing, and fail-open behavior** — `ad0f16e` (test)
2. **Task 1 GREEN: Implement atomic sequencing and run-summary transitions** — `fa899be` (feat)
3. **Task 2: Bound retention and preserve terminal run identity** — `1f31401` (feat)
4. **Task 3: Export the dependency-light Collector core API** — `5ce4812` (feat)

## Files Created/Modified

- `src/agentguard/events/collector.py` — Bounded timelines, lock-protected sequence/summary transaction, immutable snapshots, safe diagnostics, and rejection counters.
- `tests/unit/test_event_collector.py` — Concurrent ordering, lifecycle state machine, retention, terminal reuse, failure isolation, immutability, and import-boundary tests.
- `src/agentguard/events/__init__.py` — Public v1 contract, normalizer, safe preview, Collector, summary, result, and diagnostic exports.
- `src/agentguard/__init__.py` — Primary `EventCollector`, `EventEnvelope`, and `RunSummary` root exports.

## Decisions Made

- Used one ordinary `threading.Lock` because `EventSink.emit()` may run from OS threads; custom clocks and normalizers execute before lock acquisition and can safely re-enter read APIs.
- Kept arrival/lock acceptance order authoritative. Source timestamps and `extensions.source_sequence` remain evidence but never control order or deduplication.
- Allowed a late `run_started` to backfill `started_at` while preserving earlier sequences and `first_observed_at`; repeated nonterminal starts remain separate evidence without resetting timing.
- Only `run_finished` creates a terminal run status. Tool, permission, approval-denial, lock, and batch failures remain nonterminal facts.
- Chose safe capacity rejection over eviction so a terminal `run_id` can never be forgotten and resurrected in the same Collector lifetime.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The repository Git index is outside the writable sandbox surface. Each normal commit was rerun with the authorized Git escalation, hooks enabled, and only explicitly named Phase 11 Plan 03 files staged.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. The Collector read APIs, state transitions, limits, diagnostics, and exports are fully wired; persistence, REST/SSE, and UI remain intentionally owned by later phases.

## Verification

- `PYTHONPATH=src pytest -q tests/unit/test_event_collector.py -x` — 18 passed after Task 2; 20 Collector tests pass in final focused verification.
- `PYTHONPATH=src python -c "import agentguard; from agentguard.events import EventCollector, EventEnvelope; assert agentguard.EventCollector is EventCollector"` — passed.
- `PYTHONPATH=src pytest -q tests/unit/test_event_collector.py tests/unit/test_event_sinks.py tests/unit/test_report.py -x` — 27 passed.
- `PYTHONPATH=src pytest -q tests/unit/test_event_collector.py tests/unit/test_event_contract.py tests/unit/test_event_sinks.py tests/unit/test_report.py -x` — 65 passed.
- `PYTHONPATH=src pytest -q` — 208 passed.
- `git diff --check` — passed.

## Self-Check: PASSED

- Both created files and both modified public export modules exist.
- Task commits `ad0f16e`, `fa899be`, `1f31401`, and `5ce4812` exist in order with no tracked file deletions.
- All task acceptance criteria and plan-level verification commands pass.
- No stub or unregistered threat surface was found in the files changed by this plan.
- The pre-existing untracked `docs/career/` directory remains untouched and unstaged.

## Next Phase Readiness

- Plan 11-04 can inject this Collector into real Runtime and GuardedToolNode paths and verify correlated approval/recovery evidence end to end.
- Phase 12 can build v1 history persistence and REST reads on immutable envelopes and summaries without redefining ordering or run state.
- No blockers remain.

---
*Phase: 11-event-contract-and-collector*
*Completed: 2026-09-06*
