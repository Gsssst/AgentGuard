# Phase 5 Wave 1 Summary

## Completed

- Added the fixed capability vocabulary: `read`, `write`, `external`, and `destructive`.
- Added immutable `Tool.capabilities` metadata with registration-time validation.
- Added fail-closed `PermissionPolicy` with deterministic allow, deny, and approval-required decisions.
- Added structured `PermissionDenied` and typed `ApprovalDecision` contracts.
- Added `RunStatus.WAITING_APPROVAL` and `StopReason.PERMISSION_DENIED` while keeping `RunResult` terminal-only.
- Re-exported permission types from `agentguard` and `agentguard.runtime`.

## Compatibility

Tools registered without `capabilities` retain an empty immutable set, and the existing `ToolExecutor` path is unchanged. Runtime behavior remains unchanged until a later wave explicitly configures a permission policy.

## Verification

```text
PYTHONPATH=src pytest -q tests/unit/test_permissions.py tests/unit/test_tool_execution.py tests/unit/test_domain_models.py
29 passed

PYTHONPATH=src pytest -q
81 passed
```

No Git commit was created; the user manages staging and commits.
