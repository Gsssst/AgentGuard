import pytest

from agentguard import (
    ApprovalDecision,
    Capability,
    KNOWN_CAPABILITIES,
    PermissionDecisionKind,
    PermissionPolicy,
)
from agentguard.runtime.tool import Tool, ToolRegistry


def noop() -> str:
    return "ok"


def test_fixed_capability_vocabulary_is_exactly_four_labels() -> None:
    assert KNOWN_CAPABILITIES == {"read", "write", "external", "destructive"}
    assert Capability.READ.value == "read"


@pytest.mark.parametrize("labels", ["read", [""], ["unknown"], [" READ", "bogus"], [1]])
def test_invalid_capability_labels_are_rejected(labels) -> None:
    with pytest.raises((TypeError, ValueError)):
        Tool("bad", noop, capabilities=labels)


def test_tool_capabilities_are_validated_and_immutable() -> None:
    tool = Tool("send", noop, capabilities=["external", "write", "write"])

    assert tool.capabilities == frozenset({"external", "write"})
    with pytest.raises(AttributeError):
        tool.capabilities = frozenset({"read"})


def test_registry_rejects_invalid_capabilities_before_storing_tool() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError):
        registry.register("bad", noop, capabilities=["not-a-capability"])
    assert registry.get("bad") is None


def test_policy_decisions_are_three_way_and_fail_closed() -> None:
    policy = PermissionPolicy(allowed={"read"}, approval_required={"external"})

    assert policy.decide({"read"}).kind is PermissionDecisionKind.ALLOW
    assert policy.decide({"write"}).kind is PermissionDecisionKind.DENY
    assert policy.decide({"external", "write"}).kind is PermissionDecisionKind.APPROVAL_REQUIRED
    assert policy.decide({"read", "write"}).kind is PermissionDecisionKind.DENY
    assert policy.decide(set()).kind is PermissionDecisionKind.DENY


def test_policy_can_evaluate_tool_metadata_without_invoking_callable() -> None:
    called = False

    def side_effect() -> None:
        nonlocal called
        called = True

    tool = Tool("side-effect", side_effect, capabilities={"read"})
    decision = PermissionPolicy(allowed={"read"}).decide(tool)

    assert decision.allowed
    assert called is False


def test_permission_policy_normalizes_labels_and_rejects_overlap() -> None:
    policy = PermissionPolicy(allowed={" READ "})
    assert policy.allowed == frozenset({"read"})
    assert PermissionPolicy(
        allowed={"read"}, approval_required={"read"}
    ).decide({"read"}).allowed


def test_approval_decision_is_typed_and_defaults_to_local_audit_actor() -> None:
    decision = ApprovalDecision(approved=True)
    assert decision.actor == "local_user"
    assert decision.action_digest is None

    with pytest.raises(ValueError):
        ApprovalDecision(approved=False, actor=" ")
