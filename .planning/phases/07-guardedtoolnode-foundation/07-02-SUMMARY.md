---
phase: 07-guardedtoolnode-foundation
plan: 02
subsystem: langgraph-adapter
tags: [langgraph, langchain-core, guarded-tool-node, optional-dependency]
requires: [07-01]
provides: [GuardedToolNode, ToolGuard, langgraph-extra]
affects: [Phase 8 multi-tool batch, Phase 9 approval bridge]
tech-stack:
  added: [langgraph 0.6.11, langchain-core 0.3.86]
  patterns: [lazy optional import, adapter-owned registry, structured ToolMessage]
key-files:
  created: [src/agentguard/integrations/__init__.py, src/agentguard/integrations/langgraph.py, tests/unit/test_langgraph_adapter.py]
  modified: [pyproject.toml]
key-decisions:
  - GuardedToolNode reads a configurable messages key and returns a messages state update.
  - Unconfigured tools fail closed before invocation.
  - Adapter tools remain separate from the injected Runtime registry.
requirements-completed: [ADAPTER-01, ADAPTER-02, ADAPTER-03, ADAPTER-04, COMPAT-01]
duration: 0 min
completed: 2026-09-02
---

# Phase 7 Plan 2: GuardedToolNode Foundation Summary

Added the optional LangGraph/LangChain Core dependency extra and implemented `GuardedToolNode` with immutable `ToolGuard` metadata. The node supports configurable message keys, last tool-calling AI message selection, async-first LangChain invocation, sync fallback, safe structured failures, stable JSON content, and original tool-call IDs.

## Verification

- `PYTHONPATH=src pytest -q tests/unit/test_langgraph_adapter.py` — 5 passed
- Core `import agentguard` succeeds without adapter imports
- Installed dependency versions verified: `langgraph 0.6.11`, `langchain-core 0.3.86`

## Deviations from Plan

- Added duck-typed fake AI message support for deterministic tests while retaining real LangChain `AIMessage` support.
- Added `ToolGuard.approval_required` metadata field for Phase 9 compatibility; no approval interrupt behavior is implemented in this phase.

## Self-Check: PASSED

Ready for Plan 07-03.
