---
phase: 11
phase_name: event-contract-and-collector
project: AgentGuard
generated: 2026-09-06
language: en
paired_record: 11-LEARNINGS.md
---

# Phase 11 Learning Record: Event Contract and Collector

This record describes only behavior demonstrated by code and automated tests. Phase 11 establishes a process-local, bounded observability boundary; it is not a distributed log, an exactly-once event bus, or a production high-availability platform. The paired Chinese record is [11-LEARNINGS.md](./11-LEARNINGS.md).

## 1. Problem and Phase Boundary

The v0.3 `RuntimeEvent` is an internal compatibility event: the CLI, legacy sinks, reports, and existing tests depend on its free-form `data` shape. Rewriting it for the Console would break those consumers. Phase 11 therefore adds a strict `agentguard.event.v1` normalizer and `EventCollector` behind it, projecting Runtime and LangGraph Adapter facts into one safe timeline (D-01–D-05, D-10).

This phase owns only the event contract, correlation identity, process-local collection, and summaries. v1 JSONL history and REST belong to Phase 12, SSE and external ingestion to Phase 13, and the React Console/browser interaction to Phase 14. Web approval controls, authentication, and RBAC come later.

## 2. Design and Implementation Tradeoffs

### 2.1 Strict v1 Envelope (D-01–D-05)

`EventEnvelope` has a fixed schema, run/call correlation, Collector sequence, occurrence/receipt times, event status, payload, and extensions; inapplicable correlation fields are explicit `null` values (D-02, D-03). Each of the 23 `EventType` values has an explicit payload allowlist. Unknown fields are not silently moved into `extensions`, which currently admits only source sequence evidence (D-01, D-04). Malformed data goes to bounded diagnostics rather than the normal timeline and cannot propagate from `EventSink.emit()` into the observed Agent (D-05).

Keeping `RuntimeEvent` and adding a second boundary costs an extra mapping layer. It preserves COMPAT-01 for existing callers and prevents the future Web layer from becoming a core dependency.

### 2.2 Internal and External Call Identity (D-06–D-10)

Internal `call_id` is the logical-call key; external `tool_call_id` is nullable, repeatable source evidence (D-06). Sequential Runtime calls derive a stable UUID5 from non-secret `run_id + step`. LangGraph creates one real `batch_id` when an AIMessage begins and distinct call IDs from original input positions. Arguments, exceptions, actors, and approval reasons never contribute to identifiers.

Runtime attempt/retry callbacks close over one correlation value. LangGraph `_agentguard_prepared` stores run ID, batch ID, call ID, valid external ID, and original index, then reuses them after approval resume (D-07–D-10). Invalid external IDs only produce local placeholders for Agent-visible messages; they do not enter the envelope's `tool_call_id`.

### 2.3 Collector Order and Run State (D-11–D-15, D-19–D-21)

Source `data.sequence` survives only as `extensions.source_sequence`. Authoritative order is allocated by the Collector inside a short `threading.Lock` transaction: terminal check, sequence allocation, append, and immutable summary replacement (D-11, D-12). Identical content, repeated source sequence, or earlier occurrence time is still retained in receipt order; there is no silent deduplication or historical insertion (D-13, D-14).

Tool failure, timeout, denial, and failed batches do not terminate a run. Only `run_finished` can enter completed/failed/cancelled (D-19, D-20). If a tool event arrives first, the summary truthfully sets `incomplete_start=true` without inventing a start time or duration; a valid late start only backfills start time (D-21). A terminal run ID cannot be resurrected and a new run needs a new ID (D-15).

### 2.4 Safe Preview and Bounded Retention (D-16–D-18)

Arguments and results cross v1 only through recursively redacted, detached previews with depth, node, collection, and string budgets. Sensitive field names such as password, token, secret, API key, and authorization are replaced before their values are traversed; truncation is explicit (D-16). Raw exception messages, stacks, checkpoint paths, loop signatures, and approval reasons are discarded. Failures retain only type, category, attempt count, timeout metadata, and fixed summaries (D-18). v0.4 has no switch that disables redaction or exposes raw values (D-17).

An important boundary is that redaction recognizes sensitive field names; it does not scan every ordinary string for arbitrary secrets. If a credential is placed under a generic key such as `value`, the system does not claim reliable discovery. Callers should use structured sensitive fields and avoid sending raw data to telemetry.

## 3. Deliberate Faults, Observations, and Root Causes

| Deliberate fault | Observation | Fix or confirmed boundary |
|---|---|---|
| Nested secrets, deep/wide collections, cycles, NaN, bytes, and hostile objects | Shallow redaction could leak or produce unbounded/non-JSON data | `_safety.safe_preview()` redacts by sensitive key before enforcing depth, item, node, and string budgets; it never calls arbitrary `repr/str` (D-16, D-17) |
| Exception messages containing tokens, file paths, and newlines | Legacy `RuntimeEvent.data.error_message` can carry raw text | The normalizer drops error/stack/path/reason and emits fixed `safe_summary`; contract and LangGraph tests assert sentinels are absent (D-18) |
| `batch_id` used as `run_id` | One logical run would split into synthetic batch runs | Runtime and Adapter now separate the true run ID and shared batch ID; `test_event_correlation.py` proves they differ (D-08) |
| Retry, approval resume, and crash replay regenerate identity | One logical call would fragment in the Console | Producers generate/store call ID once and reuse it for attempts, approval, and resume (D-06–D-10) |
| Submit source sequence 99, then 1, then 1 again | Trusting source order would reorder or lose facts | Collector assigns 1, 2, 3 in acceptance order; source values remain evidence only (D-11–D-14) |
| Send `run_started` after terminal completion | Forgetting identity could resurrect a finished run | Reject with `run_already_terminal`; terminal identity remains reserved for the Collector lifetime (D-15) |
| Exceed run, event-deque, and diagnostic limits | Unbounded storage grows memory; silent trimming pretends history is complete | New runs reject safely; total versus retained counts/ranges stay explicit and diagnostics are bounded |
| Make normalizer/commit raise a secret-bearing error and let normalizer re-enter reads | Calling under the lock could deadlock; raw failures could stop the Agent | Clock/normalizer run outside the lock; `emit()` catches `Exception` and stores only fixed diagnostic codes |
| LangGraph unknown/missing-guard/approval branches return only `ToolMessage` | Early returns were invisible to the Collector | Adapter emits strict facts through `Runtime.emit_framework_event()`; subset batch boundaries are suppressed and the original AIMessage owns one boundary pair |
| Put a secret in an ordinary `value` string in the new test | The test exposed that key-based redaction is not content scanning | We did not invent arbitrary-secret detection; the test uses token/password fields and this limitation is explicit here |

## 4. LangGraph Approval and Compatibility Evidence

`tests/integration/test_langgraph_observability.py` uses public `StateGraph`, `MessagesState`, `MemorySaver`, `Command(resume=...)`, and a stable `configurable.thread_id`. A mixed direct/pending batch has one `batch_started` before suspension and one `batch_finished` only after resume. The direct tool executes exactly once; pending work executes only after explicit approval. Each original input yields one input-ordered final `ToolMessage`, and valid external IDs remain unchanged.

The combined new and existing LangGraph tests cover unknown tools, duplicate/invalid external IDs, invalid arguments, missing guards, missing decisions, explicit denial, digest mismatch, missing tools at resume, transient retry, timeout, approved failures, and sibling isolation. Adapter events describe facts only: Runtime still exclusively enforces permission, digest, lock, timeout, and retry controls (T-11-14–T-11-18).

Core `import agentguard` loads neither LangGraph, LangChain Core, FastAPI, nor future Console modules. If the optional integration is absent, its tests skip with an `agentguard[langgraph]` installation hint. This environment proves only Python 3.12.9, `langgraph==0.6.11`, and `langchain-core==0.3.86`.

## 5. Reproducible Test Evidence

Observed on the current worktree on 2026-09-06:

- `PYTHONPATH=src python -m pytest -q tests/integration/test_langgraph_observability.py tests/integration/test_langgraph_approval.py tests/integration/test_langgraph_optional.py -rs -x` → **12 passed with one third-party deprecation warning**.
- `PYTHONPATH=src python -m pytest -q` → **212 passed**.
- `PYTHONPATH=src python -c "import agentguard"` → exit code 0.
- `git diff --check` → exit code 0.

Supporting evidence also includes the 23-event matrix in `tests/unit/test_event_contract.py`, concurrency/state/capacity/failure-isolation tests in `tests/unit/test_event_collector.py`, and retry/approval/checkpoint correlation tests in `tests/integration/test_event_correlation.py`.

## 6. Security Boundary and Capability Limits

- **Process-local:** Collector, locks, and indexes apply only inside the current Python process; there is no cross-process order, shared locking, or HA.
- **At-least-once:** Every accepted arrival remains evidence; there is no exactly-once promise or content-hash deduplication.
- **Bounded retention:** Per-run events, run count, and diagnostics are limited. A timeline may contain only its tail; summaries expose true totals and retained ranges.
- **Safety first:** There is no raw-exception, raw-stack, or disable-redaction debug switch; fixed summaries intentionally trade away detail.
- **Version-bounded:** Evidence covers the pinned LangGraph/LangChain versions and public APIs, not broad framework or historical-version support.
- **Not implemented:** JSONL/REST (Phase 12), SSE/external ingestion (Phase 13), and React supervision UI (Phase 14) are outside this phase. Web approval control, authentication/RBAC, and multi-tenancy are later work.

## 7. Decision Evidence Index (D-01–D-21)

| Decisions | Evidence |
|---|---|
| D-01–D-05 | Strict shape/allowlist rejection in `test_event_contract.py`; fail-open diagnostics in `test_event_collector.py` |
| D-06–D-10 | Call/run/batch identity and resume grouping in `test_event_correlation.py` and `test_langgraph_observability.py` |
| D-11–D-15 | Contiguous concurrent sequence, reverse/repeated source order, and terminal-reuse rejection tests |
| D-16–D-18 | Adversarial safe-preview, error sentinel, and core-import isolation tests |
| D-19–D-21 | Nonterminal tool failure, approval transitions, incomplete start, and late-start tests |

---
*Phase: 11-event-contract-and-collector*
*Evidence date: 2026-09-06*
