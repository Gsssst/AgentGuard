---
phase: 07-guardedtoolnode-foundation
status: passed
verified: 2026-09-02
---

# Phase 7 Verification

## Goal

Integrate AgentGuard's guarded tool execution boundaries into LangGraph through an optional `GuardedToolNode`, while leaving graph state and checkpoint ownership with LangGraph.

## Automated checks

- `PYTHONPATH=src pytest -q` — **107 passed**.
- `PYTHONPATH=src pytest -q tests/unit/test_runtime_explicit_tool.py tests/unit/test_langgraph_adapter.py tests/integration/test_langgraph_optional.py` — **12 passed**.
- `PYTHONPATH=src python -S -c 'import agentguard'` — **passed** without optional dependencies.
- `PYTHONPATH=src python -S -c 'import agentguard.integrations.langgraph'` — **passed expected guard** with actionable `agentguard[langgraph]` installation message.
- `git diff --check` — **passed**.
- Real LangGraph `StateGraph` smoke test with `langgraph 0.6.11` and `langchain-core 0.3.86` — **passed**.

## Requirement evidence

- ADAPTER-01..06 — optional extra, `GuardedToolNode`, `ToolGuard`, fail-closed configuration, Runtime explicit-tool seam, and stable `ToolMessage` IDs are implemented and tested.
- COMPAT-01..03, COMPAT-05 — lazy import boundary, deterministic fake tests, real optional smoke test, and bilingual learning records are present.
- COMPAT-04 — foundation failure tests cover success, denial, timeout/retry, lock timeout, and unknown/malformed calls. Approval and digest-mismatch tests remain assigned to Phase 9 where that behavior is implemented.

## Known limits

This phase intentionally handles one tool call only. Multi-call batch concurrency belongs to Phase 8; interrupt/resume approval and digest-bound resume validation belong to Phase 9.

## Verdict

**PASSED** — Phase 7 goal achieved within its approved scope.
