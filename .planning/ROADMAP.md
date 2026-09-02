# Roadmap: AgentGuard

## Phase 1 — Deterministic Runtime Skeleton

Define the Action/Tool/Result state model and implement the smallest scripted loop, event model, CLI entry point, and baseline tests. The phase ends with one successful local run and explicit termination reasons.

## Phase 2 — Tool Failure Boundaries

Add timeout, cancellation, bounded retry, idempotency metadata, and deterministic delay/failure tools. Deliberately create failures and document the observed semantics.

## Phase 3 — Loop Guard and Reliability Report

Add repeated-action detection, step/time budgets, structured JSONL reporting, integrated fault scenarios, and a reproducible end-to-end test suite. Compare the first design with selected mature Runtime implementations and record trade-offs.

## Phase 4 — Recovery and Evaluation (v0.2 candidate)

Only after V0.1 is validated: checkpoint/resume, crash simulation, duplicate execution, scenario registry, benchmark metrics, and recovery reports.

## Phase 5 — Permission, Concurrency, and Adapters (future)

Explore approval state, audit, resource locks, conflict policies, LangGraph/Pi adapters, and a framework-neutral benchmark. Decide separately whether a Java Control Plane is justified.

## Milestones

- **V0.1 Runtime Reliability Core**: Phases 1–3
- **V0.2 Recovery and Evaluation**: Phase 4, after V0.1 evidence supports expansion

### Phase 4: Recovery and Evaluation (v0.2 candidate): checkpoint/resume, crash simulation, duplicate execution, scenario registry, benchmark metrics, and recovery reports

**Goal:** Add an inspectable local checkpoint/resume path with deterministic crash simulation, explicit at-least-once recovery evidence, and a shared reliability evaluation harness.
**Requirements**: CHECKPOINT-01, CHECKPOINT-02, RECOVERY-01, RECOVERY-02, RECOVERY-03, EVAL-01, EVAL-02
**Depends on:** Phase 3
**Plans:** 3 plans

Plans:
- [x] 04-01 — checkpoint model, codec, and atomic local store
- [x] 04-02 — Runtime checkpoint hooks, crash simulation, resume, and recovery reporting
- [x] 04-03 — scenario registry, evaluation runner, and bilingual learning notes

### Phase 5: Permission Control and Approval Boundaries

**Goal:** Add inspectable Tool capability permissions, explicit approval pauses, and audit-safe evidence while deferring concurrency and framework adapters.
**Requirements**: PERMISSION-01, PERMISSION-02, PERMISSION-03, APPROVAL-01, APPROVAL-02, APPROVAL-03, AUDIT-01, AUDIT-02, DX-03
**Depends on:** Phase 4
**Plans:** 3/3 plans executed

Plans:
- [x] 05-01 — capability tags, permission policy, and waiting state contracts
- [x] 05-02 — checkpointed approval pause and explicit digest-bound resume
- [x] 05-03 — audit redaction, permission events, reports, and bilingual notes

---
*Roadmap created: 2026-08-31*
