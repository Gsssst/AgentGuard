import pytest

from agentguard import (
    CallTool,
    Finish,
    RunResult,
    RunState,
    RunStatus,
    StopReason,
    ToolResult,
    ToolResultStatus,
)


def test_typed_actions_are_constructed_and_copy_arguments() -> None:
    arguments = {"query": "agent runtime"}
    action = CallTool(tool_name="search", arguments=arguments)
    arguments["query"] = "mutated-after-construction"

    assert action.tool_name == "search"
    assert action.arguments == {"query": "agent runtime"}
    assert Finish(reason="done").reason == "done"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: CallTool(tool_name="", arguments={}),
        lambda: CallTool(tool_name="search", arguments=[]),
        lambda: Finish(reason=""),
    ],
)
def test_actions_reject_invalid_values(factory) -> None:
    with pytest.raises((ValueError, TypeError)):
        factory()


def test_tool_result_normalizes_success_and_failure_without_exception_object() -> None:
    success = ToolResult(
        tool_name="echo",
        status=ToolResultStatus.SUCCESS,
        value="hello",
    )
    failure = ToolResult(
        tool_name="echo",
        status=ToolResultStatus.FAILED,
        error_type="ValueError",
        error_message="bad input",
    )

    assert success.value == "hello"
    assert failure.error_type == "ValueError"
    assert not hasattr(failure, "exception")


def test_tool_result_rejects_inconsistent_error_fields() -> None:
    with pytest.raises(ValueError):
        ToolResult(tool_name="echo", status=ToolResultStatus.SUCCESS, error_message="oops")
    with pytest.raises(ValueError):
        ToolResult(tool_name="echo", status=ToolResultStatus.FAILED)


def test_run_state_keeps_only_recent_history() -> None:
    state = RunState(run_id="run-001", history_limit=2)
    for index in range(3):
        result = ToolResult(
            tool_name="echo",
            status=ToolResultStatus.SUCCESS,
            value=index,
        )
        state.record(CallTool(tool_name="echo", arguments={"value": index}), result)
        state.step += 1

    assert state.step == 3
    assert [entry.result.value for entry in state.recent_history] == [1, 2]
    assert state.last_result.value == 2


def test_run_state_rejects_invalid_step_and_history_limit() -> None:
    with pytest.raises(ValueError):
        RunState(run_id="run-001", step=-1)
    with pytest.raises(ValueError):
        RunState(run_id="run-001", history_limit=0)


def test_run_result_requires_terminal_consistent_state() -> None:
    state = RunState(run_id="run-001")
    completed = RunResult(
        run_id="run-001",
        status=RunStatus.COMPLETED,
        stop_reason=StopReason.COMPLETED,
        final_state=state,
    )

    assert completed.final_state.run_id == "run-001"

    with pytest.raises(ValueError):
        RunResult(
            run_id="run-001",
            status=RunStatus.RUNNING,
            stop_reason=StopReason.COMPLETED,
            final_state=state,
        )
    with pytest.raises(ValueError):
        RunResult(
            run_id="run-001",
            status=RunStatus.FAILED,
            stop_reason=StopReason.COMPLETED,
            final_state=state,
        )
