import json

import pytest

from agentguard import CallTool, Checkpoint, CheckpointStore, RunState, ToolResult, ToolResultStatus


def _checkpoint() -> Checkpoint:
    state = RunState("run-1")
    state.record(CallTool("echo", {"value": 1}), ToolResult("echo", ToolResultStatus.SUCCESS, value=1))
    return Checkpoint("run-1", state, max_steps=3)


def test_store_saves_loads_and_creates_parent(tmp_path) -> None:
    store = CheckpointStore(tmp_path / "nested" / "checkpoints")
    path = store.save(_checkpoint())

    assert path == tmp_path / "nested" / "checkpoints" / "run-1.json"
    assert json.loads(path.read_text(encoding="utf-8"))["run_id"] == "run-1"
    assert store.load(path).state.step == 0


def test_store_replacement_failure_preserves_previous_file(tmp_path, monkeypatch) -> None:
    store = CheckpointStore(tmp_path)
    path = store.save(_checkpoint())
    previous = path.read_bytes()

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr("agentguard.checkpoint.store.os.replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        store.save(_checkpoint(), path)

    assert path.read_bytes() == previous
    assert list(tmp_path.glob("*.tmp")) == []


def test_store_path_for_is_run_scoped(tmp_path) -> None:
    assert CheckpointStore(tmp_path).path_for("abc") == tmp_path / "abc.json"

