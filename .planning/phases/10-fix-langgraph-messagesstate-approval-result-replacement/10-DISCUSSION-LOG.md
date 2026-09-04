# Phase 10: Fix LangGraph MessagesState approval result replacement - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-04
**Phase:** 10-fix-langgraph-messagesstate-approval-result-replacement
**Areas discussed:** state write strategy, API compatibility and graph routing, regression test scope

---

## State write strategy

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | Separate preparation state from user-visible messages; `prepare()` does not emit approval placeholders | ✓ |
| 2 | Keep placeholder messages and replace them later through reducer-specific behavior | |
| 3 | Add a second message stream or duplicate checkpoint state | |

**User's choice:** 1
**Notes:** The fixed internal key is `_agentguard_prepared`. Mixed batches retain direct results and pending context in machine state until resume; if no approval is pending, `prepare()` returns final messages directly.

## API compatibility and graph routing

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | Preserve `__call__()` and expose explicit `prepare()` → `approval()` composition for approval graphs | ✓ |
| 2 | Change `__call__()` to the new two-node lifecycle | |
| 3 | Introduce a new graph-node factory abstraction | |

**User's choice:** 1
**Notes:** Callers register public methods directly and own the LangGraph conditional route. The route checks only whether `_agentguard_prepared.pending` is non-empty. The old `__call__()` approval path keeps its existing behavior; replay limitations remain documented without a warning or hard rejection.

## Regression test scope

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | Real default `MessagesState + add_messages` mixed-batch pause/resume test plus lightweight compatibility smoke tests | ✓ |
| 2 | Only test the approval resume path | |
| 3 | Build a broad reducer/schema compatibility matrix | |

**User's choice:** 1
**Notes:** The integration test must include directly allowed, approval-required and denied calls; assert no approval placeholder appears while paused, then exactly one final `ToolMessage` per original `tool_call_id` in input order. Also protect the no-pending `prepare()` path and ordinary legacy `__call__()` behavior. This phase intentionally covers only the default `messages` key.

## the agent's Discretion

- Choose the minimal JSON shape and serialization details for `_agentguard_prepared`.
- Choose the concrete LangGraph message merge/replacement projection needed to satisfy `add_messages` semantics.
- Choose lightweight test fakes and checkpointer setup using already-verified optional dependencies.

## Deferred Ideas

- Custom message keys/reducers and broad version compatibility.
- New replay deduplication semantics or warnings for legacy `__call__()` approval usage.
- Multi-round approval, frontend approval UI, RBAC, external approval services, distributed locks/checkpoints and exactly-once side-effect guarantees.
