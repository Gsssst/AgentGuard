# ADR 003: Tool Timeout and Retry Semantics

**Status:** Accepted  
**Date:** 2026-09-01

## Decision

- Timeout guarantees bounded Runtime return, not universal termination of underlying work.
- Per-Tool timeout overrides the Runtime default.
- Timeout is an observation available to the Router.
- Runtime retry repeats the same Tool and arguments; Router fallback changes strategy.
- Automatic retry requires both `RetrySafety.SAFE` and `FailureKind.TRANSIENT`.
- `max_attempts` includes the initial attempt and defaults to one.
- Backoff is deterministic exponential backoff without jitter.
- Sync timeout and all timeout results are not automatically retried in the initial policy.

## Consequences

The model is conservative and reproducible, but it does not provide hard execution isolation. A Tool developer may also incorrectly label a Tool as `SAFE`; metadata is a policy input, not proof of idempotency.

## Evidence

The Phase 2 test suite demonstrates layered timeout selection, async cancellation, continuing sync threads, cancellation suppression, correct classification of Tool-raised `TimeoutError`, bounded attempts, retry eligibility, backoff, event traces, and Router fallback.
