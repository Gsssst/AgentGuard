---
phase: 10-fix-langgraph-messagesstate-approval-result-replacement
plan: 02
subsystem: integration-testing
tags: [langgraph, messagesstate, add_messages, interrupt, resume, regression, learning]
requires:
  - phase: 10-fix-langgraph-messagesstate-approval-result-replacement
    provides: "Pending/message separation and consumed approval projection from Plan 10-01"
provides:
  - "Real MessagesState/add_messages mixed-batch approval regression evidence"
  - "Bilingual blocker-closure learning records"
affects: [v0.3-milestone-audit, release-evidence]
tech-stack:
  added: []
  patterns: ["Filter MessagesState's AIMessage when asserting ordered ToolMessage results"]
key-files:
  created:
    - .planning/phases/10-fix-langgraph-messagesstate-approval-result-replacement/10-LEARNINGS.md
    - .planning/phases/10-fix-langgraph-messagesstate-approval-result-replacement/10-LEARNINGS.en.md
  modified:
    - tests/integration/test_langgraph_approval.py
    - tests/unit/test_langgraph_approval.py
requirements-completed: [BATCH-04, APPROVAL-03, APPROVAL-06, COMPAT-04, COMPAT-05]
duration: 12min
completed: 2026-09-04
---

# Phase 10 Plan 02 Summary

**Proved approval result uniqueness with a real `MessagesState + add_messages` graph and documented the B1 fix in paired Chinese/English records.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-04T08:46:16Z
- **Completed:** 2026-09-04T08:58:16Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Extended the real integration state from a plain `TypedDict` to public `MessagesState` while retaining `_agentguard_prepared`.
- Added a mixed-batch pause/resume regression covering direct, approval-required, and unguarded denied calls.
- Verified pause has no approval placeholder and resume has exactly one ordered `ToolMessage` per original call ID.
- Preserved direct-call-once, redaction, digest mismatch, missing-tool, and optional-dependency evidence.
- Added structurally paired Chinese and English learning records with deliberate-fault evidence and bounded compatibility claims.

## Task Commits

Git commits were intentionally not created; per the user's workflow, changes remain in the working tree for the user to stage and commit.

## Files Created/Modified

- `tests/integration/test_langgraph_approval.py` — real reducer regression and MessageState-aware result assertions.
- `tests/unit/test_langgraph_approval.py` — consumed pending-state assertion.
- `10-LEARNINGS.md` / `10-LEARNINGS.en.md` — bilingual B1 reproduction, fix, evidence, and limits.

## Decisions Made

- Treat the AIMessage as existing graph history and assert result uniqueness only across filtered `ToolMessage` values.
- Keep the regression limited to the default public `messages` reducer and verified optional dependency versions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected a syntax typo in the new integration assertion**

- **Found during:** Task 1 (real MessagesState/add_messages regression)
- **Issue:** A malformed closing bracket prevented pytest collection.
- **Fix:** Corrected the assertion to compare the direct invocation list and pass the failure message separately.
- **Files modified:** `tests/integration/test_langgraph_approval.py`
- **Verification:** Targeted suite and full suite both passed.
- **Committed in:** Not committed per user workflow.

**Total deviations:** 1 auto-fixed (Rule 1 bug).
**Impact on plan:** Test-only correction; no scope change.

## Issues Encountered

The existing integration assertions assumed a plain list reducer and attempted to read `tool_call_id` from the AIMessage retained by `MessagesState`. They were updated to filter `ToolMessage` values, which is required by the standard reducer and preserves the intended assertions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

All Phase 10 implementation and regression work is complete. Run the v0.3 milestone audit again to confirm B1 and the three affected requirements are fully satisfied before release decisions.

---
*Phase: 10-fix-langgraph-messagesstate-approval-result-replacement*
*Completed: 2026-09-04*
