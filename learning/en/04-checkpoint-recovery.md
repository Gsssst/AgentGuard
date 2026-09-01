# Checkpoint and Recovery

## Problem

A process can crash after a Tool has completed but before the next checkpoint is persisted. The Runtime must resume from the last confirmed state while honestly exposing that the current Action may execute again.

## First-version design

- A checkpoint stores only the minimum state needed to choose the next Action: `run_id`, `RunState`, `max_steps`, event position, resume attempt, and lifecycle.
- Persist after each complete step: record the ToolResult, increment `step`, then atomically replace the JSON file using a temporary file, `flush`, `fsync`, and `os.replace`.
- Recovery is explicit through `Runtime.resume(path, router)`; normal `run()` never scans stale files.
- Validate JSON syntax, schema version, required fields, and state invariants before recovery. Corrupt or incompatible data is rejected before any Tool executes.
- The first version is at-least-once. An Action in the crash window may be replayed; events keep the same `run_id`, increment `resume_attempt`, and mark `duplicate_possible`.
- One registry drives three scenarios: clean completion, crash followed by resume, and corrupt-checkpoint rejection.

## Verified behavior

```text
PYTHONPATH=src pytest -q
69 passed
```

In the crash scenario, the Tool executes but the second checkpoint is not written; recovery executes that Tool again and still ends with `completed`. The corrupt-checkpoint scenario raises `CheckpointCorruptError` before the Tool side-effect counter changes, and the original file remains intact.

## Trade-offs and boundaries

- Local JSON is readable and easy to test, but it is not distributed coordination and does not claim complete power-loss durability.
- At-least-once is simpler than exactly-once, but a non-idempotent Tool can produce duplicate side effects; idempotency keys and deduplication storage are deferred.
- A shared Scenario Registry keeps tests and evaluation grounded in the same definitions instead of allowing two scenario suites to drift.

## Not solved

Exactly-once execution, automatic recovery, checkpoint cleanup, process-level termination, external side-effect rollback, Redis/database stores, and token/cost/semantic-quality metrics are not implemented.
