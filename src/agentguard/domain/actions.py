"""Actions proposed by a Router."""

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class CallTool:
    """Request one registered Tool execution."""

    tool_name: str
    arguments: dict[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")
        if not isinstance(self.arguments, dict):
            raise TypeError("arguments must be a dictionary")
        # Copy the mapping so callers cannot mutate the Action through the
        # dictionary they passed after construction.
        object.__setattr__(self, "arguments", dict(self.arguments))


@dataclass(frozen=True)
class Finish:
    """Request explicit completion of a run."""

    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")


Action: TypeAlias = CallTool | Finish
