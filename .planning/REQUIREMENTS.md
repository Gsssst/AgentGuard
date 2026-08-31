# Requirements: AgentGuard

**Defined:** 2026-08-31  
**Core Value:** An Agent Runtime must terminate, remain bounded, and leave enough evidence to explain what happened when tools fail or the agent repeats itself.

## v0.1 Requirements

### Agent Loop

- [ ] **LOOP-01**: A developer can run a deterministic scripted Agent Loop that proposes actions, executes tools, observes results, and terminates with an explicit reason.
- [ ] **LOOP-02**: The Runtime rejects malformed or unknown actions without crashing or silently executing them.
- [ ] **LOOP-03**: The Runtime enforces a configurable maximum step budget.

### Tool Reliability

- [ ] **TOOL-01**: A tool call is cancelled and reported as timed out when it exceeds its configured deadline.
- [ ] **TOOL-02**: A tool can declare whether retry is safe, and non-idempotent tools are not blindly retried.
- [ ] **TOOL-03**: Retry attempts are bounded and recorded with attempt number and failure reason.

### Loop Protection

- [ ] **GUARD-01**: The Runtime detects repeated equivalent actions using a documented signature policy.
- [ ] **GUARD-02**: A detected loop terminates the run with an explainable stop reason.

### Evidence and Faults

- [ ] **EVENT-01**: The Runtime emits structured events for run start/finish, tool start/success/failure/timeout, retry scheduling, and loop termination.
- [ ] **FAULT-01**: The project provides deterministic tools/scenarios for delay, timeout, controlled failure, and repeated results.
- [ ] **REPORT-01**: A developer can inspect a run as JSONL or an equivalent machine-readable report.

### Developer Experience

- [ ] **DX-01**: The first vertical slice is runnable locally without an external model API, database, Redis, or RabbitMQ.
- [ ] **DX-02**: Automated tests cover the primary success and failure paths of the first vertical slice.
- [ ] **DX-03**: Each completed reliability capability has a learning note grounded in implementation and test evidence.

## v0.2+ Requirements

- Checkpoint and resume after process failure.
- Crash and duplicate-execution fault scenarios.
- Permission levels, approval state, interrupt/resume, and audit trail.
- Resource locks and read/write conflict handling.
- Framework adapters, beginning with a LangGraph adapter.
- Framework-neutral reliability benchmark and comparative reports.
- Optional local HTTP API and simple UI.
- Java Control Plane, PostgreSQL, Redis, and RabbitMQ only when demonstrated requirements justify them.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full business Agent | Duplicates AstraLoom and distracts from Runtime reliability. |
| Real LLM in first slice | Adds nondeterminism and API cost before core semantics are tested. |
| Java + Python distributed deployment in V0.1 | Introduces cross-service debugging before the Runtime model is stable. |
| RabbitMQ / Redis in V0.1 | No demonstrated queue, lock, or distributed-state requirement yet. |
| Frontend and multi-tenant SaaS | Not needed to validate the core developer workflow. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| LOOP-01..03 | Phase 1 | Pending |
| TOOL-01..03 | Phase 2 | Pending |
| GUARD-01..02 | Phase 3 | Pending |
| EVENT-01, REPORT-01 | Phase 1 | Pending |
| FAULT-01 | Phase 2 | Pending |
| DX-01 | Phase 1 | Pending |
| DX-02, DX-03 | Phase 3 | Pending |

**Coverage:** 14 v0.1 requirements; all mapped to exactly one initial roadmap phase.

---
*Requirements defined: 2026-08-31*
*Last updated: 2026-08-31 after initialization*
