---
phase: 09-approval-bridge-and-compatibility-evidence
plan: 01
subsystem: integrations
tags: [langgraph, interrupt, approval, digest, permissions, runtime]
requires:
  - phase: 08-multi-tool-batch-execution
    provides: ordered, failure-isolated explicit batch execution
  - phase: 05-permission-control-and-approval-boundaries
    provides: capability policy, redaction, approval decisions and digests
provides:
  - typed, redacted and versioned approval interrupt projections
  - fail-closed per-call resume normalization
  - replay-safe preparation and approval adapter entry points
  - Runtime approval-context revalidation and audit events
affects: [phase-09-plan-02, langgraph-adapter, approval]
tech-stack:
  added: []
  patterns: [single interrupt payload, per-call digest binding, preparation/approval split]
key-files:
  created:
    - src/agentguard/integrations/approval.py
    - tests/unit/test_langgraph_approval.py
  modified:
    - src/agentguard/integrations/langgraph.py
    - src/agentguard/integrations/__init__.py
    - src/agentguard/runtime/engine.py
key-decisions:
  - "Approval projection hashes canonical unredacted arguments but only exposes recursive redacted arguments."
  - "Preparation and approval are separate public adapter entry points so direct side effects can be persisted by LangGraph before interrupt replay."
  - "Runtime receives explicit ApprovalDecision values and original input step indices, then rechecks policy and digest before acquiring locks."
patterns-established:
  - "Missing, malformed, denied, and digest-mismatched resume entries become per-call denials; valid sibling decisions continue."
  - "Approved adapter-owned tools always execute through Runtime.execute_explicit_batch with ordered results."
requirements-completed: [APPROVAL-01, APPROVAL-02, APPROVAL-03, APPROVAL-04, APPROVAL-05, APPROVAL-06]
metrics:
  duration: "~35 min"
  completed: "2026-09-04"
---

# Phase 9 Plan 1: Approval Bridge Summary

**Versioned LangGraph approval projections with fail-closed resume validation and Runtime-governed replay-safe tool execution.**

## Accomplishments

- Added frozen `ApprovalItem`, `ApprovalBatch`, and `NormalizedApproval` contracts plus deterministic batch IDs and recursive redaction.
- Added `GuardedToolNode.prepare()` and `GuardedToolNode.approval()`; mixed batches execute directly-allowed calls first, interrupt once for pending calls, and merge complete ordered `ToolMessage` outputs.
- Extended Runtime explicit execution with approval context, original step-index propagation, policy/digest revalidation, and approval audit events.
- Added deterministic tests covering nested secret masking, stable digests, missing/unknown/mismatched decisions, isolated failures, partial approval, and one-interrupt behavior.

## Verification

- `PYTHONPATH=src pytest -q tests/unit/test_langgraph_approval.py tests/unit/test_langgraph_adapter.py -x` — **17 passed**.
- `PYTHONPATH=src pytest -q -x` — **124 passed**.
- `git diff --check` — **passed**.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved original input indices through approved subset execution**

- **Found during:** Task 2
- **Issue:** The approved subset is compacted before Runtime execution, which would calculate approval digests against subset positions rather than original tool-call indices.
- **Fix:** Added the optional `step_indices` mapping to `Runtime.execute_explicit_batch()` and supplied original indices from the adapter.
- **Files modified:** `src/agentguard/runtime/engine.py`, `src/agentguard/integrations/langgraph.py`
- **Verification:** Approval digest and mixed-batch tests pass.
- **Committed in:** User-managed working tree (no commit performed by this agent).

**Total deviations:** 1 auto-fixed (Rule 1: 1).
**Impact on plan:** Required for correct digest binding; no scope expansion.

## Issues Encountered

- The repository intentionally contains unrelated uncommitted Phase 8 and `docs/career/` changes. They were preserved and not staged or modified.

## User Setup Required

None - no new external service or dependency configuration required.

## Known Limits

- The combined `GuardedToolNode.__call__` convenience path still has LangGraph's normal at-least-once replay semantics; replay-sensitive graphs should compose `prepare` and `approval` as separate nodes.
- Approval payload state currently carries original arguments for digest recomputation; the human-facing interrupt payload remains recursively redacted. Durable encryption/remote approval storage is out of scope.

## Next Phase Readiness

Ready for Plan 09-02 compatibility evidence and real `StateGraph`/`MemorySaver` interrupt-resume tests. No Git commit was created per the user's standing instruction.

## Self-Check: PASSED

- Created files exist on disk.
- Full test suite passed (124 tests).
- No STATE.md or ROADMAP.md changes were made by this plan executor.

---
*Phase: 09-approval-bridge-and-compatibility-evidence*
*Plan: 01*
