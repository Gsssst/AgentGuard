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

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 3
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 4 to break down)

---
*Roadmap created: 2026-08-31*
