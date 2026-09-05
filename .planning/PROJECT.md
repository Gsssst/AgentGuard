# AgentGuard

## What This Is

AgentGuard is a learning-first, open-source reliability control and fault-injection toolkit for Agent Runtimes. Through v0.3 it provides a Python library and CLI for deterministic Agent execution, guarded tool boundaries, recovery evidence, permissions, resource-aware concurrency, and an optional LangGraph adapter with digest-bound human approval.

## Core Value

An Agent Runtime must terminate, remain bounded, and leave enough evidence to explain what happened when tools fail or the agent repeats itself.

## Current State

**Shipped:** v0.3 LangGraph Adapter on 2026-09-04.

- 22/22 v0.3 requirements verified.
- 136 automated tests passing.
- Optional LangGraph 0.6.11 / LangChain Core 0.3.86 integration.
- Multi-tool concurrency, resource locking, permission boundaries, safe structured failures, and digest-bound approval resume.
- Standard `MessagesState + add_messages` pause/resume flow verified with one ordered final result per call.

## Current Milestone: v0.4 Agent Observability Console

**Goal:** Add a local Web console that lets AgentGuard developers observe and replay Agent tool execution, approvals, failures, and retries.

**Target features:**

- FastAPI local service with SSE event streaming.
- React + Vite run list, run detail timeline, and event detail drawer.
- In-memory live state with JSONL history persistence.
- Built-in deterministic test scenarios plus a small external SDK/API ingestion path.
- Read-only approval status in v0.4; UI approve/deny is deferred to a later minor release.

**Explicit boundaries:** No database, WebSocket, login, multi-tenancy, or production HA in this milestone.

## Requirements

### Validated

- ✓ Deterministic scripted Agent Loop with explicit termination reasons — v0.1 Phases 1–3
- ✓ Bounded timeout, cancellation, retry, and idempotency boundaries — v0.1 Phase 2
- ✓ Loop detection, step/time budgets, and reliability reporting — v0.1 Phase 3
- ✓ Local checkpoint/resume, crash recovery evidence, and evaluation scenarios — v0.2 Phase 4
- ✓ Capability permissions, approval pauses, digest binding, and audit redaction — v0.2 Phase 5
- ✓ Process-local resource locks and explicit batch concurrency — v0.2 Phase 6
- ✓ Optional LangGraph integration with explicit fail-closed Tool guards — v0.3 Phase 7
- ✓ Ordered, failure-isolated multi-tool execution through Runtime controls — v0.3 Phase 8
- ✓ Redacted, digest-bound per-call LangGraph interrupt/resume approvals — v0.3 Phase 9
- ✓ Standard MessagesState approval results without duplicate ToolMessages — v0.3 Phase 10

### Active

v0.4 requirements will be defined and traced in `.planning/REQUIREMENTS.md`.

### Out of Scope

- Java Control Plane in V0.1 — defer until Runtime semantics are validated.
- RabbitMQ and Redis in V0.1 — no cross-process scheduling or distributed state is needed yet.
- Production authentication, multi-tenancy, and HA — defer until a local monitoring/testing console proves the interaction model.
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
| Target Runtime developers first | Matches the core problem and maximizes learning focus | ✓ Good |
| Scripted Agent first, LLM adapter later | Makes failure behavior deterministic and debuggable | ✓ Good |
| Python library + CLI for V0.1 | Minimizes unrelated distributed-system complexity | ✓ Good |
| Interactive, sequential workflow | Preserves understanding and debugging checkpoints | ✓ Good |
| Planning docs tracked in Git | Keeps architectural reasoning and scope history auditable | ✓ Good |
| LangGraph remains the workflow owner | Avoids competing checkpoint and routing state between the adapter and AgentGuard | ✓ Good |
| Adapter is exposed as `GuardedToolNode` | Minimizes changes for existing LangGraph `ToolNode` users | ✓ Good |
| Unconfigured tools fail closed | Prevents accidental bypass of capability and approval controls | ✓ Good |
| LangGraph is an optional dependency | Keeps the core AgentGuard package lightweight for non-LangGraph users | ✓ Good |
| Pending approval state is separate from messages | Prevents `add_messages` from retaining approval placeholders beside final results | ✓ Good |
| Compatibility claims are evidence-bounded | Avoids implying untested LangGraph or Python support | ✓ Good |

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
*Last updated: 2026-09-04 after starting v0.4 Agent Observability Console*
