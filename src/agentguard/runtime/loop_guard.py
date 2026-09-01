"""Deterministic guard for consecutive repeated Tool Actions."""

import json
from dataclasses import dataclass
from typing import Any

from agentguard.domain.actions import Action, CallTool


def canonicalize(value: Any) -> Any:
    """Return a JSON-compatible canonical value with sorted mappings."""

    if isinstance(value, dict):
        return {str(key): canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return {"__tuple__": [canonicalize(item) for item in value]}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported value in Action arguments: {type(value).__name__}")


def action_signature(action: Action) -> str:
    """Build a stable signature for one Action.

    `Finish` is intentionally represented too, although the Runtime only
    applies the repeated-action guard to `CallTool` actions.
    """

    if isinstance(action, CallTool):
        payload = {"tool_name": action.tool_name, "arguments": canonicalize(action.arguments)}
    else:
        payload = {"action_type": type(action).__name__, "reason": action.reason}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass
class LoopGuard:
    """Track consecutive identical Action signatures."""

    threshold: int = 3
    _last_signature: str | None = None
    _consecutive_count: int = 0

    def __post_init__(self) -> None:
        if self.threshold <= 0:
            raise ValueError("threshold must be positive")

    def observe(self, action: Action) -> tuple[bool, str, int]:
        """Record an Action and return (detected, signature, count)."""

        signature = action_signature(action)
        if signature == self._last_signature:
            self._consecutive_count += 1
        else:
            self._last_signature = signature
            self._consecutive_count = 1

        return (
            isinstance(action, CallTool) and self._consecutive_count >= self.threshold,
            signature,
            self._consecutive_count,
        )

    @property
    def consecutive_count(self) -> int:
        return self._consecutive_count
