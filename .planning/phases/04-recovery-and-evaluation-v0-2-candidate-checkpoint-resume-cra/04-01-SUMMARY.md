---
phase: 04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra
plan: 01
subsystem: checkpoint
tags: [checkpoint, json, atomic-write, validation]
requires: [Phase 3 Runtime and event contracts]
provides: [typed checkpoint model, strict JSON codec, atomic local CheckpointStore]
affects: [04-02 Runtime resume integration]
tech-stack:
  added: [Python standard library json, pathlib, tempfile, os.replace]
  patterns: [explicit typed projection, validate-before-side-effect, same-directory atomic replacement]
key-files:
  created:
    - src/agentguard/checkpoint/model.py
    - src/agentguard/checkpoint/codec.py
    - src/agentguard/checkpoint/store.py
    - src/agentguard/checkpoint/__init__.py
    - tests/unit/test_checkpoint.py
    - tests/unit/test_checkpoint_store.py
  modified:
    - src/agentguard/__init__.py
key-decisions:
  - Use schema_version 1 and explicit JSON fields instead of pickle or __dict__ serialization.
  - Use tempfile + flush + fsync + os.replace so a failed write preserves the previous checkpoint.
  - Reject corrupt, incomplete, unsupported, or non-JSON-compatible values with distinct checkpoint errors.
requirements-completed: [CHECKPOINT-01, CHECKPOINT-02]
duration: "under 1 hour"
completed: 2026-09-01
---

# Phase 04 Plan 01: Checkpoint Foundation Summary

Implemented the schema-versioned checkpoint model, strict domain-object JSON codec, and local atomic file store required for explicit Runtime recovery.

## Verification

- `PYTHONPATH=src pytest -q tests/unit/test_checkpoint.py tests/unit/test_checkpoint_store.py` — 8 passed.
- `PYTHONPATH=src pytest -q` — 61 passed, including all Phase 1–3 tests.
- Replacement-failure test confirms the previous canonical file remains byte-for-byte unchanged and temporary files are cleaned up.
- Corrupt JSON, missing fields, unsupported schema version, invalid lifecycle, and non-JSON ToolResult values are rejected before any executor integration exists.

## Deviations from Plan

**[Rule 1 - Bug] Root package exports missing codec functions** — Found during: checkpoint unit-test collection | Issue: `dumps_checkpoint`/`loads_checkpoint` were not exported from `agentguard` | Fix: re-exported codec functions from `src/agentguard/__init__.py` | Verification: 61 tests pass.

**Total deviations:** 1 auto-fixed. **Impact:** None; public API now matches the plan and tests.

## Self-Check: PASSED

All task acceptance criteria and plan-level verification commands pass. Ready for `04-02` Runtime integration.
