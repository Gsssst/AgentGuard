# LangGraph Adapter Stack Research

**Scope:** v0.3 `GuardedToolNode` integration.

## Findings

- LangGraph exposes prebuilt tool execution through `langgraph.prebuilt.ToolNode`.
- Tool calls and results use LangChain Core message types, especially `AIMessage.tool_calls` and `ToolMessage`.
- Human-in-the-loop pauses are represented with `langgraph.types.interrupt`; a later invocation resumes with `Command(resume=...)` while LangGraph's checkpointer persists graph state.
- LangGraph nodes receive a state object and optional `RunnableConfig`; the adapter should preserve these inputs and avoid inventing a second graph checkpoint protocol.

## Dependency recommendation

Use an optional extra containing `langgraph` and `langchain-core`. Exact compatible versions should be selected during implementation against the supported Python version and tested in a clean environment. This repository currently does not have either package installed, so version compatibility is not claimed yet.

## What not to add

- Do not make LangGraph a core dependency.
- Do not replace LangGraph's checkpointer or graph scheduler.
- Do not import private LangGraph modules when public `ToolNode`, `interrupt`, `Command`, and message APIs are sufficient.
