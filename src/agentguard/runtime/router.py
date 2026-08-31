"""Router protocols and deterministic Router implementations."""

from collections.abc import Sequence
from typing import Protocol

from agentguard.domain.actions import Action
from agentguard.domain.state import RunState


class Router(Protocol):
    """Component that proposes one Action from the current state."""

    async def next_action(self, state: RunState) -> Action:
        """Return the next requested Action."""


class ScriptedRouter:
    """Deterministic Router useful for examples and fault scenarios."""

    def __init__(self, actions: Sequence[Action]) -> None:
        self._actions = tuple(actions)

    async def next_action(self, state: RunState) -> Action:
        if state.step >= len(self._actions):
            raise RuntimeError("scripted router has no remaining actions")
        return self._actions[state.step]
