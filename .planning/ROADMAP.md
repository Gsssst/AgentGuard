# Roadmap: AgentGuard

## Completed Milestones

- ✅ **v0.1 Runtime Reliability Core** — Phases 1–3 (shipped)
- ✅ **v0.2 Recovery, Permissions, and Concurrency** — Phases 4–6 (shipped)
- ✅ **v0.3 LangGraph Adapter** — Phases 7–10 (shipped 2026-09-04) — [archive](milestones/v0.3-ROADMAP.md)

## Current Milestone: v0.4 Agent Observability Console

**Goal:** Add a local Web console that lets AgentGuard developers observe and replay Agent tool execution, approvals, failures, and retries.

**Phases:** 4 | **Requirements:** 20 | **Coverage:** 100%

## Phases

### Phase 11: Event Contract and Collector

**Goal:** Define a versioned, safe event envelope and collect Runtime/adapter events into a process-local run index.
**Requirements:** OBS-03, OBS-04, COMPAT-01
**Depends on:** v0.3 Runtime and adapter events

**Success criteria:**

1. Event envelopes validate required identity, sequence, timestamp, type, status, and safe payload fields.
2. Runtime and adapter events are normalized without leaking raw exceptions or secrets.
3. A collector assigns monotonic per-run sequence numbers and exposes live run summaries in memory.
4. Core `import agentguard` and existing tests remain independent of console dependencies.

### Phase 12: JSONL History and Run API

**Goal:** Persist runs as append-only JSONL and expose local REST endpoints for run lists and run details.
**Requirements:** OBS-01, OBS-02, HISTORY-01, HISTORY-02, HISTORY-03
**Depends on:** Phase 11

**Success criteria:**

1. Built-in run creation returns a stable `run_id` and appears in the run list.
2. Events are flushed to UTF-8 JSONL before live publication.
3. Service restart reloads recent runs and valid events while safely handling a truncated final line.
4. REST responses expose status, timing, event counts, and ordered safe events.

### Phase 13: SSE, External Ingestion, and Demo Scenarios

**Goal:** Stream run events live, support bounded external local ingestion, and provide deterministic scenarios for the console.
**Requirements:** STREAM-01, STREAM-02, STREAM-03, DEMO-01, INGEST-01, INGEST-02, COMPAT-02
**Depends on:** Phase 12

**Success criteria:**

1. SSE delivers ordered events with reconnectable IDs and `Last-Event-ID` resume behavior.
2. Slow or disconnected subscribers are bounded and cannot block a run.
3. Built-in scenarios cover success, retry, timeout, approval-pending, approval-denied, and terminal failure.
4. External local events use the same validation, sequencing, and redaction boundary as built-in events.
5. Backend tests cover stream ordering, reconnect, queue bounds, scenarios, and ingestion failures.

### Phase 14: React Console and End-to-End Evidence

**Goal:** Deliver the local React/Vite run list, timeline, detail drawer, and complete bilingual evidence for the observability workflow.
**Requirements:** UI-01, UI-02, UI-03, COMPAT-03, COMPAT-04
**Depends on:** Phase 13

**Success criteria:**

1. Run list shows status, timing, and event-count summaries from the API.
2. Run detail timeline updates incrementally from SSE without manual refresh.
3. Event detail drawer shows safe fields for calls, approvals, retries, failures, and results.
4. Frontend fixtures/tests cover rendering, live updates, and API error states.
5. A documented local quickstart demonstrates built-in and external runs end to end; Chinese and English learning notes record deliberate failures and limits.

## Requirement Traceability

| Requirement | Phase | Status |
|---|---|---|
| OBS-01..02 | Phase 12 | Pending |
| OBS-03..04 | Phase 11 | Pending |
| STREAM-01..03 | Phase 13 | Pending |
| HISTORY-01..03 | Phase 12 | Pending |
| UI-01..03 | Phase 14 | Pending |
| DEMO-01 | Phase 13 | Pending |
| INGEST-01..02 | Phase 13 | Pending |
| COMPAT-01 | Phase 11 | Pending |
| COMPAT-02 | Phase 13 | Pending |
| COMPAT-03..04 | Phase 14 | Pending |

## Technical Boundaries

- Single-process local service; no database, broker, WebSocket, login, or multi-tenancy.
- SSE is read-only in v0.4; page-level approval is deferred.
- JSONL is append-only history, not a general analytics/query engine.
- AgentGuard's existing redaction and at-least-once/process-local limits remain explicit.

---
*Roadmap created: 2026-09-04 for milestone v0.4*
