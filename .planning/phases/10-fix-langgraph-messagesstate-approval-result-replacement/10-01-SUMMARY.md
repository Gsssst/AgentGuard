---
phase: 10-fix-langgraph-messagesstate-approval-result-replacement
plan: 01
subsystem: langgraph-adapter
tags: [langgraph, messagesstate, add_messages, approval, toolmessage]
requires:
  - phase: 09-approval-bridge-and-compatibility-evidence
    provides: "Two-node prepare/approval lifecycle, digest-bound approval DTOs, and ordered result merge"
provides:
  - "Pending approval projections that keep machine state separate from user-visible messages"
  - "Consumed approval context and compatibility smoke coverage"
affects: [phase-10-integration-regression, v0.3-milestone-audit]
tech-stack:
  added: []
  patterns: ["Omit messages from pending node updates; emit final ToolMessages once after resume"]
key-files:
  created: []
  modified:
    - src/agentguard/integrations/langgraph.py
    - tests/unit/test_langgraph_adapter.py
key-decisions:
  - "Pending prepare returns only _agentguard_prepared; it never emits ApprovalRequired placeholders."
  - "Approval marks pending as consumed while preserving the legacy __call__ wrapper."
requirements-completed: [BATCH-04, APPROVAL-03, APPROVAL-06]
duration: 8min
completed: 2026-09-04
---

# Phase 10 Plan 01 Summary

**Separated pending approval state from the LangGraph message projection and locked the compatibility behavior with deterministic tests.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-04T08:38:00Z
- **Completed:** 2026-09-04T08:46:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Changed `GuardedToolNode.prepare()` so pending batches return `_agentguard_prepared` without a `messages` update or approval placeholder.
- Kept direct results, pending calls, original IDs, indexes, and digest-bound data in machine state for `approval()`.
- Marked approval context consumed after final ordered results and preserved ordinary `__call__()` behavior.
- Added smoke tests for pending projection, no-pending prepare, legacy calls, and consumed state.

## Task Commits

Git commits were intentionally not created; per the user's workflow, changes remain in the working tree for the user to stage and commit.

## Files Created/Modified

- `src/agentguard/integrations/langgraph.py` — separates pending approval state from visible messages and clears pending after approval.
- `tests/unit/test_langgraph_adapter.py` — verifies projection and compatibility contracts.

## Decisions Made

- Omit the `messages` key while approval is pending so `add_messages` cannot append a placeholder.
- Keep `_agentguard_prepared` as the single internal state key and retain the existing `__call__()` wrapper.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for the real `MessagesState + add_messages` integration regression in Plan 10-02.

---
*Phase: 10-fix-langgraph-messagesstate-approval-result-replacement*
*Completed: 2026-09-04*
