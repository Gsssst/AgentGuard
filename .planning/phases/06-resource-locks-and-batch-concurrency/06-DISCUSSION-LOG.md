# Phase 6: Resource Locks and Batch Concurrency - Discussion Log

**Date:** 2026-09-02
**Phase:** 06-resource-locks-and-batch-concurrency

## Resource locking

| Decision | Selected behavior |
|---|---|
| Lock model | In-process `ResourceLockManager` |
| Read access | Shared lock |
| Write/destructive access | Exclusive lock |
| Fairness | Write priority |
| Conflict | Wait, then structured lock-timeout failure |

## Deadlock prevention

- Acquire multiple resources in sorted resource-ID order.
- Declare the complete resource set before execution.
- Release already acquired locks if a later acquisition fails.
- Do not support read-to-write lock upgrades in the first version.

## Resource metadata

- Tool declares `Mapping[str, ResourceAccess]`.
- Resource IDs are opaque non-empty strings with minimal trimming only.
- Resource access mode must be covered by Tool capabilities.
- Tools without resource declarations remain compatible and execute without locking.

## Batch execution

- Add explicit `execute_batch()` while preserving sequential `run()`.
- First version accepts only independent flat Actions.
- Results are independent; one Action failure does not cancel the others.
- A shared lock manager is explicit dependency injection; the default manager is local.

## Deferred ideas

Distributed locks, DAG dependencies, Router-managed concurrency, lock upgrades, remote coordination, framework adapters, and Java infrastructure remain outside this phase.
