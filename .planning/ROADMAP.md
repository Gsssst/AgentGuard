# Roadmap: AgentGuard

## Completed Milestones

- **V0.1 Runtime Reliability Core**: Phases 1–3
- **V0.2 Recovery, Permissions, and Concurrency**: Phases 4–6

## Current Milestone: v0.3 LangGraph Adapter

**Goal:** Integrate AgentGuard's guarded tool execution boundaries into LangGraph through an optional `GuardedToolNode`, while leaving graph state and checkpoint ownership with LangGraph.

**Phases:** 3 | **Requirements:** 22 | **Coverage:** 100%

## Phases

- [ ] **Phase 7: GuardedToolNode Foundation** — Optional dependency boundary, tool normalization, and single-call guarded execution.
- [ ] **Phase 8: Multi-Tool Batch Execution** — Multiple `tool_calls`, concurrency, resource conflicts, and ordered structured results.
- [ ] **Phase 9: Approval Bridge and Compatibility Evidence** — LangGraph interrupt/resume approval, digest validation, and integration evidence.

## Phase Details

### Phase 7: GuardedToolNode Foundation

**Goal:** Add the optional dependency boundary, LangChain tool normalization, explicit guard configuration, and single-call structured execution.
**Requirements**: ADAPTER-01, ADAPTER-02, ADAPTER-03, ADAPTER-04, ADAPTER-05, ADAPTER-06, COMPAT-01, COMPAT-02
**Depends on:** Phase 6
**Plans:** TBD

**Success criteria:**
1. Core `import agentguard` works without LangGraph installed, while adapter import provides an actionable extra-install message.
2. A configured LangChain tool executes through AgentGuard permission, timeout, retry, resource-lock, and audit boundaries.
3. An unconfigured tool is denied without invoking its underlying function.
4. Successful and failed single calls produce `ToolMessage` values retaining the original `tool_call_id`.
5. Deterministic fake-tool tests cover the foundation without a real LLM.

### Phase 8: Multi-Tool Batch Execution

**Goal:** Process multiple `AIMessage.tool_calls`, reuse explicit batch concurrency, and return independent ordered results.
**Requirements**: BATCH-01, BATCH-02, BATCH-03, BATCH-04, BATCH-05
**Depends on:** Phase 7
**Plans:** TBD

**Success criteria:**
1. One `AIMessage` with multiple calls produces one result per call in input order.
2. Independent calls can overlap, while calls sharing a declared resource obey lock coordination.
3. A failed or denied call does not cancel unrelated calls in the same batch.
4. Unknown tools, permission denial, timeout, retry exhaustion, and lock timeout are represented as safe structured messages.
5. Every returned message retains the matching original call ID.

### Phase 9: Approval Bridge and Compatibility Evidence

**Goal:** Bridge AgentGuard approval semantics to LangGraph `interrupt/resume`, validate digests, and finish real/fake compatibility evidence and bilingual learning notes.
**Requirements**: APPROVAL-01, APPROVAL-02, APPROVAL-03, APPROVAL-04, APPROVAL-05, APPROVAL-06, COMPAT-03, COMPAT-04, COMPAT-05
**Depends on:** Phase 8
**Plans:** TBD

**Success criteria:**
1. Approval-required calls interrupt before tool invocation with redacted summaries, call IDs, and digests.
2. `Command(resume=...)` resumes through LangGraph's checkpoint and supports independent approve/reject decisions.
3. Digest mismatch on resume prevents execution and yields a structured result.
4. Only approved calls execute; rejected calls yield `ToolMessage` results.
5. Real integration tests run when optional dependencies are installed and otherwise skip clearly; Chinese and English learning notes document failures and limits.

## Historical Phases

### Phase 1: Deterministic Runtime Skeleton
Completed.

### Phase 2: Tool Failure Boundaries
Completed.

### Phase 3: Loop Guard and Reliability Report
Completed.

### Phase 4: Recovery and Evaluation
Completed.

### Phase 5: Permission Control and Approval Boundaries
Completed.

### Phase 6: Resource Locks and Batch Concurrency
Completed.

---
*Roadmap created: 2026-09-02 for milestone v0.3*
