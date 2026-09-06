---
phase: 11-event-contract-and-collector
plan: 01
subsystem: events
tags: [python, event-contract, validation, redaction, telemetry]

requires:
  - phase: 05-permissions-and-audit
    provides: capability metadata, approval evidence, and legacy recursive redaction semantics
  - phase: 10-fix-langgraph-messagesstate-approval-result-replacement
    provides: stable RuntimeEvent vocabulary and tool approval lifecycle evidence
provides:
  - bounded recursive safe-preview projection with mandatory redaction
  - strict agentguard.event.v1 envelope and typed validation categories
  - exhaustive normalization for all 23 legacy Runtime event types
affects: [11-02-runtime-correlation, 11-03-event-collector, 11-04-langgraph-observability, phase-12-history-api]

tech-stack:
  added: []
  patterns: [bounded structural projection, declarative payload allowlists, legacy-to-v1 normalization]

key-files:
  created:
    - src/agentguard/_safety.py
    - src/agentguard/events/contract.py
    - src/agentguard/events/normalize.py
    - tests/unit/test_event_safety.py
    - tests/unit/test_event_contract.py
  modified:
    - src/agentguard/runtime/permission.py

key-decisions:
  - "Keep RuntimeEvent as the v0.3-compatible source fact and add a strict v1 normalization boundary beside it."
  - "Represent every argument/result preview as an explicit value-plus-truncated object with fixed non-disableable limits."
  - "Reject undeclared source fields and replace raw failures, paths, signatures, and approval reasons with fixed safe summaries."

patterns-established:
  - "Safety boundary: traverse only JSON primitives, mappings, lists, and tuples under depth, width, string, and node budgets."
  - "Contract boundary: one closed payload specification and deterministic event status for every EventType."
  - "Correlation boundary: internal call_id is required for tool lifecycles while run-level and batch-level nullability is validated explicitly."

requirements-completed: [OBS-03, OBS-04, COMPAT-01]

duration: 12 min
completed: 2026-09-06
---

# Phase 11 Plan 01: Event Contract and Safety Boundary Summary

**A strict `agentguard.event.v1` boundary now converts all 23 legacy Runtime events into bounded, redacted, immutable telemetry facts without changing the v0.3 source event API.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-06T01:53:41Z
- **Completed:** 2026-09-06T02:05:40Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added one standard-library safety projector that limits recursion depth, collection width, string length, and total visited nodes while safely handling cycles, bytes, hostile objects, and non-finite floats.
- Defined the exact fixed v1 envelope, UTC normalization, typed validation failures, correlation rules, event/run status vocabularies, and event-specific payload allowlists.
- Normalized every existing `EventType` without free-form passthrough; only legacy source sequence enters `extensions`, while raw exception text, stack data, checkpoint paths, loop signatures, and approval reasons are discarded.
- Preserved the public `RuntimeEvent`, `EventSink`, `redact()`, `redact_arguments()`, and permission digest behavior; the complete suite passes without Console or LangGraph imports in the new core modules.

## Task Commits

Each TDD task was committed as a RED test followed by its GREEN implementation:

1. **Task 1 RED: adversarial event safety boundary** — `a80ccee` (test)
2. **Task 1 GREEN: bounded telemetry safety projector** — `85a37e9` (feat)
3. **Task 2 RED: strict v1 event contract matrix** — `e0f1571` (test)
4. **Task 2 GREEN: exhaustive event normalization** — `971d77c` (feat)

## Files Created/Modified

- `src/agentguard/_safety.py` — Bounded structural projection, fixed placeholders, recursive marker redaction, and copy-safe `SafePreview`.
- `src/agentguard/runtime/permission.py` — Legacy redaction wrappers now delegate to the shared safety boundary; digest logic is unchanged.
- `src/agentguard/events/contract.py` — Frozen v1 fact/envelope models, status and validation enums, payload registry, UTC/JSON validation, and exact serialization.
- `src/agentguard/events/normalize.py` — Explicit source-field projection and fixed safe summaries for all legacy events.
- `tests/unit/test_event_safety.py` — Deliberate failure cases for secrets, resource bounds, cycles, unsupported values, hostile coercion, and mutation isolation.
- `tests/unit/test_event_contract.py` — Complete event matrix plus schema, timestamp, payload, correlation, safety, and compatibility failures.

## Decisions Made

- Kept the legacy event model intact because reports, sinks, and existing users still consume its free-form source shape; the strict envelope is a second public boundary.
- Used immutable wrappers and defensive thawing for public snapshots so later Collector/API layers cannot retain references to caller-owned payloads.
- Reserved top-level sequence for the future Collector; source `data.sequence` is diagnostic evidence only at `extensions.source_sequence`.
- Applied fixed failure summaries rather than attempting to sanitize attacker-controlled exception strings after serialization.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The repository's Git index is outside the writable sandbox surface. Normal commits were rerun with the already authorized Git escalation; hooks remained enabled and no verification was bypassed.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. Empty containers found by the scan are runtime accumulators or test fixtures, not unwired placeholder behavior.

## Verification

- `PYTHONPATH=src pytest -q tests/unit/test_event_safety.py tests/unit/test_event_contract.py tests/unit/test_redaction_and_digest.py tests/unit/test_event_sinks.py -x` — 49 passed.
- `PYTHONPATH=src python -c "import agentguard"` — passed.
- `PYTHONPATH=src pytest -q` — 180 passed.
- `git diff --check` — passed.
- All four Task commits exist and no tracked files were deleted.

## Self-Check: PASSED

- All five created files and the modified permission module exist.
- RED and GREEN commits exist for both TDD tasks.
- Every plan-level verification and acceptance criterion passed.
- Only the pre-existing untracked `docs/career/` remains outside the plan and was neither modified nor staged.

## Next Phase Readiness

- Plan 11-02 can now import `EventCorrelation` and feed Runtime emissions through `normalize_runtime_event()` while preserving existing execution entry points.
- Plan 11-03 can construct sequenced `EventEnvelope` values from immutable `NormalizedEvent` facts.
- No blockers remain.

---
*Phase: 11-event-contract-and-collector*
*Completed: 2026-09-06*
