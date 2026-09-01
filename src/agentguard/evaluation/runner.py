"""Execute registered deterministic scenarios and project reliability metrics."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from agentguard.checkpoint import CheckpointError
from agentguard.reporting import build_report
from agentguard.runtime.engine import SimulatedCrash

from .scenarios import DEFAULT_SCENARIOS, ScenarioRegistry


async def run_scenario(
    name: str,
    *,
    root: str | Path | None = None,
    registry: ScenarioRegistry = DEFAULT_SCENARIOS,
) -> dict[str, Any]:
    """Run one scenario, including explicit recovery where applicable."""

    definition = registry.get(name)
    root_path = Path(root) if root is not None else Path(tempfile.mkdtemp(prefix="agentguard-scenario-"))
    instance = definition.factory(root_path)
    result = None
    error: str | None = None
    crashed = False
    try:
        if definition.name == "corrupt_checkpoint_rejection":
            await instance.runtime.resume(instance.checkpoint_path, instance.router)
        else:
            result = await instance.runtime.run(instance.router, instance.state)
    except SimulatedCrash as exc:
        crashed = True
        error = str(exc)
        if definition.name == "crash_and_resume":
            result = await instance.runtime.resume(instance.checkpoint_path, instance.router)
    except CheckpointError as exc:
        error = type(exc).__name__

    report = build_report(result, instance.sink.events) if result is not None else None
    final_state_correct = definition.expected_terminal(result) if result is not None else False
    output: dict[str, Any] = {
        "scenario": definition.name,
        "description": definition.description,
        "status": report.status if report is not None else "rejected",
        "stop_reason": report.stop_reason if report is not None else "recovery_rejected",
        "crashed": crashed,
        "error": error,
        "final_state_correct": final_state_correct,
        "report": report.to_dict() if report is not None else None,
        "side_effects": dict(instance.counters),
    }
    return output


async def run_all(
    *, root: str | Path | None = None, registry: ScenarioRegistry = DEFAULT_SCENARIOS
) -> list[dict[str, Any]]:
    """Run all scenarios sequentially with fresh factories."""

    root_path = Path(root) if root is not None else Path(tempfile.mkdtemp(prefix="agentguard-scenarios-"))
    results: list[dict[str, Any]] = []
    for definition in registry.all():
        results.append(await run_scenario(definition.name, root=root_path, registry=registry))
    return results
