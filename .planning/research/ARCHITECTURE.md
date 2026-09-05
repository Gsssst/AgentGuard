# v0.4 Architecture Research

## Proposed Data Flow

```text
AgentGuard Runtime / demo runner
            |
            v
     EventCollector
       |         |
       |         +--> in-memory run index + subscriber queues
       |
       +------------> JSONL append-only history
                         |
FastAPI REST (/runs, /scenarios)
FastAPI SSE  (/runs/{id}/events)
            |
            v
      React + Vite console
```

## Event Envelope

Every persisted and streamed event should use one versioned envelope:

```json
{
  "schema_version": "agentguard.event.v1",
  "run_id": "run-123",
  "sequence": 17,
  "occurred_at": "2026-09-04T12:00:00Z",
  "event_type": "TOOL_RETRY",
  "step": 2,
  "tool_call_id": "call-2",
  "status": "retrying",
  "payload": {"attempt": 2, "failure_kind": "transient"}
}
```

The event collector owns sequence assignment. The server appends the complete
JSON line before publishing it to live subscribers, so a successful SSE send
never becomes the only copy of an event.

## API Shape

- `POST /api/runs` — start a built-in deterministic scenario.
- `GET /api/runs` — list recent runs from the in-memory index plus JSONL scan.
- `GET /api/runs/{run_id}` — return run summary and persisted events.
- `GET /api/runs/{run_id}/events` — SSE stream with `id=sequence`.
- `POST /api/events` — minimal external ingestion endpoint for trusted local
  SDK clients; apply the same validation and redaction contract.

## Frontend Composition

- `RunListPage`: recent runs and status filters.
- `RunDetailPage`: summary header and ordered timeline.
- `EventDetailDrawer`: safe JSON fields and event-type-specific labels.
- `useRunEvents`: EventSource lifecycle, reconnect, last-event ID, and dedupe.

## Build Order

1. Stabilize event envelope and collector against existing Runtime sink events.
2. Add JSONL writer/reader and recent-run index.
3. Add REST endpoints and deterministic scenario launcher.
4. Add SSE endpoint with reconnect and bounded subscriber queues.
5. Add the React run list/detail UI.
6. Add external ingestion and end-to-end tests.
