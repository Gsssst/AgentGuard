# Milestones

## v0.3 LangGraph Adapter (Shipped: 2026-09-04)

**Scope:** Phase 7–10  
**Completed:** 4 phases, 10 plans, 31 tasks  
**Requirements:** 22/22 satisfied  
**Verification:** 136 automated tests passed; 8/8 Phase 10 threats closed

### Key Accomplishments

- Added an optional LangGraph/LangChain integration without adding those dependencies to AgentGuard core.
- Introduced fail-closed `GuardedToolNode` and `ToolGuard` contracts for adapter-owned tools.
- Added bounded multi-tool concurrency with resource-lock coordination, failure isolation, stable ordering, and original call-ID preservation.
- Bridged per-call approval to public LangGraph `interrupt()` / `Command(resume=...)` with redacted projections and digest-bound decisions.
- Verified real `StateGraph`/`MemorySaver` integration and a deterministic fault matrix.
- Closed the standard `MessagesState + add_messages` duplicate-result blocker in Phase 10.

### Known Technical Debt

- Adapter-side validation and approval requests do not yet produce a complete Runtime audit-event timeline.
- Original approval arguments remain in checkpoint state for digest recomputation; the interrupt projection is redacted.
- Compatibility evidence is bounded to Python 3.12.9, LangGraph 0.6.11, and LangChain Core 0.3.86.
- Graph-level LoopGuard and terminal ReliabilityReport integration remain future work.
- Process-local locks and at-least-once execution semantics remain explicit limits.

**Archives:**

- [Roadmap](milestones/v0.3-ROADMAP.md)
- [Requirements](milestones/v0.3-REQUIREMENTS.md)
- [Milestone audit](milestones/v0.3-MILESTONE-AUDIT.md)

---

