# Phase 2: Tool Failure Boundaries - Context

**Gathered:** 2026-08-31
**Status:** Ready for planning

## Phase Boundary

Add explicit Tool timeout, cancellation behavior, bounded retry, idempotency metadata, and deterministic delay/failure scenarios to the existing single-action sequential Runtime. Parallel scheduling, process isolation, checkpoint/recovery, and permission policy remain outside this phase.

## Confirmed Decisions

### Timeout guarantee

- A timeout guarantees that AgentGuard returns control within the configured deadline; it does not universally guarantee that the underlying Tool execution or external side effects have stopped.
- Async Tools receive cooperative task cancellation where the callable honors cancellation.
- Sync Tools adapted through a worker thread stop being awaited after timeout, but the underlying thread may continue running.
- The Runtime and documentation must expose this weaker sync cancellation guarantee rather than presenting `TIMED_OUT` as proof that all side effects stopped.
- Stronger process or sandbox isolation is deferred to a later phase.

### Timeout configuration

- Use layered timeout configuration.
- Phase 2 precedence is per-Tool registration timeout over the Runtime default timeout.
- The Runtime default provides a safety boundary when a Tool has no specific timeout.
- A future per-call override may take higher precedence, but it must be constrained by Runtime Policy rather than trusted directly from a Router or LLM Action.
- Timeout events must record the effective timeout and its configuration source for later diagnosis.

### Timeout outcome

- A timeout becomes a `ToolResultStatus.TIMED_OUT` observation and is written to `RunState`.
- The Router receives the timed-out result and may choose a fallback Tool, finish, or take another allowed action.
- A single Tool timeout does not automatically fail the whole Agent Run in Phase 2.
- The Runtime still bounds the overall loop with max steps; retry budget and later loop detection provide additional guards.
- Per-Tool `fail_run` versus `return_to_router` timeout behavior is a possible future policy, not part of the initial Phase 2 slice.

### Retry responsibility

- Use a layered responsibility model.
- Runtime retries are execution-level retries of the same Tool with the same arguments after an eligible transient failure.
- Router decisions handle strategy-level fallback: changing Tool, changing arguments, or explicitly finishing.
- Runtime retries require Tool retry-safety metadata, an eligible error category, and remaining retry budget.
- Each Runtime retry emits its own Event and attempt number.
- A Router requesting the same Tool again is a new `CallTool`, not another attempt in the prior Runtime retry sequence; the two counters remain distinct.

### Retry safety

- Tool metadata uses `RetrySafety`: `SAFE`, `UNSAFE`, `REQUIRES_IDEMPOTENCY_KEY`, or `UNKNOWN`.
- The default is `UNKNOWN`, and retry policy fails closed.
- Phase 2 permits automatic Runtime retry only for `SAFE` Tools.
- `UNSAFE` and `UNKNOWN` Tools are never automatically retried.
- `REQUIRES_IDEMPOTENCY_KEY` is represented for future evolution but remains non-retryable until an actual key and deduplication mechanism exist.
- A Tool developer can still misclassify safety; documentation and tests must not imply metadata alone guarantees real-world idempotency.

### Failure classification and attempt counting

- Normalize failures into `FailureKind`: `TRANSIENT`, `PERMANENT`, `TIMEOUT`, and `CANCELLED`.
- `max_attempts` counts the initial execution and every retry. For example, `max_attempts=3` means one initial attempt plus at most two retries.
- The default is `max_attempts=1`, meaning no automatic retry unless explicitly configured.
- The initial Phase 2 automatic retry path is limited to `RetrySafety.SAFE + FailureKind.TRANSIENT` with remaining attempt budget.
- `PERMANENT` and `CANCELLED` failures are not automatically retried.
- Sync Tool timeout is not automatically retried because the timed-out worker thread may still be running.
- Async Tool timeout retry remains undecided until a cancellation experiment verifies the behavior; Phase 2 must not promise it in advance.

### Backoff

- Use deterministic exponential backoff for the initial retry implementation.
- No random jitter in Phase 2; jitter is a later experiment because it adds nondeterminism before the core retry semantics are validated.
- The policy should leave room for a future optional jitter strategy without making it active by default.
- Retry events must record the planned/effective delay so a run can be explained and tests can verify the schedule.

## Open Decisions

- Backoff and retry-exhaustion semantics.

## Deferred Ideas

- Process-isolated Tool execution.
- Container/sandbox termination guarantees.
- Parallel Tool scheduling and resource conflict handling.

---
*Phase: 02-tool-failure-boundaries*
*Context gathered: 2026-08-31*
