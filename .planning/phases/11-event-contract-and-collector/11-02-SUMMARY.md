---
phase: 11-event-contract-and-collector
plan: 02
subsystem: runtime
tags: [python, uuid5, event-correlation, checkpoint-recovery, batch-concurrency]

requires:
  - phase: 11-event-contract-and-collector
    plan: 01
    provides: strict agentguard.event.v1 normalization and EventCorrelation validation
  - phase: 06-resource-aware-concurrency
    provides: ordered failure-isolated batch execution and process-local resource locks
  - phase: 09-approval-bridge-and-compatibility-evidence
    provides: digest-bound approval and checkpoint resume semantics
provides:
  - producer-owned stable call_id propagation across tool lifecycle, retries, approvals, and recovery
  - separate real run_id and batch_id identities for registry and explicit batch execution
  - validated framework-event seam and per-index explicit-batch correlation contexts
affects: [11-03-event-collector, 11-04-langgraph-observability, phase-12-history-api]

tech-stack:
  added: []
  patterns: [namespaced deterministic UUID5, immutable event correlation closure, strict pre-sink framework validation]

key-files:
  created:
    - tests/integration/test_event_correlation.py
  modified:
    - src/agentguard/runtime/engine.py

key-decisions:
  - "Derive sequential call_id values from a fixed UUID5 namespace plus only the non-secret run_id and logical step so crash replay and approval resume recreate the same identity without checkpoint schema changes."
  - "Treat batch_id as an independent correlation field and generate/use a real run_id for every batch instead of placing batch_id in RuntimeEvent.run_id."
  - "Validate framework facts through the strict v1 normalizer before sequence advancement or sink emission, and reject nested raw exception objects at that public seam."

patterns-established:
  - "Correlation closure: action, permission, approval, lock, attempt, retry, and outcome emitters reuse one frozen EventCorrelation."
  - "Subset execution: explicit batches accept per-index contexts and can suppress only batch boundary events while retaining member lifecycle evidence."

requirements-completed: [OBS-03, OBS-04]

duration: 5h 10m elapsed (approximately 16m active; provider pause excluded)
completed: 2026-09-06
---

# Phase 11 Plan 02: Runtime Event Correlation Summary

**Runtime events now preserve one privacy-safe logical call identity through retries, approvals, checkpoint replay, and concurrent batches while keeping real run and batch identities separate.**

## Performance

- **Duration:** 5h 10m elapsed (approximately 16m active execution; interrupted by a provider usage-limit pause)
- **Started:** 2026-09-06T02:11:02Z
- **Completed:** 2026-09-06T07:21:32Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added one correlation-aware Runtime emission path that owns source sequence, attaches immutable call/tool/batch identity, and leaves `RuntimeEvent.to_dict()` backward compatible.
- Derived sequential `call_id` values deterministically from non-secret `run_id + step` coordinates so automatic retry, approval resume, and crash replay retain the same logical identity without changing checkpoint schema v1.
- Corrected both batch APIs to emit a true logical `run_id`, a separate shared `batch_id`, and a unique member `call_id` while preserving ordered results, resource-lock behavior, and isolated failures/cancellations.
- Extended explicit execution with optional keyword-only correlation inputs, per-index batch contexts, and `emit_batch_lifecycle=False` for future LangGraph subset execution.
- Added a strict `emit_framework_event()` seam that validates facts before sink emission and rejects raw exception objects without formatting or exposing their contents.
- Added deterministic fault coverage for transient retry, timeout, permission denial, approval grant/denial and pause/resume, zero-deadline lock timeout, checkpoint replay, cancellation, isolated batch failure, legacy calls, and supplied external correlation.

## Task Commits

1. **Task 1: Propagate stable call and batch identities through all Runtime emitters** — `3b18698` (feat)
2. **Task 2 RED: Add deterministic correlation and safety fault scenarios** — `22a39a4` (test)
3. **Task 2 GREEN: Reject raw framework exception objects before emission** — `3c88c97` (fix)

## Files Created/Modified

- `src/agentguard/runtime/engine.py` — Correlation construction, stable UUID5 IDs, real run/batch separation, correlation-aware emitters, explicit subset controls, and validated framework events.
- `tests/integration/test_event_correlation.py` — Lifecycle grouping and deliberate failure evidence across retry, permission, approval, timeout, locks, recovery, batches, and framework validation.

## Decisions Made

- Kept `ToolExecutor` unchanged and closed one immutable `EventCorrelation` over its attempt/retry callback, preserving the established timeout and retry boundary.
- Used deterministic UUID5 only for sequential/replayed logical calls and batch coordinates; arguments, tool results, exceptions, actors, and approval reasons never contribute to identifiers.
- Preserved external `tool_call_id` only as nullable source evidence. Internal `call_id` remains authoritative even when external identifiers are missing or duplicated.
- Kept checkpoint schema version 1 unchanged because `run_id + step` is already persisted and sufficient to reproduce sequential logical call identity.
- Changed an explicit policy approval requirement without a supplied decision to emit `approval_requested`; explicit grant/denial events always carry a valid expected digest and actor for strict normalization.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced stale Runtime test paths in verification**
- **Found during:** Task 1 verification and Task 2 read-first gate
- **Issue:** The plan referenced `tests/unit/test_runtime.py` and `tests/unit/test_runtime_approval.py`, but neither file exists in the repository.
- **Fix:** Used the current equivalents `tests/integration/test_runtime_loop.py`, `tests/unit/test_runtime_explicit_tool.py`, and the existing approval/recovery suites while retaining every intended verification category.
- **Files modified:** None
- **Verification:** Focused Runtime/correlation command passed 31 tests; the full suite passed 188 tests.
- **Committed in:** No source change required.

---

**Total deviations:** 1 auto-fixed (1 blocking verification-path correction).
**Impact on plan:** No scope expansion or runtime behavior compromise; verification used the repository's actual current test structure.

## Issues Encountered

- The first execution attempt was interrupted by a provider usage-limit pause. Work resumed from the intact uncommitted Runtime diff without reset, checkout, or loss of user changes.
- Git index writes require elevated filesystem permission in this environment. Normal hooks remained enabled and every commit staged only the explicitly named plan file.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. All correlation paths used by this plan are wired to Runtime emitters and covered by executable fault scenarios.

## Verification

- `PYTHONPATH=src python -m pytest -q tests/integration/test_event_correlation.py tests/integration/test_recovery_scenarios.py tests/integration/test_batch_concurrency.py tests/integration/test_runtime_loop.py tests/unit/test_runtime_explicit_tool.py -x` — 31 passed.
- `PYTHONPATH=src python -m pytest -q` — 188 passed.
- `PYTHONPATH=src python -c "import agentguard"` — passed.
- `git diff --check` — passed.
- No tracked files were deleted; `docs/career/` remained untouched and untracked.

## Self-Check: PASSED

- The created integration test and modified Runtime module exist.
- Task commits `3b18698`, `22a39a4`, and `3c88c97` exist in order.
- The RED failure reproduced raw framework exception acceptance; the GREEN fix rejects it before sequence advancement and sink emission.
- All task acceptance criteria and plan-level verification categories pass.

## Next Phase Readiness

- Plan 11-03 can consume normalizable Runtime events with trustworthy per-call, per-batch, and per-run identity.
- Plan 11-04 can generate adapter-owned contexts, pass them into `execute_explicit_batch()`, suppress subset boundaries, and use `emit_framework_event()` for early rejection/approval facts.
- No blockers remain.

---
*Phase: 11-event-contract-and-collector*
*Completed: 2026-09-06*
