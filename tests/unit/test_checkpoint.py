import json

import pytest

from agentguard import (
    CallTool,
    Checkpoint,
    CheckpointCorruptError,
    CheckpointLifecycle,
    CheckpointSerializationError,
    CheckpointValidationError,
    Finish,
    RunState,
    RunStatus,
    ToolResult,
    ToolResultStatus,
    dumps_checkpoint,
    loads_checkpoint,
)


def _checkpoint() -> Checkpoint:
    state = RunState("run-1", step=1, history_limit=2)
    state.record(CallTool("echo", {"text": "hello"}), ToolResult("echo", ToolResultStatus.SUCCESS, value="hello"))
    return Checkpoint("run-1", state, max_steps=5, event_position=3)


def test_checkpoint_round_trip_preserves_state_and_metadata() -> None:
    checkpoint = _checkpoint()
    restored = loads_checkpoint(dumps_checkpoint(checkpoint))

    assert restored.run_id == "run-1"
    assert restored.state.step == 1
    assert restored.state.status is RunStatus.RUNNING
    assert restored.state.recent_history[0].action == CallTool("echo", {"text": "hello"})
    assert restored.state.last_result is not None
    assert restored.state.last_result.value == "hello"
    assert restored.event_position == 3


def test_checkpoint_encodes_actions_and_is_deterministic_json() -> None:
    checkpoint = _checkpoint()
    checkpoint.pending_action = Finish("done")
    raw = json.loads(dumps_checkpoint(checkpoint))

    assert raw["schema_version"] == 1
    assert raw["pending_action"] == {"action_type": "finish", "reason": "done"}
    assert dumps_checkpoint(checkpoint) == dumps_checkpoint(checkpoint)


def test_checkpoint_rejects_corrupt_missing_and_unsupported_input() -> None:
    with pytest.raises(CheckpointCorruptError):
        loads_checkpoint("{")

    raw = json.loads(dumps_checkpoint(_checkpoint()))
    del raw["state"]
    with pytest.raises(CheckpointValidationError):
        loads_checkpoint(json.dumps(raw))

    raw = json.loads(dumps_checkpoint(_checkpoint()))
    raw["schema_version"] = 99
    with pytest.raises(Exception, match="99"):
        loads_checkpoint(json.dumps(raw))


def test_checkpoint_rejects_non_json_tool_value() -> None:
    state = RunState("run-1")
    state.record(CallTool("bad", {}), ToolResult("bad", ToolResultStatus.SUCCESS, value=object()))
    with pytest.raises(CheckpointSerializationError):
        dumps_checkpoint(Checkpoint("run-1", state, max_steps=2))


def test_checkpoint_validates_lifecycle_and_run_id() -> None:
    with pytest.raises(CheckpointValidationError):
        Checkpoint("", RunState("run-1"), max_steps=1)
    checkpoint = _checkpoint()
    checkpoint.lifecycle = CheckpointLifecycle.COMPLETED
    assert checkpoint.lifecycle is CheckpointLifecycle.COMPLETED

