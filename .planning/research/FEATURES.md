# v0.4 Feature Research

## Table Stakes

| Capability | Expected behavior | Complexity |
|---|---|---|
| Run list | Show recent runs with status, start time, duration, and event counts | Low |
| Run detail | Show one run's ordered event timeline | Low |
| Event detail | Inspect safe fields for tool, approval, retry, timeout, and failure events | Medium |
| Live updates | Append new events to the open run without page refresh | Medium |
| History | Re-open a completed run from JSONL-backed records | Medium |
| Deterministic demo | Start built-in success/failure/approval scenarios from the UI | Medium |

## Differentiators for AgentGuard

- Correlate every event with `run_id`, sequence number, step, tool call ID, and
  terminal status.
- Make failure kinds and retry attempts visible instead of flattening them into
  generic logs.
- Preserve the same redaction boundary used by Runtime and LangGraph approval.
- Show a clear distinction between direct execution, pending approval, denied
  calls, retrying calls, and final failures.
- Surface known limits: process-local event collection, bounded compatibility,
  and at-least-once side-effect semantics.

## Deferred Features

- Page-level approve/deny actions.
- Multi-run comparison, trend charts, alert rules, and export formats.
- User accounts, RBAC, multi-tenancy, and remote deployment.
- DAG visualization and graph-level LoopGuard dashboards.

## Proposed v0.4 User Flow

1. Start the local console.
2. Choose a built-in scenario or connect an external AgentGuard runtime.
3. Open the newly created run automatically.
4. Watch events arrive through SSE.
5. Click an event to inspect its safe detail payload.
6. Return to the run list and reopen the persisted JSONL history.
