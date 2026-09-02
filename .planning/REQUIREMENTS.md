# Requirements: AgentGuard v0.3 LangGraph Adapter

**Defined:** 2026-09-02  
**Core Value:** An Agent Runtime must terminate, remain bounded, and leave enough evidence to explain what happened when tools fail or the agent repeats itself.

## v0.3 Requirements

### Adapter Foundation

- [x] **ADAPTER-01**: A developer can install LangGraph support as an optional extra while the AgentGuard core package remains importable without LangGraph.
- [x] **ADAPTER-02**: A developer can use `GuardedToolNode` to connect LangChain-compatible tools to AgentGuard.
- [x] **ADAPTER-03**: A developer can configure each LangChain tool through `ToolGuard` with capabilities, resources, timeout, retry, and approval metadata.
- [x] **ADAPTER-04**: A tool without a `ToolGuard` configuration is denied without invoking the underlying tool.
- [x] **ADAPTER-05**: A configured tool call passes through AgentGuard permission, timeout, retry, resource-lock, and audit boundaries.
- [x] **ADAPTER-06**: Every success or failure result becomes a structured `ToolMessage` carrying the original `tool_call_id`.

### Multi-Tool Calls

- [ ] **BATCH-01**: `GuardedToolNode` can process multiple `tool_calls` from one `AIMessage`.
- [ ] **BATCH-02**: Independent calls can execute concurrently while conflicting calls obey AgentGuard resource-lock semantics.
- [ ] **BATCH-03**: Failure of one call does not automatically cancel other independent calls.
- [ ] **BATCH-04**: Returned `ToolMessage` objects preserve input call order and each original call ID.
- [ ] **BATCH-05**: Permission denial, timeout, retry exhaustion, lock timeout, and unknown-tool outcomes are represented as structured messages.

### Approval Bridge

- [ ] **APPROVAL-01**: Approval-required tool calls pause through LangGraph `interrupt` before the underlying tool is invoked.
- [ ] **APPROVAL-02**: The interrupt payload contains only redacted tool information, an argument summary, the `tool_call_id`, and an action digest.
- [ ] **APPROVAL-03**: Approval resumes through `Command(resume=...)`, with LangGraph owning checkpoint persistence and graph recovery state.
- [ ] **APPROVAL-04**: A reviewer can approve or reject each pending call independently by `tool_call_id`.
- [ ] **APPROVAL-05**: Resume recomputes the action digest and refuses execution when the call arguments no longer match the approved action.
- [ ] **APPROVAL-06**: Only approved calls execute; rejected calls return structured `ToolMessage` results.

### Compatibility and Evidence

- [x] **COMPAT-01**: Importing the adapter without optional dependencies produces an actionable installation message rather than an unexplained `ModuleNotFoundError`.
- [x] **COMPAT-02**: Deterministic fake tools and message fixtures test adapter behavior without a real LLM service.
- [x] **COMPAT-03**: Real LangGraph integration tests run when the optional dependencies are installed and otherwise skip with a clear reason.
- [ ] **COMPAT-04**: Automated tests cover success, denial, timeout, retry exhaustion, lock conflict, approval, and digest-mismatch scenarios.
- [x] **COMPAT-05**: Chinese and English learning notes record implementation decisions, deliberate failures, and known limits.

## Future Requirements

- Framework-neutral adapter protocol shared by multiple Agent frameworks.
- Full graph factory and higher-level graph construction helpers.
- Streaming tool progress and event propagation into LangGraph streams.
- Dependency-aware DAG execution for tool batches.
- Cross-process or distributed resource coordination.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Replacing LangGraph routing or checkpointing | LangGraph remains the authoritative graph runtime and persistence owner. |
| Supporting every historical LangGraph version | v0.3 will document and test a bounded compatible version range. |
| Real LLM provider calls | Deterministic tool-call messages are sufficient to validate the adapter boundary. |
| Automatic inference of tool capabilities or resources | Guard configuration remains explicit and fail-closed. |
| Distributed locks or exactly-once execution | Existing AgentGuard guarantees are process-local and at-least-once-aware. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ADAPTER-01..06 | Phase 7 | Complete |
| COMPAT-01..03, COMPAT-05 | Phase 7 | Complete |
| COMPAT-04 | Phase 9 | Pending |
| BATCH-01..05 | Phase 8 | Pending |
| APPROVAL-01..06 | Phase 9 | Pending |

**Coverage:**
- v0.3 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-02*
*Last updated: 2026-09-02 after v0.3 scope confirmation*
