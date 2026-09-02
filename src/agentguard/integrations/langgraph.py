"""LangGraph adapter for AgentGuard guarded Tool execution.

LangGraph and LangChain Core remain optional dependencies. Importing this
module without the extra produces an actionable installation message.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

try:
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.runnables import RunnableConfig
except ImportError as exc:  # pragma: no cover - exercised in subprocess tests
    raise ImportError(
        "LangGraph adapter requires optional dependencies; install with "
        "`pip install 'agentguard[langgraph]'`."
    ) from exc

from agentguard.domain.actions import CallTool
from agentguard.domain.results import FailureKind, ToolResult, ToolResultStatus
from agentguard.runtime.engine import Runtime
from agentguard.runtime.policy import RetrySafety
from agentguard.runtime.resources import ResourceAccess
from agentguard.runtime.tool import Tool


@dataclass(frozen=True)
class ToolGuard:
    """Explicit AgentGuard metadata for one LangChain Tool."""

    capabilities: frozenset[str] = frozenset()
    resources: Mapping[str, ResourceAccess | str] = field(default_factory=dict)
    timeout: float | None = None
    retry_safety: RetrySafety = RetrySafety.UNKNOWN
    approval_required: bool = False

    def __post_init__(self) -> None:
        normalized = Tool(
            name="guard-validation",
            function=lambda: None,
            capabilities=self.capabilities,
            resources=self.resources,
            timeout=self.timeout,
            retry_safety=self.retry_safety,
        )
        object.__setattr__(self, "capabilities", normalized.capabilities)
        object.__setattr__(self, "resources", normalized.resources)
        if not isinstance(self.approval_required, bool):
            raise TypeError("approval_required must be a boolean")


def _safe_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _error_content(result: ToolResult) -> str:
    safe_messages = {
        FailureKind.TIMEOUT: "tool execution exceeded its deadline",
        FailureKind.CANCELLED: "tool execution was cancelled",
        FailureKind.RESOURCE_LOCK_TIMEOUT: "tool resource lock timed out",
        FailureKind.TRANSIENT: "tool failed with a transient error",
        FailureKind.PERMANENT: "tool execution was rejected or failed",
    }
    payload = {
        "error": result.error_type or "ToolError",
        "message": safe_messages.get(result.failure_kind, "tool call failed"),
        "failure_kind": result.failure_kind.value if result.failure_kind else None,
        "attempts": result.attempts,
    }
    return _safe_content(payload)


def _tool_name(tool: Any) -> str:
    name = getattr(tool, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("LangChain tools must expose a non-empty name")
    return name.strip()


class GuardedToolNode:
    """A LangGraph-compatible node for one tool-calling AIMessage."""

    def __init__(
        self,
        tools: list[Any] | tuple[Any, ...],
        *,
        runtime: Runtime,
        guards: Mapping[str, ToolGuard],
        messages_key: str = "messages",
    ) -> None:
        if not isinstance(runtime, Runtime):
            raise TypeError("runtime must be an AgentGuard Runtime")
        if not isinstance(messages_key, str) or not messages_key.strip():
            raise ValueError("messages_key must be a non-empty string")
        self.runtime = runtime
        self.messages_key = messages_key
        self._tools: dict[str, Any] = {}
        for tool in tools:
            name = _tool_name(tool)
            if name in self._tools:
                raise ValueError(f"duplicate adapter tool name: {name}")
            if runtime.executor.get_tool(name) is not None:
                raise ValueError(f"adapter tool conflicts with Runtime registry: {name}")
            self._tools[name] = tool
        self._guards = dict(guards)

    async def __call__(self, state: Mapping[str, Any], config: RunnableConfig | None = None) -> dict[str, list[Any]]:
        messages = state.get(self.messages_key) if isinstance(state, Mapping) else None
        if not isinstance(messages, (list, tuple)) or not messages:
            return {"messages": [self._failure_message("MissingMessages", "no messages available")]} 
        ai_message = next(
            (
                message
                for message in reversed(messages)
                if getattr(message, "tool_calls", None)
                and (
                    isinstance(message, AIMessage)
                    or message.__class__.__name__ in {"AIMessage", "FakeAIMessage"}
                )
            ),
            None,
        )
        if ai_message is None:
            return {"messages": [self._failure_message("MissingToolCalls", "no tool-calling AIMessage available")]}
        calls = list(ai_message.tool_calls)
        if len(calls) != 1:
            return {
                "messages": [
                    self._failure_message(
                        "MultipleToolCalls", "Phase 8 adds multi-tool batch execution"
                    )
                ]
            }
        call = calls[0]
        tool_call_id = str(call.get("id", ""))
        name = str(call.get("name", ""))
        args = call.get("args", {})
        guard = self._guards.get(name)
        if guard is None:
            return {"messages": [self._failure_message("PermissionDenied", f"tool '{name}' has no ToolGuard", tool_call_id)]}
        lang_tool = self._tools.get(name)
        if lang_tool is None:
            return {"messages": [self._failure_message("UnknownTool", f"unknown tool: {name}", tool_call_id)]}
        run_id = self._run_id(config)
        adapter_tool = Tool(
            name=name,
            function=self._invoke_langchain_tool(lang_tool),
            timeout=guard.timeout,
            retry_safety=guard.retry_safety,
            capabilities=guard.capabilities,
            resources=guard.resources,
        )
        result = await self.runtime.execute_explicit_tool(CallTool(name, args), adapter_tool, run_id=run_id, step=0)
        if result.status is ToolResultStatus.SUCCESS:
            content = _safe_content(result.value)
        else:
            content = _error_content(result)
        return {"messages": [ToolMessage(content=content, tool_call_id=tool_call_id)]}

    def _run_id(self, config: Mapping[str, Any] | None) -> str:
        if isinstance(config, Mapping):
            configurable = config.get("configurable")
            if isinstance(configurable, Mapping):
                value = configurable.get("run_id")
                if isinstance(value, str) and value.strip():
                    return value
            value = config.get("run_id")
            if isinstance(value, str) and value.strip():
                return value
        return f"langgraph-{uuid.uuid4().hex}"

    @staticmethod
    def _failure_message(error_type: str, message: str, tool_call_id: str = "") -> ToolMessage:
        content = _safe_content({"error": error_type, "message": message})
        return ToolMessage(content=content, tool_call_id=tool_call_id or "agentguard-missing")

    @staticmethod
    def _invoke_langchain_tool(lang_tool: Any):
        async def invoke(**kwargs: Any) -> Any:
            ainvoke = getattr(lang_tool, "ainvoke", None)
            if callable(ainvoke):
                return await ainvoke(kwargs)
            invoke_method = getattr(lang_tool, "invoke", None)
            if callable(invoke_method):
                return await asyncio.to_thread(invoke_method, kwargs)
            raise TypeError("LangChain Tool must expose ainvoke() or invoke()")

        return invoke


__all__ = ["GuardedToolNode", "ToolGuard"]
