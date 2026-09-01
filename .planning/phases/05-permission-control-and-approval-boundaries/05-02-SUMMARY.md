# Phase 5 Wave 2 Summary

- Extended checkpoints with pending Action, capability labels, action digest, and typed approval metadata.
- Added strict waiting-state validation and backward-compatible decoding for old checkpoints.
- Added `RunPause` for the non-terminal `WAITING_APPROVAL` projection.
- Inserted the permission gate after `ACTION_PROPOSED` and before loop/tool execution.
- Implemented explicit approval resume with digest validation and original pending Action execution.
- Added approval lifecycle events and ensured direct denial/approval pause do not invoke Tools before authorization.

Verification: `PYTHONPATH=src pytest -q` -> 85 passed. Manual approval pause/resume verified zero pre-approval side effects and one post-approval Tool execution.
