from agentguard import (
    CallTool,
    EventType,
    Finish,
    InMemoryEventSink,
    RunState,
    RunStatus,
    Runtime,
    StopReason,
    build_report,
)
from agentguard.events.model import RuntimeEvent
from agentguard.runtime.tool import ToolExecutor, ToolRegistry
import pytest


@pytest.mark.asyncio
async def test_report_combines_terminal_summary_events_and_metrics() -> None:
    async def echo(text: str) -> str:
        return text

    sink = InMemoryEventSink()
    result = await Runtime(
        ToolExecutor(ToolRegistry({"echo": echo})),
        event_sink=sink,
    ).run(
        type(
            "Router",
            (),
            {
                "next_action": lambda self, state: _action(
                    CallTool("echo", {"text": "hello"}) if state.step == 0 else Finish("done")
                ),
            },
        )(),
        RunState("report-run"),
    )

    report = build_report(result, sink.events)

    assert report.status == "completed"
    assert report.stop_reason == "completed"
    assert report.tool_calls == 1
    assert report.failed_tool_calls == 0
    assert report.retry_count == 0
    assert report.evidence_consistent is True
    assert report.checkpoint_writes == 0
    assert report.recovery_attempts == 0
    assert report.recovery_success is False
    assert report.to_dict()["events"][-1]["event_type"] == "run_finished"


async def _action(action):
    return action


def test_report_marks_missing_or_inconsistent_terminal_evidence() -> None:
    result = __import__("agentguard").RunResult(
        run_id="run-001",
        status=RunStatus.COMPLETED,
        stop_reason=StopReason.COMPLETED,
        final_state=RunState("run-001", step=1),
    )
    events = [RuntimeEvent(EventType.RUN_STARTED, "run-001", 0)]

    report = build_report(result, events)

    assert report.evidence_consistent is False


def test_report_counts_retry_and_loop_events() -> None:
    result = __import__("agentguard").RunResult(
        run_id="run-001",
        status=RunStatus.FAILED,
        stop_reason=StopReason.LOOP_DETECTED,
        final_state=RunState("run-001", step=2),
    )
    events = [
        RuntimeEvent(EventType.RETRY_SCHEDULED, "run-001", 0),
        RuntimeEvent(EventType.LOOP_DETECTED, "run-001", 2),
        RuntimeEvent(
            EventType.RUN_FINISHED,
            "run-001",
            2,
            {"status": "failed", "stop_reason": "loop_detected"},
        ),
    ]

    report = build_report(result, events)

    assert report.retry_count == 1
    assert report.loop_detected is True
    assert report.evidence_consistent is True


def test_report_counts_recovery_and_duplicate_evidence() -> None:
    result = __import__("agentguard").RunResult(
        run_id="run-001",
        status=RunStatus.COMPLETED,
        stop_reason=StopReason.COMPLETED,
        final_state=RunState("run-001", step=2),
    )
    events = [
        RuntimeEvent(EventType.RESUME_STARTED, "run-001", 1, {"resume_attempt": 1, "duplicate_possible": True}),
        RuntimeEvent(EventType.TOOL_STARTED, "run-001", 1, {"resume_attempt": 1, "duplicate_possible": True}),
        RuntimeEvent(EventType.RUN_FINISHED, "run-001", 2, {"status": "completed", "stop_reason": "completed"}),
    ]

    report = build_report(result, events)

    assert report.recovery_attempts == 1
    assert report.recovery_success is True
    assert report.duplicate_possible_tool_executions == 1
    assert report.crash_to_recovery_steps == 1
    assert report.final_state_correct is None
