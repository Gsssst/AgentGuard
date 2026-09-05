# Requirements: AgentGuard v0.4 Agent Observability Console

**Defined:** 2026-09-04
**Core Value:** An Agent Runtime must terminate, remain bounded, and leave enough evidence to explain what happened when tools fail or the agent repeats itself.

## v0.4 Requirements

### Run and Event Observability

- [ ] **OBS-01**: A developer can start a built-in deterministic Agent run and receive a stable `run_id`.
- [ ] **OBS-02**: A developer can list recent runs with status, start time, duration, and event counts.
- [ ] **OBS-03**: Every collected event uses a versioned envelope with `run_id`, monotonic per-run sequence, UTC timestamp, event type, status, and safe payload fields.
- [ ] **OBS-04**: The collector represents tool calls, approvals, failures, retries, timeouts, and terminal results without exposing raw exception stacks or secrets.

### Real-Time Streaming

- [ ] **STREAM-01**: A developer can subscribe to `/api/runs/{run_id}/events` and receive new run events through SSE in sequence order.
- [ ] **STREAM-02**: Stream events carry reconnectable IDs, and a reconnecting client can resume from `Last-Event-ID` without duplicating already-consumed events.
- [ ] **STREAM-03**: A slow or disconnected browser client cannot block the Agent run or grow an unbounded server-side queue.

### Local History

- [ ] **HISTORY-01**: Each validated event is appended as one UTF-8 JSON value per line to a local JSONL history file before it is published to live subscribers.
- [ ] **HISTORY-02**: After a service restart, a developer can reload recent runs and their event timelines from JSONL files.
- [ ] **HISTORY-03**: History loading handles a truncated final line safely and does not discard valid preceding events.

### Web Console

- [ ] **UI-01**: The React console displays a run list with status, timing, and event-count summaries.
- [ ] **UI-02**: The run detail page displays an ordered timeline that updates from SSE without a manual refresh.
- [ ] **UI-03**: Selecting an event opens a detail drawer showing safe, event-type-specific fields for tool calls, approvals, retries, failures, and results.

### Scenarios and External Ingestion

- [ ] **DEMO-01**: Built-in deterministic scenarios cover at least success, retry, timeout, approval-pending, approval-denied, and terminal-failure paths.
- [ ] **INGEST-01**: An external local Agent can submit validated events through a documented SDK/API path and see them in the same run timeline.
- [ ] **INGEST-02**: External ingestion applies the same schema validation, run sequencing, and redaction boundary as built-in events.

### Compatibility and Evidence

- [ ] **COMPAT-01**: AgentGuard core remains importable and testable without installing the console's FastAPI or frontend dependencies.
- [ ] **COMPAT-02**: Backend tests cover event envelopes, JSONL persistence, SSE ordering/reconnect, queue bounds, and ingestion failures.
- [ ] **COMPAT-03**: Frontend tests or deterministic fixtures verify run-list rendering, timeline updates, safe event details, and API error states.
- [ ] **COMPAT-04**: Chinese and English learning notes record the event contract, deliberate failures, and known local-console limits.

## Future Requirements

### Interactive Approval and Analysis

- **APPROVAL-UI-01**: A reviewer can approve or reject pending calls directly from the Web console.
- **ANALYTICS-01**: A developer can compare multiple runs and view failure/retry trends.
- **EXPORT-01**: A developer can export a run as JSON, CSV, or a shareable report.

### Platformization

- **PLATFORM-01**: Persist runs in a queryable database with retention and pagination.
- **PLATFORM-02**: Support authenticated users, roles, and multi-tenant workspaces.
- **PLATFORM-03**: Support WebSocket or hosted event infrastructure for remote deployments.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Page-level approve/deny | Keep v0.4 focused on trustworthy observation before adding control-plane mutations. |
| Database persistence | JSONL is sufficient for the first local single-process history workflow. |
| WebSocket transport | SSE is adequate for one-way monitoring and has a smaller failure surface. |
| Login, RBAC, and multi-tenancy | No remote or shared deployment requirement has been demonstrated. |
| Trend analytics and cross-run comparison | First validate the event contract and run-detail workflow. |
| Distributed event bus, HA, or hosted telemetry | Process-local AgentGuard semantics remain the explicit project boundary. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
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

**Coverage:**

- v0.4 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-04*
*Last updated: 2026-09-04 after v0.4 scope confirmation*
