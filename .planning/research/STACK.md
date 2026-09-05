# v0.4 Stack Research

## Recommendation

Use the existing Python runtime with a small FastAPI service, native SSE
responses, a React + Vite frontend, and JSONL append-only history. Do not add a
database, WebSocket broker, or external event bus in v0.4.

## Findings

### FastAPI SSE

Current FastAPI documentation exposes `EventSourceResponse` and
`ServerSentEvent`. Events can carry JSON data plus `event`, `id`, `retry`, and
`comment` fields. A generator-based endpoint is enough for the local console;
`id` and `retry` provide the minimum contract for reconnectable streams.

Source: <https://fastapi.tiangolo.com/tutorial/server-sent-events/> and
<https://fastapi.tiangolo.com/reference/sse/>

### Browser transport

The browser `EventSource` API opens a persistent HTTP connection and receives
unidirectional events. It automatically attempts reconnection and can send the
last received event ID back to the server. This matches a monitoring console:
the browser sends commands through ordinary HTTP, while runtime events flow
from server to browser.

Source: <https://developer.mozilla.org/en-US/docs/Web/API/EventSource>

### React + Vite

Vite provides a lightweight development server and fast HMR. Its official React
plugin is sufficient for a single-page local console. Keep the frontend as a
separate `web/` package so the Python core remains importable without Node.

Source: <https://vite.dev/guide/> and <https://vite.dev/guide/features>

### JSONL

JSON Lines stores one valid UTF-8 JSON value per line and is naturally suited to
append-only logs and Unix-style processing. Every event should end with a
newline. JSONL is a file format, not a query engine, so v0.4 should use bounded
in-memory indexes for recent runs and scan files only for basic history reads.

Source: <https://jsonlines.org/>

## Version and Dependency Boundary

- Keep Python compatibility aligned with the existing project.
- Add FastAPI/Uvicorn only to a console/server extra if they are not already
  present in the environment.
- Pin or document the Vite/React versions used by the checked-in frontend.
- Treat SSE as HTTP/1.1-compatible one-way transport; no WebSocket dependency.

## Rejected Additions

- Redis, Kafka, RabbitMQ, or a hosted telemetry backend: no demonstrated
  cross-process requirement yet.
- SQLite/PostgreSQL: historical query needs are small enough for JSONL in this
  milestone.
- OpenTelemetry: useful later, but it would introduce a second event model
  before AgentGuard's own event contract is stable.
