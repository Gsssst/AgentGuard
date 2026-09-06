import json
import math

from agentguard._safety import SafePreview, safe_preview
from agentguard.runtime.permission import redact, redact_arguments


class HostileObject:
    def __init__(self) -> None:
        self.coercion_attempted = False

    def __str__(self) -> str:
        self.coercion_attempted = True
        raise AssertionError("hostile __str__ must never be called")

    __repr__ = __str__


def _strict_json(preview: SafePreview) -> str:
    return json.dumps(preview.to_dict(), allow_nan=False, sort_keys=True)


def test_safe_preview_recursively_redacts_default_and_caller_markers_without_mutation() -> None:
    source = {
        "password": "top-secret",
        "nested": [{"AUTHORIZATION": "Bearer attacker", "session_cookie": "cookie-value"}],
        "visible": "ok",
    }

    preview = safe_preview(source, sensitive_fields=("cookie",))

    assert preview.value == {
        "password": "[REDACTED]",
        "nested": [{"AUTHORIZATION": "[REDACTED]", "session_cookie": "[REDACTED]"}],
        "visible": "ok",
    }
    assert preview.truncated is False
    assert "top-secret" not in _strict_json(preview)
    assert "attacker" not in _strict_json(preview)
    assert "cookie-value" not in _strict_json(preview)
    assert source["password"] == "top-secret"


def test_safe_preview_bounds_strings_depth_collection_width_and_total_nodes() -> None:
    long_text = "x" * 600
    deep = {"a": {"b": {"c": {"d": {"e": "hidden"}}}}}
    wide = list(range(25))
    many_nodes = {f"item_{index}": [index] for index in range(150)}

    long_preview = safe_preview(long_text)
    deep_preview = safe_preview(deep)
    wide_preview = safe_preview(wide)
    node_preview = safe_preview(many_nodes)

    assert len(long_preview.value) == 512
    assert long_preview.truncated is True
    assert "[MAX_DEPTH]" in _strict_json(deep_preview)
    assert deep_preview.truncated is True
    assert len(wide_preview.value) == 20
    assert wide_preview.truncated is True
    assert node_preview.truncated is True
    for preview in (long_preview, deep_preview, wide_preview, node_preview):
        _strict_json(preview)


def test_safe_preview_handles_cycles_bytes_non_finite_floats_and_hostile_objects() -> None:
    cycle: list[object] = []
    cycle.append(cycle)
    hostile = HostileObject()
    source = {
        "cycle": cycle,
        "bytes": b"attacker-bytes",
        "nan": math.nan,
        "positive_infinity": math.inf,
        "negative_infinity": -math.inf,
        "object": hostile,
    }

    preview = safe_preview(source)
    encoded = _strict_json(preview)

    assert preview.truncated is True
    assert preview.value["cycle"] == ["[CYCLE]"]
    assert preview.value["bytes"] == "[UNSUPPORTED_BYTES]"
    assert preview.value["nan"] == "[NON_FINITE_FLOAT]"
    assert preview.value["positive_infinity"] == "[NON_FINITE_FLOAT]"
    assert preview.value["negative_infinity"] == "[NON_FINITE_FLOAT]"
    assert preview.value["object"] == "[UNSUPPORTED_OBJECT]"
    assert hostile.coercion_attempted is False
    assert "attacker-bytes" not in encoded


def test_safe_preview_is_detached_from_source_and_returned_values_are_copy_safe() -> None:
    source = {"items": [{"value": 1}]}
    preview = safe_preview(source)

    source["items"][0]["value"] = 99
    first_read = preview.value
    first_read["items"][0]["value"] = 42

    assert preview.value == {"items": [{"value": 1}]}
    assert preview.to_dict() == {"value": {"items": [{"value": 1}]}, "truncated": False}


def test_safe_preview_enforces_positive_boolean_free_limits() -> None:
    for keyword in ("max_depth", "max_collection_items", "max_string_chars", "max_nodes"):
        try:
            safe_preview({}, **{keyword: True})
        except TypeError:
            pass
        else:
            raise AssertionError(f"{keyword} accepted bool as an integer")

        try:
            safe_preview({}, **{keyword: 0})
        except ValueError:
            pass
        else:
            raise AssertionError(f"{keyword} accepted a non-positive limit")


def test_legacy_redaction_wrappers_keep_supported_container_shapes() -> None:
    source = {"items": ({"token": "secret"}, "visible")}

    redacted = redact(source)
    redacted_arguments_value = redact_arguments(source)

    assert redacted == {"items": ({"token": "[REDACTED]"}, "visible")}
    assert redacted_arguments_value == redacted
    assert isinstance(redacted["items"], tuple)
    assert source["items"][0]["token"] == "secret"
