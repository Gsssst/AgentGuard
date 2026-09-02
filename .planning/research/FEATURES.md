# LangGraph Adapter Feature Research

## Table stakes

1. Accept LangChain-compatible tools and map them to explicit AgentGuard `ToolGuard` declarations.
2. Consume the current `AIMessage` tool calls and emit one `ToolMessage` per call with the original `tool_call_id`.
3. Preserve input order in returned messages while allowing independent calls to use AgentGuard batch execution.
4. Convert permission, timeout, retry-exhaustion, lock-timeout, and unknown-tool outcomes into safe structured messages.
5. Fail closed when a tool has no guard configuration.
6. Keep graph state/checkpoint ownership in LangGraph.

## Differentiators for this milestone

- Approval-required calls pause through LangGraph `interrupt/resume`.
- Approval decisions are bound to a canonical action digest and checked on resume.
- Existing AgentGuard audit events and reliability reports remain available for adapter calls.
- Deterministic fake LangChain tools and failure scenarios make the integration testable without an LLM provider.

## Deferred

- Full graph factory, automatic DAG scheduling, cross-process locks, streaming token integration, and framework-agnostic message translation beyond LangChain Core.
