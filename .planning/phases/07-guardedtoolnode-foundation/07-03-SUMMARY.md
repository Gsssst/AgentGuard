---
phase: 07-guardedtoolnode-foundation
plan: 03
subsystem: adapter-evidence
tags: [testing, langgraph, integration, learning-notes, redaction]
requires: [07-02]
provides: [optional StateGraph smoke test, bilingual learning evidence]
affects: [Phase 8, Phase 9]
tech-stack:
  added: []
  patterns: [importorskip optional integration, safe error summaries]
key-files:
  created: [tests/integration/test_langgraph_optional.py, learning/zh-CN/07-langgraph-adapter.md, learning/en/07-langgraph-adapter.md]
  modified: [src/agentguard/integrations/langgraph.py, tests/unit/test_langgraph_adapter.py]
key-decisions:
  - Agent-visible error content is generic by failure kind; detailed exception text stays in AgentGuard evidence.
  - Real integration tests use a minimal public StateGraph and skip clearly when optional dependencies are absent.
requirements-completed: [ADAPTER-05, ADAPTER-06, COMPAT-02, COMPAT-03, COMPAT-04, COMPAT-05]
duration: 0 min
completed: 2026-09-02
---

# Phase 7 Plan 3: Approval Bridge and Compatibility Evidence Summary

Completed deterministic adapter failure coverage, optional real LangGraph StateGraph integration, and Chinese/English learning notes. Added regression checks for sync fallback, configurable message keys, last-message selection, safe exception summaries, and the installed optional dependency path.

## Verification

- `PYTHONPATH=src pytest -q tests/unit/test_langgraph_adapter.py tests/integration/test_langgraph_optional.py` — 8 passed
- `PYTHONPATH=src pytest -q` — 107 passed
- `git diff --check` — passed
- Real `StateGraph` smoke test — passed with `langgraph 0.6.11` / `langchain-core 0.3.86`

## Deviations from Plan

None — plan executed within the Phase 7 boundary. Multi-tool batching and interrupt/resume approval remain deferred to Phases 8 and 9.

## Self-Check: PASSED

Phase 7 implementation is ready for goal verification.
