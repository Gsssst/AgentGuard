"""Runtime policies for timeout and bounded Tool retries."""

from dataclasses import dataclass
from enum import StrEnum

from agentguard.domain.results import FailureKind, ToolResult, ToolResultStatus


class RetrySafety(StrEnum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    REQUIRES_IDEMPOTENCY_KEY = "requires_idempotency_key"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RetryPolicy:
    """Deterministic retry limits and exponential backoff configuration."""

    max_attempts: int = 1
    initial_delay: float = 0.1
    multiplier: float = 2.0
    max_delay: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.initial_delay < 0:
            raise ValueError("initial_delay cannot be negative")
        if self.multiplier < 1:
            raise ValueError("multiplier must be at least 1")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay cannot be smaller than initial_delay")

    def delay_for_retry(self, retry_index: int) -> float:
        """Return the deterministic delay before a 1-based retry index."""

        if retry_index <= 0:
            raise ValueError("retry_index must be positive")
        return min(self.max_delay, self.initial_delay * self.multiplier ** (retry_index - 1))

    def allows(
        self,
        *,
        safety: RetrySafety,
        result: ToolResult,
        attempt: int,
        is_async_tool: bool,
    ) -> bool:
        """Return whether another attempt is safe and within budget."""

        if attempt >= self.max_attempts or safety is not RetrySafety.SAFE:
            return False
        if result.status is ToolResultStatus.FAILED:
            return result.failure_kind is FailureKind.TRANSIENT
        # Timeout retry stays disabled in the initial policy. Async timeout
        # cancellation behavior needs its own experiment before duplication is
        # considered safe; sync worker threads may still be running.
        return False


def classify_exception(exc: BaseException) -> FailureKind:
    """Classify a Tool exception conservatively for retry decisions."""

    if isinstance(exc, (ConnectionError, TimeoutError)):
        return FailureKind.TRANSIENT
    return FailureKind.PERMANENT
