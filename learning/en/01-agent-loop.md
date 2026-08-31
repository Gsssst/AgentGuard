# Agent Loop

## Problem

Before an Agent Runtime can control failures, it needs a stable boundary between the component that proposes the next action and the component that executes or rejects it.

## Why it matters

If Actions and ToolResults are unconstrained dictionaries, the Runtime cannot reliably distinguish a Tool request from completion. Invalid state may only be discovered after a side effect has already occurred.

## My first design

Use a LangGraph-like state-routing concept, but keep the first abstraction project-owned:

```text
RunState → Router → one Action → Runtime validation/execution → ToolResult → RunState
```

The first typed Actions are `CallTool` and `Finish`. `RunState` stores the run ID, step, status, last result, and a bounded recent-history window.

## Alternatives

- A fixed Action list is useful for deterministic fault scenarios but cannot express state-dependent routing.
- Raw dictionaries resemble LLM Tool Calling output but move validation too late.
- Direct LangGraph `Command` objects would bind the core model to a framework before its Runtime semantics are understood.

## Failure modes to test next

- The Router returns an unsupported object.
- The Router requests an unknown Tool.
- A Tool raises an exception.
- The Router never returns `Finish`.
- Recent history exceeds its configured bound.

## What broke

The Runtime integration tests included a Router that always returned `CallTool("echo", ...)` and never returned `Finish`. With `max_steps=3`, the Runtime executed three steps and terminated as `FAILED / STEP_BUDGET_EXCEEDED` rather than running forever:

```text
status: failed
stop_reason: step_budget_exceeded
step: 3
```

Another deliberate failure returned a plain dictionary instead of `CallTool` or `Finish`. The Runtime converted it to `FAILED / INVALID_ACTION` and did not execute the unsupported structure.

## Debug process

The successful `echo → Finish` case was verified first, followed by the non-finishing Router case. The final `RunResult` status, stop reason, and `final_state.step` confirmed that termination happened after the third Tool execution, not a fourth attempt.

## What is verified so far

The domain and Runtime tests pass (18 tests). They verify constrained Action values, serializable Tool failure fields instead of raw exception objects, bounded recent history, sync/async execution through one entry point, consistent terminal `RunResult` values, and step-budget enforcement for a non-finishing Router.

## Structured Event records

The Runtime now emits Events for key facts: `run_started`, `action_proposed`, `tool_started`, `tool_succeeded`, `tool_failed`, and `run_finished`. Tests use `InMemoryEventSink` to assert ordering; CLI runs will use `JsonlEventSink` to write one JSON object per line.

Events record “what happened,” while `RunState` records the information the Router needs to choose its next Action. An Event stream is not a Checkpoint: it does not by itself guarantee process recovery, but it makes one run explainable.

## CLI vertical slice

The successful scenario can now be run locally with:

```bash
PYTHONPATH=src python -m agentguard.cli run --output /tmp/agentguard-run.jsonl
```

The actual run returns `status: completed` and `stop_reason: completed`; its JSONL contains six ordered events from `run_started` through `run_finished`. It requires no external model API, database, Redis, or RabbitMQ.

## What is not solved yet

Timeout, retry, cancellation, loop detection, and checkpoint/resume are not implemented. The model does not yet answer when an event or a future checkpoint should be persisted relative to Tool execution.

## Interview questions I can now answer

- Why separate Router decisions from Runtime execution?
- Why use typed Python objects instead of dictionaries at the Runtime boundary?
- Why are Event history and resumable Checkpoint state separate concepts?
- Why does `RunResult` carry both a status and a stop reason?
