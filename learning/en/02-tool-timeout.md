# Tool Timeout and Retry

## Problem

An Agent Tool may never return, fail transiently, or continue producing side effects after the Runtime has stopped waiting. The Runtime must return within a bound without falsely claiming that underlying execution has stopped.

## First design

- Per-Tool timeout overrides the Runtime default.
- Timeout becomes a `TIMED_OUT` observation in `RunState`, allowing Router fallback.
- Async Tools receive cooperative cancellation; sync Tools only stop being awaited and their worker threads may continue.
- `FailureKind` describes one failure; `RetrySafety` describes whether repeating the Tool is considered safe.
- Only `SAFE + TRANSIENT` is automatically retried.
- `max_attempts` includes the initial execution and defaults to one.
- Backoff is deterministic exponential backoff with no jitter.

## What broke

### A Tool-raised TimeoutError was misreported as a Runtime deadline

The first implementation caught `asyncio.TimeoutError`. A fault test showed that `asyncio.TimeoutError` and built-in `TimeoutError` are the same exception type, so a Tool-raised upstream timeout was incorrectly reported as an AgentGuard deadline.

The fix explicitly creates a Task and uses `asyncio.wait` to determine whether the Task remained incomplete at the deadline. Only that path raises the internal `_RuntimeDeadlineExceeded`; a completed Task preserves its own `TimeoutError` as a transient Tool failure.

### An uncooperative async Tool could suppress cancellation

An async Tool may catch `CancelledError` and continue waiting. Awaiting that Task after cancellation would make the timeout path unbounded again.

The Runtime now requests cancellation, yields one event-loop turn for cooperative cleanup, and detaches a still-running Task before returning `TIMED_OUT`. This preserves bounded Runtime return while acknowledging that underlying work may continue.

## Failure modes

- A timed-out sync Tool may continue in its worker thread, so automatic timeout retry is disabled to prevent overlapping duplicate calls.
- `UNKNOWN`, `UNSAFE`, and `REQUIRES_IDEMPOTENCY_KEY` are non-retryable until a real idempotency-key mechanism exists.
- A `PERMANENT` failure is not retried even when the Tool is `SAFE`.
- Timeout retry remains disabled pending broader cancellation experiments.

## Event evidence

The event stream can show:

```text
tool_attempt_started
retry_scheduled
tool_attempt_started
tool_succeeded / tool_failed / tool_timed_out
```

Events include attempt number, maximum attempts, delay, effective timeout, and timeout source.

## Verified

Forty-three tests pass, covering layered timeouts, async cancellation, the weak sync-thread guarantee, uncooperative coroutines, failure classification, retry safety, attempt budgets, deterministic exponential backoff, retry events, and Router fallback.

## Not solved

Process-level forced termination, external side-effect rollback, idempotency keys and deduplication storage, random jitter, checkpoint/recovery, and concurrent resource conflicts are not implemented.
