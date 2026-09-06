---
phase: 11-event-contract-and-collector
plan: 04
subsystem: integrations
tags: [python, langgraph, event-collector, approval-resume, observability]

requires:
  - phase: 11-event-contract-and-collector
    plan: 02
    provides: producer-owned stable run, call, and batch correlation
  - phase: 11-event-contract-and-collector
    plan: 03
    provides: strict process-local EventCollector timelines and summaries
provides:
  - correlated safe LangGraph adapter facts across direct work, rejection, approval pause, and resume
  - one logical AIMessage batch boundary pair across direct and pending subsets
  - real StateGraph/MemorySaver observability evidence and paired bilingual learning records
affects: [phase-12-history-api, phase-13-live-streaming, phase-14-console]

tech-stack:
  added: []
  patterns: [adapter-owned correlation projection, framework-event safety seam, original-batch lifecycle ownership]

key-files:
  created:
    - tests/integration/test_langgraph_observability.py
    - .planning/phases/11-event-contract-and-collector/11-LEARNINGS.md
    - .planning/phases/11-event-contract-and-collector/11-LEARNINGS.en.md
  modified:
    - src/agentguard/integrations/langgraph.py

key-decisions:
  - "Create one opaque batch ID and one per-index internal call ID at prepare time, persist them in machine state, and preserve only valid external tool-call IDs as envelope evidence."
  - "Suppress Runtime subset batch lifecycle events so the original AIMessage owns exactly one start/finish pair across approval suspension."
  - "Represent adapter-side rejection and approval outcomes through Runtime.emit_framework_event while keeping all authorization and execution controls inside Runtime."

patterns-established:
  - "Prepared correlation: run_id, batch_id, call_id, external tool_call_id, message placeholder ID, and input index survive approval resume together."
  - "Observable early return: adapter rejections emit allowlisted strict facts without raw arguments, exception messages, digests mismatch details, or approval reasons."

requirements-completed: [OBS-03, OBS-04, COMPAT-01]

duration: 6h 20m elapsed (approximately 24m active; provider pause excluded)
completed: 2026-09-06
---

# Phase 11 Plan 04: LangGraph Observability Integration Summary

**GuardedToolNode now produces one safe correlated Collector timeline across direct execution, early rejection, approval pause, and resume while retaining ordered MessagesState results.**

## Performance

- **Duration:** 6h 20m elapsed (approximately 24m active execution; interrupted by a provider usage-limit pause)
- **Started:** 2026-09-06T07:38:00Z
- **Completed:** 2026-09-06T13:58:28Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added Adapter-owned correlation for every original AIMessage input, preserving true run ID, one shared batch ID, distinct internal call IDs, valid external IDs, and original indexes through approval resume.
- Made malformed calls, duplicate IDs, unknown tools, missing guards, policy denial, approval request/denial/digest mismatch, missing resumed tools, retry, timeout, cancellation, and final outcomes visible through the strict v1 boundary.
- Kept mixed direct/pending execution to one logical batch boundary pair, with direct work executed once and final ToolMessages emitted once in original order.
- Added real public `StateGraph`, `MessagesState`, `MemorySaver`, and `Command(resume=...)` evidence plus an optional-import isolation subprocess test.
- Produced structurally paired Chinese and English learning records covering D-01 through D-21, deliberate failures, security boundaries, compatibility, and deferred scope.

## Task Commits

Each task was committed atomically:

1. **Task 1: Carry logical correlation through every GuardedToolNode branch** — `565e449` (feat)
2. **Task 2: Prove real LangGraph observability and v0.3 compatibility** — `910c251` (test)
3. **Task 3: Record paired Phase 11 learning evidence and run the full release gate** — `4693a80` (docs)

## Files Created/Modified

- `src/agentguard/integrations/langgraph.py` — Original-batch correlation, subset lifecycle suppression, persisted prepared identities, and safe framework event helpers.
- `tests/integration/test_langgraph_observability.py` — Real direct and approval-resume timelines, failure isolation, sentinel safety, and optional-import isolation.
- `.planning/phases/11-event-contract-and-collector/11-LEARNINGS.md` — Chinese failure-oriented Phase 11 evidence.
- `.planning/phases/11-event-contract-and-collector/11-LEARNINGS.en.md` — Structurally paired English evidence.

## Decisions Made

- Used a random opaque batch ID plus UUID5 per-index call IDs derived only from non-secret run/batch/index coordinates; tool arguments, errors, actors, and reasons never contribute to identity.
- Separated the external source `tool_call_id` from the Agent-visible placeholder ID so invalid IDs remain usable for ordered ToolMessages without becoming trusted envelope evidence.
- Emitted one logical `batch_started` before partitioning and delayed `batch_finished` until all original calls are final; Runtime direct/pending subset boundaries remain disabled.
- Reused `Runtime.execute_explicit_batch()` for actual tool work and `Runtime.emit_framework_event()` only for adapter-owned facts, so observability cannot bypass permission, digest, resource-lock, timeout, or retry controls.

## Deviations from Plan

None - plan executed within its intended architecture and scope.

## Issues Encountered

- The first RED run placed a secret sentinel in an ordinary `value` string and correctly exposed that AgentGuard uses structural sensitive-key redaction rather than arbitrary content scanning. The fixture was corrected to use `token`/`password` fields, and both learning records now state this limit explicitly instead of claiming automatic discovery of arbitrary secrets.
- Execution was interrupted by a provider usage-limit pause after Task 1. Work resumed from commit `565e449`; no task was replayed, amended, reset, or lost.
- Git index writes required the already authorized filesystem escalation. Hooks stayed enabled and each commit staged only its explicit plan files.
- `roadmap.update-plan-progress` correctly detected 4 plans and 4 summaries but left the legacy human-readable progress line at 3/4; the handler was rerun and the stale ROADMAP/requirements trace rows were corrected to match the authoritative completed artifacts.

## TDD Gate Compliance

Task 2 was an integration-evidence task whose production behavior had already been committed in Task 1. Its initial RED execution failed on the over-broad ordinary-string secret assumption; after correcting the test to the locked key-based safety contract, the final evidence passed. There is therefore a test commit but no separate GREEN implementation commit for Task 2; no production behavior was added during that evidence-only task.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. JSONL/REST, SSE/external ingestion, and React UI are intentionally deferred capabilities, not unwired Phase 11 placeholders.

## Threat Flags

None. The adapter adds no network endpoint, file-access path, schema migration, authentication path, or external ingestion surface; all HIGH threats T-11-14 through T-11-18 are covered by automated correlation, safety, replay, and failure-isolation evidence.

## Verification

- `PYTHONPATH=src python -m pytest -q tests/unit/test_langgraph_adapter.py tests/unit/test_langgraph_approval.py tests/integration/test_langgraph_approval.py -rs -x` — 27 passed after Task 1.
- `PYTHONPATH=src python -m pytest -q tests/integration/test_langgraph_observability.py tests/integration/test_langgraph_approval.py tests/integration/test_langgraph_optional.py -rs -x` — 12 passed with one third-party deprecation warning.
- `PYTHONPATH=src python -m pytest -q` — 212 passed.
- `PYTHONPATH=src python -c "import agentguard"` — passed.
- `git diff --check` — passed.
- Chinese and English learning records each contain seven matching numbered sections and cover D-01 through D-21.

## Self-Check: PASSED

- All three created artifacts and the modified adapter exist.
- Task commits `565e449`, `910c251`, and `4693a80` exist in order, with no tracked file deletion.
- All task acceptance criteria and plan-level verification commands passed.
- The pre-existing untracked `docs/career/` directory remains untouched and unstaged.

## Next Phase Readiness

- Phase 11 is complete: four plans now provide the v1 contract, Runtime correlation, bounded Collector, and real LangGraph integration evidence.
- Phase 12 can persist only validated envelopes and expose history APIs without redefining correlation or ordering.
- No blockers remain.

---
*Phase: 11-event-contract-and-collector*
*Completed: 2026-09-06*
