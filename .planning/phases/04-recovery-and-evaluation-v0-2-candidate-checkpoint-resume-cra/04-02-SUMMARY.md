---
phase: 04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra
plan: 02
subsystem: runtime-recovery
tags: [resume, simulated-crash, events, reliability-report]
requires: [04-01 checkpoint model, codec, and atomic store]
provides: [post-step checkpoint hooks, explicit Runtime.resume, recovery events, recovery metrics]
affects: [04-03 scenario registry and evaluation runner]
tech-stack:
  added: [stdlib asyncio/pathlib integration]
  patterns: [single Runtime execution path, validate-before-side-effect, event sequence evidence]
key-files:
  created:
    - tests/integration/test_recovery_scenarios.py
  modified:
    - src/agentguard/runtime/engine.py
    - src/agentguard/events/model.py
    - src/agentguard/reporting/report.py
    - src/agentguard/__init__.py
    - tests/unit/test_report.py
key-decisions:
  - Add recovery event types without changing existing JSONL event fields.
  - Resume is explicit, preserves run_id, increments resume_attempt, and marks duplicate_possible.
  - Event sequence is carried in event data and checkpoint position reserves the checkpoint-written event.
requirements-completed: [RECOVERY-01, RECOVERY-02, RECOVERY-03]
duration: "under 1 hour"
completed: 2026-09-01
---

# Phase 04 Plan 02: Runtime Recovery Summary

Integrated checkpoint persistence into the existing sequential Runtime loop, added deterministic crash injection and explicit resume, and extended reliability reports with recovery evidence.

## Verification

- `PYTHONPATH=src pytest -q tests/integration/test_recovery_scenarios.py` — 2 passed.
- `PYTHONPATH=src pytest -q` — 64 passed.
- Crash scenario executes a Tool, raises `SimulatedCrash` before the next checkpoint, preserves the previous checkpoint, then resumes with the same run_id and a possible duplicate execution.
- Corrupt checkpoint scenario rejects before any Tool side-effect counter increments.
- Existing event sink and Phase 1–3 integration tests remain green.

## Deviations from Plan

**[Rule 1 - Bug] Event-position reservation** — Found during: recovery integration review | Issue: saving the checkpoint before emitting `checkpoint_written` would reuse that event's sequence on resume | Fix: active checkpoint event_position reserves the next checkpoint event sequence | Verification: full 64-test suite passes.

**Total deviations:** 1 auto-fixed. **Impact:** Recovery event ordering remains monotonic and auditable.

## Self-Check: PASSED

All acceptance criteria and plan-level verification commands pass. Ready for `04-03` evaluation scenarios.
