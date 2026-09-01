# Phase 3: Loop Guard and Reliability Report - Context

**Gathered:** 2026-09-01
**Status:** Ready for planning

## Phase Boundary

Detect repeated Agent actions, enforce the existing step/time budgets as explicit reliability guards, and produce a report that explains why a run stopped. This phase builds on the Phase 1–2 Runtime, Event, timeout, and retry semantics. Checkpoint/recovery and parallel scheduling remain deferred.

## Open Decisions

- How many repetitions constitute a loop and whether the threshold is consecutive or windowed.
- Whether different Tool results reset the loop counter.
- Report format and whether it is derived solely from Events or also from final RunState.

## Confirmed Decisions

### Action signature

- Loop Guard compares a canonical Action signature made from Tool name plus canonicalized arguments.
- Dictionary keys are sorted; list order is preserved; scalar types remain distinct.
- Identical Tool names with different arguments are not repeated signatures.
- Semantic similarity or embedding/LLM-based loop detection is deferred.

### Repeat threshold

- Detect consecutive repeated signatures only.
- Three consecutive identical canonical Action signatures trigger `LOOP_DETECTED`.
- A different Action resets the consecutive counter.
- Tool result content is not part of the Phase 3 loop signature or reset logic.
- The guard runs before Tool execution. The third repeated Action is recorded as detected and is not executed.

### Report model

- `RunResult` provides the terminal summary calculated by the Runtime.
- Events are the complete execution facts and the source for timeline and derived metrics.
- A Phase 3 report combines terminal summary, ordered timeline, and metrics: run ID, status, stop reason, steps, tool calls, failed calls, retry count, and loop-detected flag.
- If the terminal summary and event stream are incomplete or inconsistent, the report marks the inconsistency instead of silently choosing one source.
- Token usage, model latency/cost, human intervention, and recovery metrics are deferred until real LLM, HITL, and checkpoint capabilities exist.

---
*Phase: 03-loop-guard-and-reporting*
*Context gathered: 2026-09-01*
