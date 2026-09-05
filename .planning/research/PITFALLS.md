# v0.4 Pitfalls and Prevention

| Pitfall | Consequence | Prevention |
|---|---|---|
| Publishing before JSONL append | Live UI shows an event that history cannot replay | Append and flush the validated event before publishing |
| Unbounded subscriber queues | A slow browser consumes memory | Bound queues; disconnect or coalesce slow clients |
| Missing SSE IDs | Reconnect duplicates or loses events | Use monotonic per-run sequence IDs and dedupe by ID in the client |
| Treating SSE as bidirectional | Approval/control commands become hidden in the stream | Use ordinary REST POSTs for commands; SSE is read-only in v0.4 |
| Partial JSONL writes | One malformed line breaks history loading | Write one serialized line under a lock, tolerate/flag a trailing partial line |
| Raw arguments or exceptions in UI | Secrets or internal stack traces leak | Reuse AgentGuard redaction and safe error-summary helpers |
| Mixing wall-clock and monotonic time | Durations and ordering become confusing | Persist UTC timestamps; calculate durations from Runtime evidence |
| CORS/dev proxy mismatch | Frontend cannot connect to local API | Configure one documented Vite proxy and test the production-like served path |
| Reading the whole log per request | History latency grows with every run | Maintain a bounded run index and add explicit pagination later |
| Assuming process restart durability is HA | Users overestimate reliability | Document JSONL local durability and process-local live subscribers |

## Test Matrix

- Event envelope validation and redaction.
- Append/reload round trip, including a truncated final line.
- SSE receives ordered IDs and reconnects from `Last-Event-ID`.
- Slow subscriber is bounded and isolated from the producer.
- Built-in scenarios emit success, retry, timeout, approval, denial, and final
  failure events.
- External ingestion rejects malformed or unsafe events.
- React run list and detail view render the same fixture events as the API.
