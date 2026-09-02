# LangGraph Adapter Pitfalls Research

| Pitfall | Prevention |
|---|---|
| Assuming `ToolNode` input/output shapes without testing the supported LangGraph version | Add clean-environment integration tests and keep translation code isolated. |
| Losing `tool_call_id` or returning plain strings | Always emit `ToolMessage` with the original ID and a stable content schema. |
| Calling tools before checking permissions or approval | Normalize and guard every call before invocation; missing configuration fails closed. |
| Maintaining a second checkpoint/resume store | Use LangGraph checkpointer and `interrupt/resume`; AgentGuard only binds approval evidence to the action digest. |
| Resuming approval after arguments changed | Recompute and compare the canonical digest; reject mismatches. |
| Letting one failed call cancel unrelated calls | Use independent result collection and preserve input order. |
| Treating a timeout as proof that a synchronous worker stopped | Preserve existing AgentGuard timeout semantics and document possible background completion. |
| Importing optional dependencies at package import time | Lazy import the adapter and raise an actionable installation error. |
| Overpromising compatibility across rapidly changing LangGraph APIs | Pin/test a supported range and document the tested version. |
