# Phase 6: Resource Locks and Batch Concurrency - Research

**Researched:** 2026-09-02
**Confidence:** HIGH for the local asyncio design; MEDIUM for fairness details because the project has no existing concurrency primitive.

## Recommendation

Use a small standard-library `ResourceLockManager` built on `asyncio.Condition`. Represent each resource as a canonical string key with a reader count, one writer owner, and a count of waiting writers. Grant a request when every requested resource is available; if any resource conflicts, wait until notified or until a monotonic deadline expires.

Acquire all requested resources in sorted key order. Validate and normalize the complete request before waiting. On partial acquisition failure, release all acquired resources in a `finally` block. Do not support lock upgrades. Track read/write/destructive mode explicitly rather than inferring from capability labels.

Wrap ToolExecutor execution with an async context manager so release is guaranteed for success, Tool exceptions, timeout results, task cancellation, and lock timeout. A lock timeout must return a structured result and must not emit `TOOL_STARTED`.

## Batch boundary

Add an explicit `Runtime.execute_batch(actions)` API. Keep `Runtime.run()` unchanged and sequential. The batch API should validate a flat collection of independent `CallTool` Actions, schedule one coroutine per Action with `asyncio.gather(..., return_exceptions=False)` only after each coroutine converts its own Tool failure into a `ToolResult`, and return results associated with the original input order. One Action failure must not cancel unrelated Actions.

Permission checks must run before lock acquisition. For approved/allowed Actions, the order is: validate Tool metadata and resources, authorize, acquire locks, emit start evidence, invoke ToolExecutor, release locks, emit result evidence. Existing retry/timeout behavior remains inside the Tool boundary.

## Compatibility and limits

Use only Python 3.11+ standard library. A lock manager injected into multiple Runtime instances provides process-local coordination; the default manager is private to one Runtime. Resource IDs remain opaque strings and are not path-resolved. Unlabelled resources remain unlocked for backward compatibility. This phase does not provide cross-process durability, rollback, DAG scheduling, lock leasing, or exactly-once execution.

## Verification focus

- Two reads of one resource overlap.
- A write blocks reads and writes of the same resource.
- Waiting writers prevent later readers from bypassing them.
- Multi-resource requests acquired in sorted order do not deadlock.
- Lock timeout leaves the Tool uncalled and releases any partial locks.
- Exceptions, timeout, cancellation, and normal completion all release locks.
- Independent batch failures do not cancel other Actions and preserve input/result association.
