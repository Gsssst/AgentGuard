"""Deterministic scenario definitions shared by tests and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agentguard.checkpoint import CheckpointStore
from agentguard.domain.actions import CallTool, Finish
from agentguard.domain.state import RunState
from agentguard.events.sinks import InMemoryEventSink
from agentguard.runtime.engine import Runtime, SimulatedCrash
from agentguard.runtime.router import ScriptedRouter
from agentguard.runtime.tool import ToolExecutor, ToolRegistry


@dataclass
class ScenarioInstance:
    runtime: Runtime
    router: ScriptedRouter
    state: RunState
    checkpoint_path: Path
    sink: InMemoryEventSink
    counters: dict[str, int]


ScenarioFactory = Callable[[Path], ScenarioInstance]
ExpectedPredicate = Callable[[object], bool]


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    description: str
    factory: ScenarioFactory
    expected_terminal: ExpectedPredicate
    fault: str | None
    metrics: tuple[str, ...]


class ScenarioRegistry:
    def __init__(self, definitions: tuple[ScenarioDefinition, ...] = ()) -> None:
        self._definitions: dict[str, ScenarioDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ScenarioDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"scenario already registered: {definition.name}")
        self._definitions[definition.name] = definition

    def get(self, name: str) -> ScenarioDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"unknown scenario: {name}") from exc

    def all(self) -> tuple[ScenarioDefinition, ...]:
        return tuple(self._definitions.values())


def _make_tools(counters: dict[str, int]) -> ToolExecutor:
    async def echo(value: int) -> int:
        counters["echo"] = counters.get("echo", 0) + 1
        return value

    return ToolExecutor(ToolRegistry({"echo": echo}))


def _clean_factory(root: Path) -> ScenarioInstance:
    counters: dict[str, int] = {}
    sink = InMemoryEventSink()
    path = root / "clean-completion.json"
    runtime = Runtime(
        _make_tools(counters),
        event_sink=sink,
        checkpoint_store=CheckpointStore(root),
        checkpoint_path=path,
    )
    router = ScriptedRouter([CallTool("echo", {"value": 1}), Finish("done")])
    return ScenarioInstance(runtime, router, RunState("clean-completion"), path, sink, counters)


def _crash_factory(root: Path) -> ScenarioInstance:
    counters: dict[str, int] = {}
    sink = InMemoryEventSink()
    path = root / "crash-and-resume.json"

    def crash_hook(boundary: str) -> None:
        if boundary == "after_tool_before_checkpoint":
            counters["hook"] = counters.get("hook", 0) + 1
            if counters["hook"] == 2:
                raise SimulatedCrash(boundary)

    runtime = Runtime(
        _make_tools(counters),
        event_sink=sink,
        checkpoint_store=CheckpointStore(root),
        checkpoint_path=path,
        crash_hook=crash_hook,
    )
    router = ScriptedRouter([
        CallTool("echo", {"value": 1}),
        CallTool("echo", {"value": 2}),
        Finish("done"),
    ])
    return ScenarioInstance(runtime, router, RunState("crash-and-resume"), path, sink, counters)


def _corrupt_factory(root: Path) -> ScenarioInstance:
    counters: dict[str, int] = {}
    sink = InMemoryEventSink()
    path = root / "corrupt-checkpoint.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{", encoding="utf-8")
    runtime = Runtime(_make_tools(counters), event_sink=sink)
    router = ScriptedRouter([CallTool("echo", {"value": 1}), Finish("done")])
    return ScenarioInstance(runtime, router, RunState("corrupt-checkpoint"), path, sink, counters)


DEFAULT_SCENARIOS = ScenarioRegistry(
    (
        ScenarioDefinition(
            "clean_completion",
            "A Tool call and Finish complete without a crash.",
            _clean_factory,
            lambda result: getattr(result, "stop_reason", None).value == "completed",
            None,
            ("checkpoint_writes", "final_state_correct"),
        ),
        ScenarioDefinition(
            "crash_and_resume",
            "A crash after Tool execution is recovered explicitly with replay evidence.",
            _crash_factory,
            lambda result: getattr(result, "stop_reason", None).value == "completed",
            "after_tool_before_checkpoint",
            ("recovery_success", "duplicate_possible_tool_executions", "crash_to_recovery_steps"),
        ),
        ScenarioDefinition(
            "corrupt_checkpoint_rejection",
            "A malformed checkpoint is rejected before any Tool side effect.",
            _corrupt_factory,
            lambda result: result is None,
            "corrupt_json",
            ("safe_rejection", "side_effects"),
        ),
    )
)

