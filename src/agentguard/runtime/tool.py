"""Tool registration and the unified async execution boundary."""

import asyncio
import inspect
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from agentguard.domain.actions import CallTool
from agentguard.domain.results import FailureKind, ToolResult, ToolResultStatus
from agentguard.events.model import EventType

from .policy import RetryPolicy, RetrySafety, classify_exception
from .permission import normalize_capabilities
from .resources import ResourceAccess, normalize_resources, validate_resource_capabilities

ToolCallable = Callable[..., Any]
ToolEventCallback = Callable[[EventType, dict[str, Any]], None]


class _RuntimeDeadlineExceeded(Exception):
    """Internal signal that AgentGuard's own deadline expired."""


def _consume_background_task_result(task: asyncio.Task[Any]) -> None:
    """Retrieve a detached task result so late failures are not unobserved."""

    try:
        task.result()
    except (asyncio.CancelledError, Exception):
        pass


@dataclass(frozen=True)
class Tool:
    """A named callable that can be requested by a CallTool Action."""

    name: str
    function: ToolCallable
    timeout: float | None = None
    retry_safety: RetrySafety = RetrySafety.UNKNOWN
    capabilities: frozenset[str] = frozenset()
    resources: Mapping[str, ResourceAccess | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool name must be a non-empty string")
        if not callable(self.function):
            raise TypeError("tool function must be callable")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("tool timeout must be positive")
        object.__setattr__(self, "capabilities", normalize_capabilities(self.capabilities))
        normalized_resources = normalize_resources(self.resources)
        validate_resource_capabilities(normalized_resources, self.capabilities)
        object.__setattr__(self, "resources", normalized_resources)


class ToolRegistry:
    """In-memory name-to-tool registry for the first local Runtime."""

    def __init__(self, tools: Mapping[str, ToolCallable] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for name, function in (tools or {}).items():
            self.register(name, function)

    def register(
        self,
        name: str,
        function: ToolCallable,
        *,
        timeout: float | None = None,
        retry_safety: RetrySafety = RetrySafety.UNKNOWN,
        capabilities: Iterable[str] = (),
        resources: Mapping[str, ResourceAccess | str] | None = None,
    ) -> None:
        self._tools[name] = Tool(
            name=name,
            function=function,
            timeout=timeout,
            retry_safety=retry_safety,
            capabilities=capabilities,
            resources=resources,
        )

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)


class ToolExecutor:
    """Execute sync and async Tools through one async method."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        default_timeout: float | None = 30.0,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if default_timeout is not None and default_timeout <= 0:
            raise ValueError("default_timeout must be positive")
        self._registry = registry
        self._default_timeout = default_timeout
        self._retry_policy = retry_policy or RetryPolicy()

    def get_tool(self, name: str) -> Tool | None:
        """Return registered metadata without invoking the Tool."""

        return self._registry.get(name)

    async def execute(
        self,
        action: CallTool,
        *,
        on_event: ToolEventCallback | None = None,
    ) -> ToolResult:
        tool = self._registry.get(action.tool_name)
        if tool is None:
            return ToolResult(
                tool_name=action.tool_name,
                status=ToolResultStatus.FAILED,
                error_type="UnknownTool",
                error_message=f"unknown tool: {action.tool_name}",
                failure_kind=FailureKind.PERMANENT,
                attempts=0,
            )

        return await self.execute_explicit(action, tool, on_event=on_event)

    async def execute_explicit(
        self,
        action: CallTool,
        tool: Tool,
        *,
        on_event: ToolEventCallback | None = None,
    ) -> ToolResult:
        """Execute a supplied Tool without adding it to this registry."""

        if not isinstance(tool, Tool):
            raise TypeError("tool must be an AgentGuard Tool")
        if tool.name != action.tool_name:
            raise ValueError("tool name must match action.tool_name")

        timeout = tool.timeout if tool.timeout is not None else self._default_timeout
        timeout_source = "tool" if tool.timeout is not None else (
            "runtime" if self._default_timeout is not None else None
        )

        async def invoke() -> Any:
            if inspect.iscoroutinefunction(tool.function):
                return await tool.function(**action.arguments)
            return await asyncio.to_thread(tool.function, **action.arguments)

        async def invoke_with_deadline() -> Any:
            if timeout is None:
                return await invoke()

            task = asyncio.create_task(invoke())
            done, _ = await asyncio.wait({task}, timeout=timeout)
            if task in done:
                # Awaiting a completed task preserves exceptions raised by the
                # Tool itself, including a Tool-raised TimeoutError.
                return await task

            task.cancel()
            # Give a cooperative coroutine one scheduling turn to observe the
            # cancellation. Never wait indefinitely: a Tool may suppress
            # CancelledError, and timeout must still return control on time.
            await asyncio.sleep(0)
            if task.done():
                _consume_background_task_result(task)
            else:
                task.add_done_callback(_consume_background_task_result)
            raise _RuntimeDeadlineExceeded

        is_async_tool = inspect.iscoroutinefunction(tool.function)
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            if on_event is not None:
                on_event(
                    EventType.TOOL_ATTEMPT_STARTED,
                    {
                        "tool_name": action.tool_name,
                        "attempt": attempt,
                        "max_attempts": self._retry_policy.max_attempts,
                        "timeout_seconds": timeout,
                        "timeout_source": timeout_source,
                        "retry_safety": tool.retry_safety.value,
                    },
                )
            try:
                value = await invoke_with_deadline()
                result = ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.SUCCESS,
                    value=value,
                    attempts=attempt,
                )
            except _RuntimeDeadlineExceeded:
                result = ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.TIMED_OUT,
                    error_type="TimeoutError",
                    error_message=f"tool exceeded {timeout:.3f}s deadline",
                    failure_kind=FailureKind.TIMEOUT,
                    timeout_seconds=timeout,
                    timeout_source=timeout_source,
                    attempts=attempt,
                )
            except Exception as exc:
                result = ToolResult(
                    tool_name=action.tool_name,
                    status=ToolResultStatus.FAILED,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    failure_kind=classify_exception(exc),
                    attempts=attempt,
                )

            if not self._retry_policy.allows(
                safety=tool.retry_safety,
                result=result,
                attempt=attempt,
                is_async_tool=is_async_tool,
            ):
                return result

            delay = self._retry_policy.delay_for_retry(attempt)
            if on_event is not None:
                on_event(
                    EventType.RETRY_SCHEDULED,
                    {
                        "tool_name": action.tool_name,
                        "completed_attempt": attempt,
                        "next_attempt": attempt + 1,
                        "max_attempts": self._retry_policy.max_attempts,
                        "delay_seconds": delay,
                        "failure_kind": (
                            result.failure_kind.value if result.failure_kind is not None else None
                        ),
                    },
                )
            await asyncio.sleep(delay)

        raise AssertionError("retry loop must return a ToolResult")
