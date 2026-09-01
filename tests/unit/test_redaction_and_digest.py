from agentguard import CallTool, action_digest, redact


def test_action_digest_is_stable_for_mapping_order_and_sensitive_values_are_not_in_redaction() -> None:
    first = CallTool("send", {"z": 1, "password": "top-secret", "nested": [{"TOKEN": "abc"}]})
    second = CallTool("send", {"nested": [{"TOKEN": "abc"}], "password": "top-secret", "z": 1})

    digest_a = action_digest(first, capabilities={"external"}, run_id="run-1", step=0)
    digest_b = action_digest(second, capabilities={"external"}, run_id="run-1", step=0)
    assert digest_a == digest_b
    projected = redact(first.arguments)
    assert projected["password"] == "[REDACTED]"
    assert projected["nested"][0]["TOKEN"] == "[REDACTED]"
    assert first.arguments["password"] == "top-secret"


def test_action_digest_changes_when_binding_context_changes() -> None:
    action = CallTool("send", {"value": 1})
    base = action_digest(action, capabilities={"external"}, run_id="run-1", step=0)
    assert action_digest(action, capabilities={"write"}, run_id="run-1", step=0) != base
    assert action_digest(action, capabilities={"external"}, run_id="run-2", step=0) != base
    assert action_digest(action, capabilities={"external"}, run_id="run-1", step=1) != base
