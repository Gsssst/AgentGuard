import pytest

from agentguard import FailureKind, ToolResult, ToolResultStatus
from agentguard.runtime.policy import RetryPolicy, RetrySafety


def test_exponential_backoff_is_deterministic_and_capped() -> None:
    policy = RetryPolicy(
        max_attempts=4,
        initial_delay=0.1,
        multiplier=2,
        max_delay=0.25,
    )

    assert [policy.delay_for_retry(i) for i in (1, 2, 3, 4)] == [0.1, 0.2, 0.25, 0.25]


def test_only_safe_transient_results_are_retryable() -> None:
    policy = RetryPolicy(max_attempts=3, initial_delay=0)
    transient = ToolResult(
        "flaky",
        ToolResultStatus.FAILED,
        error_type="ConnectionError",
        error_message="temporary",
        failure_kind=FailureKind.TRANSIENT,
    )
    permanent = ToolResult(
        "broken",
        ToolResultStatus.FAILED,
        error_type="ValueError",
        error_message="bad input",
        failure_kind=FailureKind.PERMANENT,
    )

    assert policy.allows(safety=RetrySafety.SAFE, result=transient, attempt=1, is_async_tool=True)
    assert not policy.allows(safety=RetrySafety.UNKNOWN, result=transient, attempt=1, is_async_tool=True)
    assert not policy.allows(safety=RetrySafety.SAFE, result=permanent, attempt=1, is_async_tool=True)
    assert not policy.allows(safety=RetrySafety.SAFE, result=transient, attempt=3, is_async_tool=True)


def test_timeout_retry_is_disabled_for_both_async_and_sync_tools_initially() -> None:
    policy = RetryPolicy(max_attempts=2, initial_delay=0)
    timeout = ToolResult(
        "slow",
        ToolResultStatus.TIMED_OUT,
        error_type="TimeoutError",
        error_message="deadline exceeded",
        failure_kind=FailureKind.TIMEOUT,
        timeout_seconds=0.1,
        timeout_source="runtime",
    )

    assert not policy.allows(safety=RetrySafety.SAFE, result=timeout, attempt=1, is_async_tool=True)
    assert not policy.allows(safety=RetrySafety.SAFE, result=timeout, attempt=1, is_async_tool=False)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"initial_delay": -1},
        {"multiplier": 0.5},
        {"initial_delay": 2, "max_delay": 1},
    ],
)
def test_retry_policy_rejects_invalid_configuration(kwargs) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(**kwargs)
