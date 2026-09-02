---
phase: 07-guardedtoolnode-foundation
plan: 01
subsystem: runtime-adapter-seam
tags: [runtime, explicit-tool, permissions, locks, retries]
requires: [Phase 6 resource locks and batch concurrency]
provides: [Runtime.execute_explicit_tool, ToolExecutor.execute_explicit]
affects: [LangGraph adapter]
tech-stack:
  added: []
  patterns: [adapter-owned tool execution through Runtime controls]
key-files:
  created: [tests/unit/test_runtime_explicit_tool.py]
  modified: [src/agentguard/runtime/engine.py, src/agentguard/runtime/tool.py]
key-decisions:
  - Explicit adapter Tools are never inserted into the Runtime registry.
  - Runtime remains the owner of permission, lock, timeout, retry, and event boundaries.
requirements-completed: [ADAPTER-05, ADAPTER-06]
duration: 0 min
completed: 2026-09-02
---

# Phase 7 Plan 1: Runtime Adapter Seam Summary

Added `Runtime.execute_explicit_tool()` and `ToolExecutor.execute_explicit()` so framework adapters can keep their own Tool collection while reusing AgentGuard reliability controls. Added deterministic tests for success, permission denial, bounded retries, and lock timeout without registry mutation.

## Verification

- `PYTHONPATH=src pytest -q tests/unit/test_runtime_explicit_tool.py` — 4 passed
- Full suite pending after remaining Phase 7 plans
- `git diff --check` pending final phase verification

## Deviations from Plan

None — plan executed as written.

## Self-Check: PASSED

Ready for Plan 07-02.
