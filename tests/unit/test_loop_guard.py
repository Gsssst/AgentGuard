import pytest

from agentguard import CallTool, Finish, LoopGuard, action_signature


def test_signature_is_stable_when_mapping_key_order_changes() -> None:
    left = CallTool("search", {"query": "agent", "page": 1})
    right = CallTool("search", {"page": 1, "query": "agent"})

    assert action_signature(left) == action_signature(right)


def test_signature_preserves_list_order_and_scalar_types() -> None:
    assert action_signature(CallTool("tool", {"items": [1, 2]})) != action_signature(
        CallTool("tool", {"items": [2, 1]})
    )
    assert action_signature(CallTool("tool", {"value": 1})) != action_signature(
        CallTool("tool", {"value": "1"})
    )


def test_loop_guard_triggers_on_third_consecutive_call() -> None:
    guard = LoopGuard(threshold=3)
    action = CallTool("search", {"query": "agent"})

    assert guard.observe(action)[0] is False
    assert guard.observe(action)[0] is False
    detected, signature, count = guard.observe(action)

    assert detected is True
    assert signature == action_signature(action)
    assert count == 3


def test_different_action_resets_consecutive_count() -> None:
    guard = LoopGuard(threshold=3)
    repeated = CallTool("search", {"query": "agent"})
    different = CallTool("search", {"query": "runtime"})

    guard.observe(repeated)
    guard.observe(repeated)
    assert guard.observe(different)[2] == 1
    assert guard.observe(repeated)[2] == 1


def test_non_consecutive_repetition_does_not_trigger() -> None:
    guard = LoopGuard(threshold=3)
    actions = [
        CallTool("search", {"query": "agent"}),
        Finish("pause"),
        CallTool("search", {"query": "agent"}),
        Finish("pause"),
        CallTool("search", {"query": "agent"}),
    ]

    assert all(guard.observe(action)[0] is False for action in actions)


def test_loop_guard_rejects_non_positive_threshold() -> None:
    with pytest.raises(ValueError):
        LoopGuard(threshold=0)
