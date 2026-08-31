"""Tool registration and the unified async execution boundary."""

import asyncio
import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from agentguard.domain.actions import CallTool
from agentguard.domain.results import ToolResult, ToolResultStatus

ToolCallable = Callable[..., Any]


@dataclass(frozen=True)
class Tool:
    """A named callable that can be requested by a CallTool Action."""

    name: str
    function: ToolCallable

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool name must be a non-empty string")
        if not callable(self.function):
            raise TypeError("tool function must be callable")


class ToolRegistry:
    """In-memory name-to-tool registry for the first local Runtime."""

    def __init__(self, tools: Mapping[str, ToolCallable] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for name, function in (tools or {}).items():
            self.register(name, function)

    def register(self, name: str, function: ToolCallable) -> None:
        self._tools[name] = Tool(name=name, function=function)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)


class ToolExecutor:
    """Execute sync and async Tools through one async method."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute(self, action: CallTool) -> ToolResult:
        tool = self._registry.get(action.tool_name)
        if tool is None:
            return ToolResult(
                tool_name=action.tool_name,
                status=ToolResultStatus.FAILED,
                error_type="UnknownTool",
                error_message=f"unknown tool: {action.tool_name}",
            )

        try:
            if inspect.iscoroutinefunction(tool.function):
                value = await tool.function(**action.arguments)
            else:
                value = await asyncio.to_thread(tool.function, **action.arguments)
        except Exception as exc:
            return ToolResult(
                tool_name=action.tool_name,
                status=ToolResultStatus.FAILED,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        return ToolResult(
            tool_name=action.tool_name,
            status=ToolResultStatus.SUCCESS,
            value=value,
        )
