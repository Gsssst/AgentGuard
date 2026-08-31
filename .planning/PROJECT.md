# AgentGuard

## What This Is

AgentGuard is a learning-first, open-source reliability control and fault-injection toolkit for Agent Runtimes. V0.1 targets Agent Runtime developers and provides a small Python library plus CLI for running deterministic scripted agents, constraining tool execution, and producing explainable run evidence.

## Core Value

An Agent Runtime must terminate, remain bounded, and leave enough evidence to explain what happened when tools fail or the agent repeats itself.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Run a deterministic scripted Agent Loop without requiring a real LLM.
- [ ] Execute tools with bounded timeout, cancellation, and retry behavior.
- [ ] Represent tool idempotency and prevent unsafe blind retries.
- [ ] Detect repeated actions and enforce step/time budgets.
- [ ] Emit structured run events that explain success and failure.
- [ ] Provide deterministic fault-injection tools for timeout, delay, failure, and repeated-result scenarios.
- [ ] Expose the first vertical slice through a small Python API and CLI.
- [ ] Maintain learning notes based on implementation, tests, failures, and mature-system comparisons.

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
*Last updated: 2026-08-31 after initialization*
