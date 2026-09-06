"""Bounded, dependency-free projection of untrusted values for telemetry.

Only JSON primitives and ordinary container structure cross this boundary.
Unsupported values are replaced with fixed placeholders without invoking their
string or representation methods.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any


DEFAULT_MAX_DEPTH = 4
DEFAULT_MAX_COLLECTION_ITEMS = 20
DEFAULT_MAX_STRING_CHARS = 512
DEFAULT_MAX_NODES = 200

DEFAULT_SENSITIVE_MARKERS = (
    "password",
    "token",
    "secret",
    "api_key",
    "access_key",
    "private_key",
    "authorization",
)

REDACTED = "[REDACTED]"
MAX_DEPTH = "[MAX_DEPTH]"
MAX_NODES = "[MAX_NODES]"
CYCLE = "[CYCLE]"
UNSUPPORTED_BYTES = "[UNSUPPORTED_BYTES]"
UNSUPPORTED_OBJECT = "[UNSUPPORTED_OBJECT]"
NON_FINITE_FLOAT = "[NON_FINITE_FLOAT]"


@dataclass(frozen=True, slots=True, init=False)
class SafePreview:
    """Copy-safe bounded projection plus an explicit truncation indicator."""

    _value: Any
    truncated: bool

    def __init__(self, value: Any, *, truncated: bool) -> None:
        if not isinstance(truncated, bool):
            raise TypeError("truncated must be a boolean")
        object.__setattr__(self, "_value", deepcopy(value))
        object.__setattr__(self, "truncated", truncated)

    @property
    def value(self) -> Any:
        """Return a defensive copy so callers cannot mutate stored evidence."""

        return deepcopy(self._value)

    def to_dict(self) -> dict[str, Any]:
        """Return the public strict-JSON-compatible preview shape."""

        return {"value": self.value, "truncated": self.truncated}


@dataclass(slots=True)
class _ProjectionState:
    max_depth: int
    max_collection_items: int
    max_string_chars: int
    max_nodes: int
    markers: tuple[str, ...]
    active_containers: set[int]
    visited_nodes: int = 0
    truncated: bool = False

    def visit(self, value: Any, *, depth: int) -> Any:
        if self.visited_nodes >= self.max_nodes:
            self.truncated = True
            return MAX_NODES
        self.visited_nodes += 1

        if value is None or isinstance(value, bool) or isinstance(value, int):
            return value
        if isinstance(value, float):
            if math.isfinite(value):
                return value
            self.truncated = True
            return NON_FINITE_FLOAT
        if isinstance(value, str):
            if len(value) <= self.max_string_chars:
                return value
            self.truncated = True
            return value[: self.max_string_chars]
        if isinstance(value, bytes):
            self.truncated = True
            return UNSUPPORTED_BYTES
        if isinstance(value, Mapping):
            return self._visit_mapping(value, depth=depth)
        if isinstance(value, (list, tuple)):
            return self._visit_sequence(value, depth=depth)

        self.truncated = True
        return UNSUPPORTED_OBJECT

    def _enter_container(self, value: Any, *, depth: int) -> int | None:
        if depth >= self.max_depth:
            self.truncated = True
            return None
        identity = id(value)
        if identity in self.active_containers:
            self.truncated = True
            return -1
        self.active_containers.add(identity)
        return identity

    def _visit_mapping(self, value: Mapping[Any, Any], *, depth: int) -> dict[str, Any] | str:
        identity = self._enter_container(value, depth=depth)
        if identity is None:
            return MAX_DEPTH
        if identity == -1:
            return CYCLE

        result: dict[str, Any] = {}
        try:
            for index, (key, item) in enumerate(value.items()):
                if index >= self.max_collection_items:
                    self.truncated = True
                    break
                if not isinstance(key, str):
                    self.truncated = True
                    continue
                safe_key = self.visit(key, depth=depth + 1)
                if not isinstance(safe_key, str):
                    self.truncated = True
                    continue
                if self._is_sensitive(safe_key):
                    result[safe_key] = REDACTED
                else:
                    result[safe_key] = self.visit(item, depth=depth + 1)
        finally:
            self.active_containers.remove(identity)
        return result

    def _visit_sequence(self, value: list[Any] | tuple[Any, ...], *, depth: int) -> list[Any] | tuple[Any, ...] | str:
        identity = self._enter_container(value, depth=depth)
        if identity is None:
            return MAX_DEPTH
        if identity == -1:
            return CYCLE

        projected: list[Any] = []
        try:
            for index, item in enumerate(value):
                if index >= self.max_collection_items:
                    self.truncated = True
                    break
                projected.append(self.visit(item, depth=depth + 1))
        finally:
            self.active_containers.remove(identity)
        if isinstance(value, tuple):
            return tuple(projected)
        return projected

    def _is_sensitive(self, key: str) -> bool:
        key_text = key.casefold()
        return any(marker in key_text for marker in self.markers)


def _positive_limit(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _normalize_markers(sensitive_fields: Iterable[str]) -> tuple[str, ...]:
    if isinstance(sensitive_fields, (str, bytes)):
        raise TypeError("sensitive_fields must be an iterable of strings")
    markers = list(DEFAULT_SENSITIVE_MARKERS)
    for marker in sensitive_fields:
        if not isinstance(marker, str):
            raise TypeError("sensitive field markers must be strings")
        normalized = marker.strip().casefold()
        if not normalized:
            raise ValueError("sensitive field markers must be non-empty")
        markers.append(normalized)
    return tuple(markers)


def safe_preview(
    value: Any,
    *,
    sensitive_fields: Iterable[str] = (),
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_collection_items: int = DEFAULT_MAX_COLLECTION_ITEMS,
    max_string_chars: int = DEFAULT_MAX_STRING_CHARS,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> SafePreview:
    """Return a bounded, detached preview of an untrusted Python value."""

    state = _ProjectionState(
        max_depth=_positive_limit("max_depth", max_depth),
        max_collection_items=_positive_limit("max_collection_items", max_collection_items),
        max_string_chars=_positive_limit("max_string_chars", max_string_chars),
        max_nodes=_positive_limit("max_nodes", max_nodes),
        markers=_normalize_markers(sensitive_fields),
        active_containers=set(),
    )
    projected = state.visit(value, depth=0)
    return SafePreview(projected, truncated=state.truncated)
