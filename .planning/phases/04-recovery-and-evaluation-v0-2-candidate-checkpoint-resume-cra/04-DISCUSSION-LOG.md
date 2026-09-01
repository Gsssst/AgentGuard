# Phase 4: Recovery and Evaluation (v0.2 candidate) - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-01
**Phase:** 04-recovery-and-evaluation-v0-2-candidate-checkpoint-resume-cra
**Areas discussed:** checkpoint state and timing, duplicate execution semantics, storage/lifecycle, crash simulation, resume API and validation, recovery event identity, reliability evaluation, scenario registry

---

## Checkpoint state and timing

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal recoverable state | Save only state required to choose the next Action | ✓ |
| Full event/history snapshot | Duplicate the complete run log inside each checkpoint | |

**User's choice:** Minimal recoverable state.
**Notes:** Checkpoint is not a second copy of the full event log.

## Checkpoint write boundary

| Option | Description | Selected |
|--------|-------------|----------|
| After each complete step | Persist after ToolResult is recorded and step increments | ✓ |
| Before Tool execution | Save intent before dispatch | |

**User's choice:** After each complete step, accepting at-least-once behavior.

## Duplicate execution semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Re-execute unconfirmed Action | Simple at-least-once recovery; mark duplicate_possible | ✓ |
| Skip unconfirmed Action | At-most-once but risks losing a required result | |
| Idempotency key and dedup store | Stronger semantics with substantially more infrastructure | |

**User's choice:** Re-execute and make the risk explicit.

## Storage and lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Local JSON + atomic replacement | One file per run, schema-versioned and inspectable | ✓ |
| Redis/database | Durable shared storage but outside current local scope | |

**User's choice:** Local JSON with atomic replacement.
**Notes:** Keep files after completion/failure and update lifecycle status.

## Crash simulation

| Option | Description | Selected |
|--------|-------------|----------|
| Injectable deterministic crash point | Reproduce `after_tool_before_checkpoint` reliably | ✓ |
| Real process kill only | More realistic but nondeterministic and hard to test | |

**User's choice:** Injectable `SimulatedCrash`.

## Resume and validation

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit `resume()` | Caller chooses exactly which checkpoint to resume | ✓ |
| Automatic directory scanning | Convenient but risks unintended Tool execution | |

**User's choice:** Explicit resume only.
**Notes:** Corrupt, incomplete, or unsupported checkpoints reject before any Tool execution.

## Recovery event identity

| Option | Description | Selected |
|--------|-------------|----------|
| Same `run_id` + incremented `resume_attempt` | Append a continuous, auditable logical run history | ✓ |
| New run ID on every recovery | Easier isolation but breaks continuity | |

**User's choice:** Same logical run ID with recovery attempt metadata.

## Evaluation scope

| Option | Description | Selected |
|--------|-------------|----------|
| Reliability metrics only | Checkpoint/recovery correctness and duplicate risk | ✓ |
| Model quality/cost metrics | Deferred until real LLM execution exists | |

**User's choice:** Reliability metrics only.

## Scenario organization

| Option | Description | Selected |
|--------|-------------|----------|
| Shared scenario registry | Tests and benchmark consume the same deterministic definitions | ✓ |
| Separate ad hoc tests/benchmarks | Faster initially but duplicates behavior definitions | |

**User's choice:** Registry with three initial scenarios: clean run, crash-and-resume, corrupt-checkpoint rejection.

## the agent's Discretion

- Exact JSON schema, exception naming, event field names, metric aggregation, and fixture organization.

## Deferred Ideas

- Exactly-once/idempotency-key deduplication, distributed checkpoint stores, automatic recovery/cleanup, semantic model evaluation, and parallel scheduling.
