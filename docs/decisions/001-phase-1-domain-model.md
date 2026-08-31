# ADR 001: Phase 1 Domain Model

**Status:** Accepted for Phase 1  
**Date:** 2026-08-31

## Problem

AgentGuard needs a small vocabulary for one Agent Runtime execution before it can safely implement the execution loop. If Router decisions, tool observations, current state, and terminal outcomes are represented as loose dictionaries or raw exceptions, invalid states can travel too far and failure behavior becomes difficult to test.

## Decision

Use typed Python objects for the Phase 1 domain boundary:

- `CallTool` and `Finish` are the only Action types.
- `ToolResult` normalizes successful returns and raised exceptions into serializable data.
- `RunState` stores the current decision state plus a bounded recent-history window.
- `RunStatus` and `StopReason` are separate enums.
- `RunResult` is terminal and validates consistency between status, reason, and run ID.

## Alternatives Considered

### Unconstrained dictionaries

Rejected for the core boundary because missing keys, invalid values, and spelling differences would be discovered late. A JSON parser may be added later at the LLM adapter boundary, but it should produce typed Actions before entering the Runtime.

### One `success` boolean

Rejected because a failed Tool, invalid Action, and exhausted step budget require different handling and different evidence.

### Complete history inside `RunState`

Rejected for the initial model. The current state needs a bounded recent window; complete audit history belongs to Events and a future Checkpoint/Recovery layer.

## Consequences

Positive:

- Router and Runtime responsibilities are explicit.
- Tests can assert invalid construction and terminal-state consistency.
- Results can be serialized without retaining raw exception objects.
- Future LLM, LangGraph, or CLI adapters have a typed boundary to target.

Costs and open questions:

- The model currently uses generic `object` values; a later schema strategy may be needed for safe Tool arguments and results.
- `RunState` is mutable because the execution loop has not yet been implemented; checkpoint serialization semantics remain open.
- Timeout, retry, cancellation, loop detection, and permission states are intentionally not represented yet.

## Evidence

`tests/unit/test_domain_models.py` covers valid construction, invalid values, bounded history, serializable error fields, and terminal result validation.
