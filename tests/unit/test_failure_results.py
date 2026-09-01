import pytest

from agentguard import FailureKind, ToolResult, ToolResultStatus


def test_timeout_and_cancelled_results_are_serializable_values() -> None:
    timeout = ToolResult(
        tool_name="slow",
        status=ToolResultStatus.TIMED_OUT,
        error_type="TimeoutError",
        error_message="deadline exceeded",
        failure_kind=FailureKind.TIMEOUT,
        timeout_seconds=1.0,
        timeout_source="tool",
    )
    cancelled = ToolResult(
        tool_name="slow",
        status=ToolResultStatus.CANCELLED,
        error_type="CancelledError",
        error_message="cancelled by runtime",
        failure_kind=FailureKind.CANCELLED,
    )

    assert timeout.failure_kind is FailureKind.TIMEOUT
    assert timeout.timeout_seconds == 1.0
    assert timeout.timeout_source == "tool"
    assert cancelled.failure_kind is FailureKind.CANCELLED
    assert "exception" not in timeout.__dict__


def test_failure_status_requires_error_description() -> None:
    with pytest.raises(ValueError):
        ToolResult(tool_name="slow", status=ToolResultStatus.TIMED_OUT)

    with pytest.raises(ValueError):
        ToolResult(
            tool_name="slow",
            status=ToolResultStatus.TIMED_OUT,
            error_type="TimeoutError",
            error_message="deadline exceeded",
            failure_kind=FailureKind.PERMANENT,
        )


def test_timeout_metadata_requires_a_positive_duration_and_source() -> None:
    with pytest.raises(ValueError):
        ToolResult(
            tool_name="slow",
            status=ToolResultStatus.TIMED_OUT,
            error_type="TimeoutError",
            error_message="deadline exceeded",
            timeout_source="runtime",
        )

    with pytest.raises(ValueError):
        ToolResult(
            tool_name="slow",
            status=ToolResultStatus.TIMED_OUT,
            error_type="TimeoutError",
            error_message="deadline exceeded",
            timeout_seconds=0,
        )
