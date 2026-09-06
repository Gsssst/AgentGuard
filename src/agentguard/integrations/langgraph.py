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
from agentguard.events.contract import EventCorrelation
from agentguard.events.model import EventType
from agentguard.runtime.engine import Runtime
from agentguard.runtime.permission import PermissionDecisionKind, action_digest, redact
from agentguard.runtime.policy import RetrySafety
from agentguard.runtime.resources import ResourceAccess
from agentguard.runtime.tool import Tool
from .approval import ApprovalBatch, ApprovalItem, build_approval_batch, normalize_resume_decisions


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


def _error_content(
    result: ToolResult,
    *,
    tool_call_id: str | None = None,
    invalid_tool_call_id: bool = False,
) -> str:
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
    if invalid_tool_call_id:
        payload["tool_call_id_valid"] = False
        payload["tool_call_id"] = tool_call_id
    return _safe_content(payload)


def _tool_name(tool: Any) -> str:
    name = getattr(tool, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("LangChain tools must expose a non-empty name")
    return name.strip()


class GuardedToolNode:
    """A LangGraph-compatible node for a tool-calling AIMessage.

    One node invocation may contain several independent calls.  Validation
    failures are represented in-place while executable calls are handed to
    ``Runtime.execute_explicit_batch`` so permission, timeout, retry, and
    resource-lock semantics stay in one execution boundary.
    """

    def __init__(
        self,
        tools: list[Any] | tuple[Any, ...],
        *,
        runtime: Runtime,
        guards: Mapping[str, ToolGuard],
        messages_key: str = "messages",
        max_concurrency: int | None = None,
    ) -> None:
        if not isinstance(runtime, Runtime):
            raise TypeError("runtime must be an AgentGuard Runtime")
        if not isinstance(messages_key, str) or not messages_key.strip():
            raise ValueError("messages_key must be a non-empty string")
        Runtime._validate_max_concurrency(max_concurrency)
        self.runtime = runtime
        self.messages_key = messages_key
        self.max_concurrency = max_concurrency
        self._tools: dict[str, Any] = {}
        for tool in tools:
            name = _tool_name(tool)
            if name in self._tools:
                raise ValueError(f"duplicate adapter tool name: {name}")
            if runtime.executor.get_tool(name) is not None:
                raise ValueError(f"adapter tool conflicts with Runtime registry: {name}")
            self._tools[name] = tool
        self._guards = dict(guards)

    async def __call__(self, state: Mapping[str, Any], config: RunnableConfig | None = None) -> dict[str, Any]:
        """Execute a tool-call message, interrupting once for pending calls.

        For replay-sensitive graphs, compose :meth:`prepare` and
        :meth:`approval` as two nodes.  The combined entry point remains
        convenient for batches without approvals and intentionally documents
        LangGraph's at-least-once replay semantics.
        """
        prepared = await self.prepare(state, config)
        context = prepared.get("_agentguard_prepared")
        if not context or not context.get("pending"):
            return {"messages": prepared["messages"]}
        return await self.approval(prepared, config)

    async def prepare(self, state: Mapping[str, Any], config: RunnableConfig | None = None) -> dict[str, Any]:
        """Normalize and execute direct calls, returning approval state.

        The returned projection is plain JSON data and can be carried in graph
        state before entering an interrupting node.  No pending call acquires
        a Runtime resource lock in this stage.
        """
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
        run_id = self._run_id(config)
        calls = list(getattr(ai_message, "tool_calls", ()) or ())
        batch_id = f"langgraph-batch-{uuid.uuid4().hex}"
        correlations = {
            index: EventCorrelation(
                call_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentguard:{run_id}:{batch_id}:{index}")),
                tool_call_id=self._source_tool_call_id(call),
                batch_id=batch_id,
            )
            for index, call in enumerate(calls)
        }
        self.runtime.emit_framework_event(
            EventType.BATCH_STARTED,
            run_id=run_id,
            step=0,
            correlation=EventCorrelation(batch_id=batch_id),
            data={"size": len(calls)},
        )

        # Duplicate detection is deliberately done before dispatch.  Every
        # occurrence is failed in place, so no duplicate can invoke a tool.
        id_counts: dict[str, int] = {}
        for call in calls:
            if isinstance(call, Mapping):
                call_id = call.get("id")
                if isinstance(call_id, str) and call_id.strip():
                    id_counts[call_id] = id_counts.get(call_id, 0) + 1

        immediate: dict[int, tuple[str, ToolResult]] = {}
        executable: list[tuple[int, CallTool, Tool]] = []
        pending: list[tuple[int, str, CallTool, Tool, ToolGuard]] = []
        for index, call in enumerate(calls):
            tool_call_id = self._mapped_tool_call_id(call, index)
            correlation = correlations[index]
            if not isinstance(call, Mapping):
                result = self._failure_result("invalid", "InvalidToolCall")
                immediate[index] = (tool_call_id, result)
                self._emit_rejection(result, run_id=run_id, step=index, correlation=correlation)
                continue

            raw_id = call.get("id")
            if isinstance(raw_id, str) and raw_id.strip() and id_counts.get(raw_id, 0) > 1:
                name = call.get("name") if isinstance(call.get("name"), str) else "invalid"
                result = self._failure_result(name, "DuplicateToolCallId")
                immediate[index] = (tool_call_id, result)
                self._emit_rejection(result, run_id=run_id, step=index, correlation=correlation)
                continue

            name = call.get("name")
            args = call.get("args")
            if not isinstance(name, str) or not name.strip():
                result = self._failure_result("invalid", "InvalidToolCall")
                immediate[index] = (tool_call_id, result)
                self._emit_rejection(result, run_id=run_id, step=index, correlation=correlation)
                continue
            name = name.strip()
            if not isinstance(args, dict):
                result = self._failure_result(name, "InvalidToolCall")
                immediate[index] = (tool_call_id, result)
                self._emit_rejection(result, run_id=run_id, step=index, correlation=correlation)
                continue

            # Existence is checked before guard configuration.  This keeps an
            # unknown name distinguishable from a known but unguarded tool.
            lang_tool = self._tools.get(name)
            if lang_tool is None:
                result = self._failure_result(name, "UnknownTool")
                immediate[index] = (tool_call_id, result)
                self._emit_rejection(result, run_id=run_id, step=index, correlation=correlation)
                continue
            guard = self._guards.get(name)
            if guard is None:
                result = self._failure_result(name, "PermissionDenied")
                immediate[index] = (tool_call_id, result)
                self._emit_permission_denied(
                    name,
                    run_id=run_id,
                    step=index,
                    correlation=correlation,
                )
                continue

            adapter_tool = Tool(
                name=name,
                function=self._invoke_langchain_tool(lang_tool),
                timeout=guard.timeout,
                retry_safety=guard.retry_safety,
                capabilities=guard.capabilities,
                resources=guard.resources,
            )
            action = CallTool(name, args)
            policy_decision = (
                self.runtime.permission_policy.decide(guard.capabilities)
                if self.runtime.permission_policy is not None
                else None
            )
            if policy_decision is not None and policy_decision.kind is PermissionDecisionKind.DENY:
                result = self._failure_result(name, "PermissionDenied")
                immediate[index] = (tool_call_id, result)
                self._emit_permission_denied(
                    name,
                    run_id=run_id,
                    step=index,
                    correlation=correlation,
                    required_capabilities=policy_decision.required_capabilities,
                    forbidden_capabilities=policy_decision.forbidden_capabilities,
                    decision=policy_decision.kind.value,
                )
            elif guard.approval_required or (
                policy_decision is not None
                and policy_decision.kind is PermissionDecisionKind.APPROVAL_REQUIRED
            ):
                pending.append((index, tool_call_id, action, adapter_tool, guard))
                digest = action_digest(
                    action,
                    capabilities=guard.capabilities,
                    run_id=run_id,
                    step=index,
                )
                self.runtime.emit_framework_event(
                    EventType.APPROVAL_REQUESTED,
                    run_id=run_id,
                    step=index,
                    correlation=correlation,
                    data={
                        "tool_name": name,
                        "required_capabilities": sorted(guard.capabilities),
                        "decision": PermissionDecisionKind.APPROVAL_REQUIRED.value,
                        "action_digest": digest,
                        "arguments": redact(action.arguments),
                        "status": "waiting_approval",
                    },
                )
            else:
                executable.append((index, action, adapter_tool))

        executed: tuple[ToolResult, ...] = ()
        if executable:
            executed = await self.runtime.execute_explicit_batch(
                ((action, tool) for _, action, tool in executable),
                run_id=run_id,
                max_concurrency=self.max_concurrency,
                step_indices={position: index for position, (index, _action, _tool) in enumerate(executable)},
                correlation_contexts={position: correlations[index] for position, (index, _action, _tool) in enumerate(executable)},
                batch_id=batch_id,
                emit_batch_lifecycle=False,
            )
        by_index = {index: (self._mapped_tool_call_id(calls[index], index), result)
                    for (index, _, _), result in zip(executable, executed)}
        by_index.update(immediate)
        output: list[ToolMessage] = [
            self._result_message(by_index[index][1], by_index[index][0]) if index in by_index else
            self._failure_message("ApprovalRequired", "approval required before tool execution", self._mapped_tool_call_id(calls[index], index))
            for index in range(len(calls))
        ]
        if not pending:
            self._emit_batch_finished(
                run_id=run_id,
                batch_id=batch_id,
                size=len(calls),
                failed=sum(result.status is not ToolResultStatus.SUCCESS for _, result in by_index.values()),
            )
            return {"messages": output}

        approval_batch = build_approval_batch(
            ((index, call_id, action, guard.capabilities, guard.resources)
             for index, call_id, action, _tool, guard in pending),
            run_id=run_id,
            batch_id=batch_id,
        )
        context = {
            "run_id": run_id,
            "batch_id": batch_id,
            "batch": approval_batch.to_dict(),
            "pending": [
                {
                    "input_index": index,
                    "call_id": correlations[index].call_id,
                    "tool_call_id": correlations[index].tool_call_id,
                    "message_tool_call_id": call_id,
                    "batch_id": batch_id,
                    "run_id": run_id,
                    "tool_name": action.tool_name,
                    "arguments": dict(action.arguments),
                    "capabilities": sorted(guard.capabilities),
                    "resources": {
                        str(key): (value.value if isinstance(value, ResourceAccess) else str(value))
                        for key, value in guard.resources.items()
                    },
                }
                for index, call_id, action, _tool, guard in pending
            ],
            "immediate": {
                str(index): {
                    "tool_call_id": self._mapped_tool_call_id(calls[index], index),
                    "source_tool_call_id": correlations[index].tool_call_id,
                    "call_id": correlations[index].call_id,
                    "batch_id": batch_id,
                    "run_id": run_id,
                    "input_index": index,
                    "message": output[index].content,
                    "failed": by_index[index][1].status is not ToolResultStatus.SUCCESS,
                }
                for index in range(len(calls)) if index in by_index
            },
            "calls_count": len(calls),
            "failed_count": sum(
                result.status is not ToolResultStatus.SUCCESS
                for _, result in by_index.values()
            ),
        }
        # A pending projection must not append placeholder ToolMessages to a
        # MessagesState.  The add_messages reducer appends returned messages;
        # approval() will emit the final ordered results exactly once after
        # resume.  Keep all intermediate data in the machine state instead.
        return {"_agentguard_prepared": context}

    async def approval(self, state: Mapping[str, Any], config: RunnableConfig | None = None) -> dict[str, Any]:
        """Interrupt once for prepared calls and execute explicit approvals."""
        context = state.get("_agentguard_prepared") if isinstance(state, Mapping) else None
        if not isinstance(context, Mapping) or not context.get("pending"):
            return {"messages": list(state.get("messages", [])) if isinstance(state, Mapping) else []}
        try:
            from langgraph.types import interrupt
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise ImportError("approval bridge requires `pip install 'agentguard[langgraph]'`") from exc

        batch_data = context["batch"]
        resume = interrupt(batch_data)
        items = tuple(
            ApprovalItem(
                tool_call_id=item["tool_call_id"],
                tool_name=item["tool_name"],
                arguments=item.get("arguments", {}),
                capabilities=tuple(item.get("capabilities", ())),
                resources=tuple(item.get("resources", ())),
                action_digest=item["action_digest"],
                input_index=int(item["input_index"]),
            )
            for item in batch_data.get("items", ())
        )
        normalized = normalize_resume_decisions(resume, ApprovalBatch(
            batch_id=batch_data["batch_id"], items=items, payload_version=batch_data["payload_version"]
        ))

        approved: list[tuple[int, CallTool, Tool]] = []
        results: dict[int, tuple[str, ToolResult]] = {}
        for item in context["pending"]:
            index = int(item["input_index"])
            call_id = item["message_tool_call_id"]
            correlation = EventCorrelation(
                call_id=item["call_id"],
                tool_call_id=item.get("tool_call_id"),
                batch_id=context["batch_id"],
            )
            decision = normalized.get(call_id)
            expected = next((entry for entry in items if entry.tool_call_id == call_id), None)
            if decision is None or not decision.approved or expected is None:
                results[index] = (call_id, self._failure_result(item["tool_name"], "PermissionDenied"))
                self._emit_approval_denied(
                    item,
                    expected,
                    decision,
                    run_id=context["run_id"],
                    step=index,
                    correlation=correlation,
                )
                continue
            original_action = CallTool(item["tool_name"], dict(item["arguments"]))
            # Recompute from the unredacted state projection, never from the
            # human-facing masked payload.
            digest = action_digest(
                original_action,
                capabilities=item.get("capabilities", ()),
                run_id=context["run_id"],
                step=index,
            )
            if digest != expected.action_digest:
                results[index] = (call_id, self._failure_result(item["tool_name"], "PermissionDenied"))
                self._emit_approval_denied(
                    item,
                    expected,
                    decision,
                    run_id=context["run_id"],
                    step=index,
                    correlation=correlation,
                )
                continue
            lang_tool = self._tools.get(item["tool_name"])
            guard = self._guards.get(item["tool_name"])
            if lang_tool is None or guard is None:
                result = self._failure_result(item["tool_name"], "UnknownTool")
                results[index] = (call_id, result)
                self._emit_rejection(
                    result,
                    run_id=context["run_id"],
                    step=index,
                    correlation=correlation,
                )
                continue
            approved.append((index, original_action, Tool(
                name=item["tool_name"], function=self._invoke_langchain_tool(lang_tool),
                timeout=guard.timeout, retry_safety=guard.retry_safety,
                capabilities=guard.capabilities, resources=guard.resources,
            )))

        if approved:
            executed = await self.runtime.execute_explicit_batch(
                ((action, tool) for _, action, tool in approved),
                run_id=context["run_id"], max_concurrency=self.max_concurrency,
                approval_context={
                    position: normalized[
                        next(entry["message_tool_call_id"] for entry in context["pending"] if int(entry["input_index"]) == index)
                    ].decision
                    for position, (index, _action, _tool) in enumerate(approved)
                },
                step_indices={position: index for position, (index, _action, _tool) in enumerate(approved)},
                correlation_contexts={
                    position: EventCorrelation(
                        call_id=next(entry["call_id"] for entry in context["pending"] if int(entry["input_index"]) == index),
                        tool_call_id=next(entry.get("tool_call_id") for entry in context["pending"] if int(entry["input_index"]) == index),
                        batch_id=context["batch_id"],
                    )
                    for position, (index, _action, _tool) in enumerate(approved)
                },
                batch_id=context["batch_id"],
                emit_batch_lifecycle=False,
            )
            results.update({
                index: (next(entry["message_tool_call_id"] for entry in context["pending"] if int(entry["input_index"]) == index), result)
                for (index, _action, _tool), result in zip(approved, executed)
            })

        output: list[ToolMessage] = []
        for index in range(int(context.get("calls_count", 0))):
            if index in results:
                output.append(self._result_message(results[index][1], results[index][0]))
            else:
                entry = context.get("immediate", {}).get(str(index))
                if entry is not None:
                    output.append(ToolMessage(content=entry["message"], tool_call_id=entry["tool_call_id"]))
                else:
                    output.append(self._failure_message("PermissionDenied", "tool call was not approved", "agentguard-invalid-call-" + str(index)))
        consumed_context = dict(context)
        consumed_context["pending"] = []
        self._emit_batch_finished(
            run_id=context["run_id"],
            batch_id=context["batch_id"],
            size=int(context.get("calls_count", 0)),
            failed=int(context.get("failed_count", 0))
            + sum(result.status is not ToolResultStatus.SUCCESS for _, result in results.values()),
        )
        return {"messages": output, "_agentguard_prepared": consumed_context}

    @staticmethod
    def _source_tool_call_id(call: Any) -> str | None:
        if isinstance(call, Mapping):
            value = call.get("id")
            if (
                isinstance(value, str)
                and value
                and value == value.strip()
                and len(value) <= 256
                and not any(ord(character) < 32 for character in value)
            ):
                return value
        return None

    def _emit_rejection(
        self,
        result: ToolResult,
        *,
        run_id: str,
        step: int,
        correlation: EventCorrelation,
    ) -> None:
        self.runtime.emit_framework_event(
            EventType.TOOL_FAILED,
            run_id=run_id,
            step=step,
            correlation=correlation,
            data={
                "tool_name": result.tool_name,
                "error_type": result.error_type or "ToolError",
                "error_message": "tool call was rejected before execution",
                "failure_kind": (result.failure_kind or FailureKind.PERMANENT).value,
                "attempts": result.attempts,
            },
        )

    def _emit_permission_denied(
        self,
        tool_name: str,
        *,
        run_id: str,
        step: int,
        correlation: EventCorrelation,
        required_capabilities: Any = (),
        forbidden_capabilities: Any = (),
        decision: str = "deny",
    ) -> None:
        self.runtime.emit_framework_event(
            EventType.PERMISSION_DENIED,
            run_id=run_id,
            step=step,
            correlation=correlation,
            data={
                "tool_name": tool_name,
                "required_capabilities": sorted(required_capabilities),
                "forbidden_capabilities": sorted(forbidden_capabilities),
                "decision": decision,
            },
        )

    def _emit_approval_denied(
        self,
        item: Mapping[str, Any],
        expected: ApprovalItem | None,
        decision: Any,
        *,
        run_id: str,
        step: int,
        correlation: EventCorrelation,
    ) -> None:
        digest = expected.action_digest if expected is not None else action_digest(
            CallTool(item["tool_name"], dict(item["arguments"])),
            capabilities=item.get("capabilities", ()),
            run_id=run_id,
            step=step,
        )
        actor = getattr(decision, "actor", "unknown") or "unknown"
        if (
            not isinstance(actor, str)
            or actor != actor.strip()
            or len(actor) > 512
            or any(ord(character) < 32 for character in actor)
        ):
            actor = "unknown"
        self.runtime.emit_framework_event(
            EventType.APPROVAL_DENIED,
            run_id=run_id,
            step=step,
            correlation=correlation,
            data={
                "tool_name": item["tool_name"],
                "required_capabilities": sorted(item.get("capabilities", ())),
                "actor": actor,
                "action_digest": digest,
                "reason": "approval was denied or invalid",
            },
        )

    def _emit_batch_finished(self, *, run_id: str, batch_id: str, size: int, failed: int) -> None:
        self.runtime.emit_framework_event(
            EventType.BATCH_FINISHED,
            run_id=run_id,
            step=0,
            correlation=EventCorrelation(batch_id=batch_id),
            data={"size": size, "failed": failed},
        )

    @staticmethod
    def _mapped_tool_call_id(call: Any, index: int) -> str:
        return GuardedToolNode._source_tool_call_id(call) or f"agentguard-invalid-call-{index}"

    @staticmethod
    def _failure_result(tool_name: str, error_type: str) -> ToolResult:
        return ToolResult(
            tool_name=tool_name or "invalid",
            status=ToolResultStatus.FAILED,
            error_type=error_type,
            error_message="tool call was rejected before execution",
            failure_kind=FailureKind.PERMANENT,
            attempts=0,
        )

    @staticmethod
    def _result_message(result: ToolResult, tool_call_id: str) -> ToolMessage:
        invalid_id = tool_call_id.startswith("agentguard-invalid-call-")
        content = (
            _safe_content(result.value)
            if result.status is ToolResultStatus.SUCCESS
            else _error_content(
                result,
                tool_call_id=tool_call_id,
                invalid_tool_call_id=invalid_id,
            )
        )
        return ToolMessage(content=content, tool_call_id=tool_call_id)

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
