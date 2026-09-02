# AgentGuard

## What This Is

AgentGuard is a learning-first, open-source reliability control and fault-injection toolkit for Agent Runtimes. V0.1 targets Agent Runtime developers and provides a small Python library plus CLI for running deterministic scripted agents, constraining tool execution, and producing explainable run evidence.

## Core Value

An Agent Runtime must terminate, remain bounded, and leave enough evidence to explain what happened when tools fail or the agent repeats itself.

## Current Milestone: v0.3 LangGraph Adapter

**Goal:** Integrate AgentGuard's guarded tool execution boundaries into LangGraph through an optional `GuardedToolNode`, while leaving graph state and checkpoint ownership with LangGraph.

**Target features:**
- Optional LangGraph/LangChain Core dependency and clear installation boundary.
- `GuardedToolNode` wrapping LangChain tools with explicit capabilities, resources, timeout, retry, and approval configuration.
- Multi-tool-call execution with structured `ToolMessage` results and LangGraph `interrupt/resume` approval bridging.

## Requirements

### Validated

- ✓ Deterministic scripted Agent Loop with explicit termination reasons — v0.1 Phases 1–3
- ✓ Bounded timeout, cancellation, retry, and idempotency boundaries — v0.1 Phase 2
- ✓ Loop detection, step/time budgets, and reliability reporting — v0.1 Phase 3
- ✓ Local checkpoint/resume, crash recovery evidence, and evaluation scenarios — v0.2 Phase 4
- ✓ Capability permissions, approval pauses, digest binding, and audit redaction — v0.2 Phase 5
- ✓ Process-local resource locks and explicit batch concurrency — v0.2 Phase 6

### Active

- [ ] Provide an optional LangGraph integration without making LangGraph a core dependency.
- [ ] Expose a `GuardedToolNode` that accepts LangChain tools plus explicit per-tool guard configuration.
- [ ] Preserve LangGraph as the owner of graph state, routing, checkpoint, and interrupt/resume state.
- [ ] Route tool execution through AgentGuard permission, timeout, retry, resource-lock, and audit boundaries.
- [ ] Support multiple tool calls with input-order results and structured `ToolMessage` failures.
- [ ] Bridge approval-required calls through LangGraph `interrupt/resume` with digest-bound decisions.
- [ ] Maintain bilingual learning notes and deterministic adapter tests, including deliberate failure scenarios.

### Out of Scope

- Java Control Plane in V0.1 — defer until Runtime semantics are validated.
- RabbitMQ and Redis in V0.1 — no cross-process scheduling or distributed state is needed yet.
- Frontend, authentication, multi-tenancy, and production HA — not required to prove the reliability core.
- Full MCP, SubAgents, and Multi-Agent orchestration — these add integration surface before core failure semantics are understood.
- Real LLM execution in the first slice — model nondeterminism would obscure Runtime behavior; an adapter can be added later.
- Copying Pi, Deep Agents, or DeepSeek Harness code — mature systems are references for comparison, not implementation sources.

## Context

The creator is a computer-science master's student targeting Agent/LLM application development, with Java backend and multimodal algorithm tracks as secondary directions. AstraLoom already provides substantial evidence of AI application engineering: FastAPI, PostgreSQL/pgvector, Redis, Celery, RAG, custom tool-calling, HITL, multi-agent workflows, PDF processing, React, and Docker Compose. AgentGuard should therefore complement AstraLoom by going deeper into Runtime reliability rather than building another business Agent.

The project is explicitly learning-first. For each important capability the working loop is: understand the problem, compare designs, implement the smallest slice, deliberately break it, debug it, inspect mature implementations, improve it, and record the trade-offs. Resume claims must be grounded in real code, tests, Git history, and learning notes.

## Constraints

- **Learning**: Do not generate large opaque implementations before the design and failure modes are understood.
- **Scope**: V0.1 is a local Python library and CLI; infrastructure is added only when it solves a demonstrated problem.
- **Determinism**: The first vertical slice uses scripted agents and deterministic fault scenarios so tests are reproducible.
- **Evidence**: Every reliability feature needs automated tests and a learning note describing what broke and why the final design was chosen.
- **Honesty**: No fabricated metrics, users, contributions, or claims of completed work.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Target Runtime developers first | Matches the core problem and maximizes learning focus | — Pending |
| Scripted Agent first, LLM adapter later | Makes failure behavior deterministic and debuggable | — Pending |
| Python library + CLI for V0.1 | Minimizes unrelated distributed-system complexity | — Pending |
| Interactive, sequential workflow | Preserves understanding and debugging checkpoints | — Pending |
| Planning docs tracked in Git | Keeps architectural reasoning and scope history auditable | — Pending |
| LangGraph remains the workflow owner | Avoids competing checkpoint and routing state between the adapter and AgentGuard | — Pending |
| Adapter is exposed as `GuardedToolNode` | Minimizes changes for existing LangGraph `ToolNode` users | — Pending |
| Unconfigured tools fail closed | Prevents accidental bypass of capability and approval controls | — Pending |
| LangGraph is an optional dependency | Keeps the core AgentGuard package lightweight for non-LangGraph users | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Requirements invalidated? Move to Out of Scope with reason.
2. Requirements validated? Move to Validated with phase reference.
3. New requirements emerged? Add to Active.
4. Decisions to log? Add to Key Decisions.
5. Update the product description if reality drifted.

**After each milestone**:
1. Review all sections.
2. Re-check the Core Value.
3. Audit Out of Scope reasons.
4. Update Context with current evidence and feedback.

---
*Last updated: 2026-09-02 after starting v0.3 LangGraph Adapter*
