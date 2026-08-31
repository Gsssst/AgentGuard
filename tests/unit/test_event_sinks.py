import json

from agentguard.events import EventType, InMemoryEventSink, JsonlEventSink, RuntimeEvent


def test_in_memory_sink_preserves_event_order() -> None:
    sink = InMemoryEventSink()
    first = RuntimeEvent(EventType.RUN_STARTED, "run-001", 0)
    second = RuntimeEvent(EventType.RUN_FINISHED, "run-001", 1)

    sink.emit(first)
    sink.emit(second)

    assert sink.events == [first, second]


def test_jsonl_sink_writes_one_parseable_event_per_line(tmp_path) -> None:
    path = tmp_path / "events" / "run.jsonl"
    sink = JsonlEventSink(path)
    sink.emit(
        RuntimeEvent(
            event_type=EventType.TOOL_FAILED,
            run_id="run-失败",
            step=1,
            data={"tool_name": "broken", "error_type": "ValueError"},
        )
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])

    assert len(lines) == 1
    assert event["event_type"] == "tool_failed"
    assert event["run_id"] == "run-失败"
    assert event["data"]["error_type"] == "ValueError"


def test_runtime_event_copies_caller_data() -> None:
    data = {"tool_name": "echo"}
    event = RuntimeEvent(EventType.TOOL_STARTED, "run-001", 0, data=data)
    data["tool_name"] = "mutated"

    assert event.data["tool_name"] == "echo"
