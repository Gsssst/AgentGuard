# Phase 10 Learning Record: Fixing duplicated approval results in MessagesState

**Date:** 2026-09-04  
**Scope:** LangGraph `MessagesState + add_messages` approval-resume path

## 1. Goal and boundary

This phase fixes the B1 blocker found by the v0.3 audit: an approval placeholder
`ToolMessage` and the final resumed result were both appended by the `add_messages`
reducer, producing two results for one `tool_call_id`. LangGraph remains the owner of
graph state, checkpoints, and the `interrupt/resume` lifecycle. AgentGuard remains the
boundary for permission, digest validation, resource locks, timeout, retry, and structured
tool failures.

## 2. Failure reproduction

The old state sequence was:

```text
pause:  [AIMessage, ApprovalRequired(call-1)]
resume: [AIMessage, ApprovalRequired(call-1), success(call-1)]
```

This was not a single tool execution failure; it was a mismatch between the adapter's
returned projection and the reducer semantics. Phase 9 plain-list tests passed, while a
real `MessagesState` probe exposed the cross-phase integration defect.

## 3. Design fix

- **D-01/D-02/D-03:** When approvals are pending, `prepare()` writes only the fixed
  `_agentguard_prepared` key containing direct results, pending calls, and digest bindings.
  It omits `messages`, so no user-visible placeholder is emitted.
- **D-04/D-07:** With no pending calls, `prepare()` returns final messages directly; routing
  only inspects `_agentguard_prepared.pending`.
- **D-05/D-06/D-08:** The legacy `__call__()` behavior is preserved. Approval graphs register
  the public `prepare()` and `approval()` methods directly; no node factory is added. The
  replay limitation of the legacy approval entry remains documented as at-least-once.
- **D-09/D-10/D-11/D-12:** After resume, `approval()` merges direct, approved, denied, missing,
  digest-mismatch, missing-tool, and execution-failure results by input index, emits one final
  message for each original ID, and marks pending as consumed. Regression scope is limited to
  the default `messages` reducer.

## 4. Deliberate failures and observations

| Failure | Expected behavior | Result |
|---|---|---|
| Placeholder emitted into `messages` at pause | No `ApprovalRequired` result should appear | Fixed; paused state keeps only the original AIMessage |
| Mixed batch with direct, approval, and unguarded calls | Failures stay isolated and resume remains ordered | Passed; each call has one result |
| Direct call replay on resume | No duplicate side effect | Passed; invocation count stays at 1 |
| Missing or tampered digest | Reject only the affected call | Passed; sibling calls are unaffected |
| Sensitive argument in interrupt payload | Only recursively redacted values are exposed | Passed; raw sensitive values do not appear |

## 5. Verification evidence

Targeted regression command:

```text
PYTHONPATH=src pytest -q tests/integration/test_langgraph_approval.py \
  tests/integration/test_langgraph_optional.py tests/unit/test_langgraph_adapter.py -rs
24 passed
```

Full regression command:

```text
PYTHONPATH=src pytest -q
```

The v0.3 milestone audit must be rerun during closeout to confirm that B1 and the affected
requirements `BATCH-04`, `APPROVAL-03`, and `APPROVAL-06` move from partial to fully satisfied.

## 6. Known limits

- Compatibility remains bounded by the verified `langgraph 0.6.11`, `langchain-core 0.3.86`,
  and current Python environment.
- The legacy approval `__call__()` path retains at-least-once replay semantics; no exactly-once
  external side-effect guarantee is claimed.
- This phase does not expand custom `messages_key`, multiple reducers, approval UI, RBAC,
  external services, distributed locks, or high availability.

