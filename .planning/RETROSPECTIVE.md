# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v0.3 — LangGraph Adapter

**Shipped:** 2026-09-04  
**Phases:** 4  
**Plans:** 10  
**Sessions:** interactive, sequential development

### What Was Built

- Optional LangGraph/LangChain adapter with fail-closed `GuardedToolNode` and explicit `ToolGuard` metadata.
- Runtime-owned bounded batch execution with concurrency, resource locks, ordered results, and per-call failure isolation.
- Redacted, digest-bound LangGraph interrupt/resume approval for independent tool calls.
- Real `StateGraph`/`MemorySaver` compatibility evidence and a deterministic fault matrix.
- Phase 10 fix for duplicate approval results under `MessagesState + add_messages`.

### What Worked

- Keeping LangGraph as the graph/checkpoint owner avoided a competing persistence model.
- Explicit adapter-owned Tool pairs allowed Runtime reliability controls to be reused without mutating the global registry.
- Deliberate failure reproduction exposed the reducer-specific approval bug before release.
- Bilingual learning notes kept design decisions and limits inspectable.

### What Was Inefficient

- Historical GSD state and milestone tooling counted all repository phases instead of the v0.3 scope; the archive required manual scope correction.
- Standardized verification artifacts were introduced late, so Phase 8/9 needed discovery aliases.
- Approval audit events and graph-level reliability reporting were left as technical debt rather than designed into the first adapter contract.

### Patterns Established

- Split replay-sensitive work into `prepare()` and `approval()` nodes.
- Keep pending machine state out of user-visible `MessagesState` updates.
- Normalize untrusted resume data per call and fail closed on missing, malformed, denied, or digest-mismatched entries.
- Use input indexes as the merge key while preserving original `tool_call_id` values.

### Key Lessons

1. A passing plain-list graph test is insufficient for LangGraph integrations; reducer semantics need a real `MessagesState` regression.
2. Approval payloads should be redacted for humans while digest verification uses the original canonical arguments inside a trusted checkpoint boundary.
3. Compatibility claims should name exact tested versions and avoid implying broad framework support.
4. Milestone scope must be explicit when a repository contains historical phases and inserted closure phases.

### Cost Observations

- Model mix: not recorded by the local workflow.
- Sessions: not automatically tracked.
- Notable: the interactive, one-question-at-a-time workflow reduced opaque implementation and made the B1 regression easy to reason about.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v0.3 | interactive | 4 scoped | Added framework adapter, approval bridge, and real reducer compatibility evidence |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v0.3 | 136 passed | requirements 22/22 | LangGraph remains optional |

### Top Lessons (Verified Across Milestones)

1. Deterministic fault injection and explicit failure kinds make reliability behavior explainable.
2. Small typed contracts and evidence-first tests expose integration boundaries earlier than large end-to-end implementations.

