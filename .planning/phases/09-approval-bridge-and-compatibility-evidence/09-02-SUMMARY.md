---
phase: 09-approval-bridge-and-compatibility-evidence
plan: 02
subsystem: testing
tags: [langgraph, langchain-core, interrupt, resume, compatibility, approvals]

# Dependency graph
requires:
  - phase: 09-approval-bridge-and-compatibility-evidence
    provides: GuardedToolNode approval bridge, redacted payloads, digest validation, explicit batch execution
provides:
  - deterministic approval and fault-matrix coverage
  - real StateGraph/MemorySaver interrupt-resume compatibility evidence
  - bounded optional dependency versions and explicit skip behavior
affects: [09-03-learning-records, release-evidence]

# Tech tracking
tech-stack:
  added: []
  patterns: [two-node prepare/approval integration graph, importorskip with actionable extra hint, exact verified optional pins]

key-files:
  created:
    - tests/integration/test_langgraph_approval.py
    - tests/integration/__init__.py
    - tests/unit/__init__.py
  modified:
    - tests/unit/test_langgraph_approval.py
    - tests/unit/test_langgraph_adapter.py
    - tests/integration/test_langgraph_optional.py
    - pyproject.toml

key-decisions:
  - "Pin the optional LangGraph stack to the locally verified langgraph 0.6.11 and langchain-core 0.3.86 versions for this release evidence."
  - "Use a separate prepare and approval node in real graphs so direct calls are not replayed when the approval node resumes."
  - "When optional dependencies are unavailable, skip only adapter-specific tests with an actionable agentguard[langgraph] message while core tests remain runnable."

patterns-established:
  - "Real compatibility tests use only public StateGraph, START/END, MemorySaver, Command(resume=...), and configurable.thread_id APIs."
  - "Every approval fault is asserted as an ordered ToolMessage tied to its original tool_call_id."

requirements-completed: [COMPAT-03, COMPAT-04]

# Metrics
duration: 35min
completed: 2026-09-04
---

# Phase 9 Plan 2: Compatibility and Fault Evidence Summary

**Deterministic approval fault matrix plus real LangGraph 0.6.11 interrupt/resume evidence with explicit optional-dependency behavior**

## Performance

- **Duration:** 35 min
- **Started:** 2026-09-04T00:35:00Z
- **Completed:** 2026-09-04T01:10:32Z
- **Tasks:** 2
- **Files modified:** 8 (including two test package markers)

## Accomplishments

- Added deterministic tests for approved, rejected, missing, digest-mismatched, argument-tampered, and resume-time missing-tool calls; each result preserves the original order and `tool_call_id`.
- Added nested secret redaction assertions and approved timeout, retry exhaustion, resource-lock conflict, and post-approval failure coverage with independent sibling execution.
- Added real compiled `StateGraph` tests using `MemorySaver`, the same `configurable.thread_id`, and public `Command(resume=...)`; verified partial approval and direct-call non-replay across resume.
- Recorded and bounded the verified optional stack to `langgraph==0.6.11` and `langchain-core==0.3.86`.
- Verified optional tests execute when installed and skip clearly when blocked, while the core unit suite remains runnable without the optional stack.

## Verification Evidence

- Local combined adapter/approval/integration tests: **26 passed**.
- Full source-tree suite with `PYTHONPATH=src`: **132 passed**.
- Extra environment (`venv --system-site-packages`, editable install with `--no-build-isolation`): versions **langgraph 0.6.11**, **langchain-core 0.3.86**; real approval and optional tests **6 passed**.
- Core-only simulation with optional imports blocked: **91 passed, 12 skipped**; integration module reported `install agentguard[langgraph] for LangGraph approval integration tests`.
- `git diff --check`: passed.

The first isolated install attempt could not download the build-isolation requirement `setuptools>=68` because this sandbox has no registry access. Verification therefore used the locally available build backend with `--no-build-isolation` and a system-site-packages venv; this environment limitation is recorded for the bilingual evidence document and is not a package-name failure.

## Files Created/Modified

- `tests/integration/test_langgraph_approval.py` - Public StateGraph/checkpointer/thread resume tests, redaction, partial approval, digest mismatch, and missing-tool evidence.
- `tests/integration/test_langgraph_optional.py` - Public API availability and exact locally verified version assertions.
- `tests/unit/test_langgraph_approval.py` - Deterministic approval/fault matrix, tamper isolation, and lock/retry/timeout assertions.
- `tests/unit/test_langgraph_adapter.py` - Actionable optional dependency skip wording.
- `tests/unit/__init__.py`, `tests/integration/__init__.py` - Avoid duplicate pytest module names for unit/integration approval modules.
- `pyproject.toml` - Bounded `langgraph` and `langchain-core` optional extra pins.

## Decisions Made

- Exact optional pins are used because only the locally verified public API versions are promised in this first compatibility evidence.
- Real approval graphs separate direct preparation from the interrupting approval node, matching LangGraph replay semantics and avoiding duplicate direct side effects in the tested composition.
- Optional tests use narrow `importorskip` guards with an actionable install hint; they do not silently skip after successful imports.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Blocking test collection] Resolved duplicate pytest module names**
- **Found during:** Task 1
- **Issue:** Unit and integration files intentionally share the approval test basename, causing pytest import-file-mismatch collection errors in the repository's non-package test layout.
- **Fix:** Added minimal `tests/unit/__init__.py` and `tests/integration/__init__.py` package markers.
- **Files modified:** `tests/unit/__init__.py`, `tests/integration/__init__.py`
- **Verification:** Combined 26-test command passes.

**2. [Rule 2 - Missing critical behavior] Made approval unit tests skip cleanly without optional dependencies**
- **Found during:** Task 2
- **Issue:** The approval unit module imported the optional adapter at collection time, preventing the core suite from running in a no-extra environment.
- **Fix:** Wrapped the adapter import with `pytest.importorskip(..., exc_type=ImportError)` and standardized actionable skip wording in adapter tests.
- **Files modified:** `tests/unit/test_langgraph_approval.py`, `tests/unit/test_langgraph_adapter.py`
- **Verification:** Optional-import-blocked core suite passes with 91 passed and 12 explicit skips.

**Total deviations:** 2 auto-fixed (Rule 1: 1, Rule 2: 1)
**Impact on plan:** Both changes preserve the planned test scope and are required for reliable collection and optional-dependency semantics.

## Issues Encountered

- A fully isolated clean install could not download build isolation dependencies because outbound registry access is unavailable in this environment. The fallback local verification used `--no-build-isolation` and existing system packages; no new package was introduced.
- Existing unrelated Phase 8 work and `docs/career/` were preserved and not modified.

## User Setup Required

None - no external service configuration is required. A fresh environment with network access can reproduce the canonical `pip install -e '.[langgraph]'` command; this sandbox used the fallback described above.

## Next Phase Readiness

Plan 09-02 is complete. Plan 09-03 can now record the exact commands, observed versions, explicit skip output, deliberate failures, fixes, and known limits in the paired Chinese and English learning notes.

## Self-Check: PASSED

- Created files exist on disk.
- Real integration tests pass with the verified optional stack.
- Optional-import-blocked suite reports the actionable `agentguard[langgraph]` skip.
- No STATE.md or ROADMAP.md changes were made by this plan executor.

---
*Phase: 09-approval-bridge-and-compatibility-evidence*
*Completed: 2026-09-04*
