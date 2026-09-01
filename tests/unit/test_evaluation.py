import json

import pytest

from agentguard.evaluation import DEFAULT_SCENARIOS, ScenarioDefinition, ScenarioRegistry, run_all, run_scenario


def test_default_registry_has_three_stable_scenarios() -> None:
    names = [item.name for item in DEFAULT_SCENARIOS.all()]
    assert names == ["clean_completion", "crash_and_resume", "corrupt_checkpoint_rejection"]
    assert DEFAULT_SCENARIOS.get("crash_and_resume").metrics
    with pytest.raises(KeyError, match="unknown scenario"):
        DEFAULT_SCENARIOS.get("missing")


def test_registry_rejects_duplicate_names() -> None:
    definition = DEFAULT_SCENARIOS.get("clean_completion")
    registry = ScenarioRegistry((definition,))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition)


def test_factories_create_fresh_mutable_instances(tmp_path) -> None:
    definition = DEFAULT_SCENARIOS.get("clean_completion")
    first = definition.factory(tmp_path / "one")
    second = definition.factory(tmp_path / "two")
    assert first.runtime is not second.runtime
    assert first.router is not second.router
    assert first.counters is not second.counters


@pytest.mark.asyncio
async def test_run_all_scenarios_is_json_serializable(tmp_path) -> None:
    results = await run_all(root=tmp_path)
    assert [item["scenario"] for item in results] == [
        "clean_completion", "crash_and_resume", "corrupt_checkpoint_rejection"
    ]
    assert results[0]["status"] == "completed"
    assert results[0]["final_state_correct"] is True
    assert results[1]["report"]["recovery_success"] is True
    assert results[1]["report"]["duplicate_possible_tool_executions"] >= 1
    assert results[2]["status"] == "rejected"
    assert results[2]["error"] == "CheckpointCorruptError"
    json.dumps(results)


@pytest.mark.asyncio
async def test_corrupt_scenario_has_no_tool_side_effect(tmp_path) -> None:
    result = await run_scenario("corrupt_checkpoint_rejection", root=tmp_path)
    assert result["status"] == "rejected"
    assert result["side_effects"] == {}

