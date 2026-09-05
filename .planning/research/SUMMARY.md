# v0.4 Research Summary

## Recommendation

Build a local, single-process observability console around a versioned
AgentGuard event envelope. Use FastAPI REST endpoints plus native SSE for
one-way live updates, JSONL for append-only history, and a separate React/Vite
frontend. This is enough to validate the developer workflow without adding a
database, broker, WebSocket layer, or authentication system.

## Key Findings

- FastAPI's current SSE support provides JSON event data and reconnect metadata
  (`event`, `id`, `retry`, `comment`).
- Browser `EventSource` is unidirectional and reconnect-aware, matching a
  read-only monitoring stream.
- JSONL is easy to append and inspect, but needs bounded indexes and safe
  handling of partial/corrupt lines.
- The event collector should persist before publishing, assign monotonic IDs,
  and apply the existing AgentGuard redaction boundary.
- The first valuable UI is a run list → run timeline → event detail drawer,
  backed by deterministic built-in scenarios and a minimal external ingestion
  path.

## Sources

- FastAPI SSE tutorial: <https://fastapi.tiangolo.com/tutorial/server-sent-events/>
- FastAPI SSE reference: <https://fastapi.tiangolo.com/reference/sse/>
- MDN EventSource: <https://developer.mozilla.org/en-US/docs/Web/API/EventSource>
- Vite guide: <https://vite.dev/guide/>
- JSON Lines specification: <https://jsonlines.org/>
