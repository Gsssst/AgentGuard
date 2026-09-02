# Phase 6: Resource Locks and Batch Concurrency

## What this phase teaches

AgentGuard adds a process-local `ResourceLockManager`. A Tool declares resources as `resource ID -> access mode`: `read` uses a shared lock, while `write` and `destructive` use an exclusive lock. The mode must be covered by the Tool capability metadata. Existing Tools without resource declarations remain compatible, but receive no conflict protection.

Multiple resources are acquired in sorted resource-ID order, preventing deadlocks caused by opposite acquisition orders. Lock waits have a timeout, partial acquisition is cleaned up, and locks are released in a `finally` path after success, failure, timeout, cancellation, or exception. Writers have priority to avoid starvation; version one does not upgrade a read lock to a write lock.

`Runtime.execute_batch()` is an explicit concurrency entry point for independent flat `CallTool` actions. Results preserve input order, and one failure does not automatically cancel unrelated actions. Conflicts wait by default; after `lock_timeout`, a structured failure is returned without `TOOL_STARTED` or Tool side effects. Existing `Runtime.run()` keeps its sequential semantics.

## Verified and deferred

The verified behaviors are overlapping reads, write exclusion, writer priority, sorted acquisition, multi-resource timeout cleanup, cancellation release, batch overlap, conflict serialization, and independent failures. Test command:

```text
PYTHONPATH=src pytest -q
95 passed
```

These are in-process memory locks, not distributed locks. Rollback, DAG dependencies, Router-managed concurrency, lease renewal, and exactly-once guarantees are deferred. Locks protect only resources explicitly declared by a Tool.
