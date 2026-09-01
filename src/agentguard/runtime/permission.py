"""Capability-based permission contracts for AgentGuard Tools.

The permission layer is deliberately side-effect free. It only normalizes
metadata and returns a typed decision; the Runtime is responsible for acting
on that decision before invoking a Tool.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from typing import Any


class Capability(StrEnum):
    """The fixed capability vocabulary supported by the first version."""

    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"


KNOWN_CAPABILITIES = frozenset(capability.value for capability in Capability)


class PermissionDecisionKind(StrEnum):
    """The three outcomes returned by :meth:`PermissionPolicy.decide`."""

    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


PermissionOutcome = PermissionDecisionKind


def normalize_capabilities(capabilities: Iterable[str] | Any) -> frozenset[str]:
    """Validate and canonicalize a capability collection."""

    if isinstance(capabilities, (str, bytes)):
        raise TypeError("capabilities must be an iterable of labels, not a string")
    try:
        labels = list(capabilities)
    except TypeError as exc:
        raise TypeError("capabilities must be an iterable of labels") from exc

    normalized: set[str] = set()
    for label in labels:
        if not isinstance(label, str):
            raise TypeError("capability labels must be strings")
        value = label.strip().lower()
        if not value:
            raise ValueError("capability labels must be non-empty")
        if value not in KNOWN_CAPABILITIES:
            raise ValueError(f"unknown capability label: {label!r}")
        normalized.add(value)
    return frozenset(normalized)


@dataclass(frozen=True)
class PermissionDenied:
    """Structured explanation for a direct permission denial."""

    required_capabilities: frozenset[str]
    forbidden_capabilities: frozenset[str]
    reason: str = "capability is not permitted by policy"

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_capabilities", normalize_capabilities(self.required_capabilities))
        object.__setattr__(self, "forbidden_capabilities", normalize_capabilities(self.forbidden_capabilities))
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("permission denial reason must be a non-empty string")

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True)
class PermissionDecision:
    """A deterministic, side-effect-free policy evaluation result."""

    kind: PermissionDecisionKind
    required_capabilities: frozenset[str] = frozenset()
    forbidden_capabilities: frozenset[str] = frozenset()
    denial: PermissionDenied | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PermissionDecisionKind):
            raise TypeError("kind must be a PermissionDecisionKind")
        object.__setattr__(self, "required_capabilities", normalize_capabilities(self.required_capabilities))
        object.__setattr__(self, "forbidden_capabilities", normalize_capabilities(self.forbidden_capabilities))
        if self.kind is PermissionDecisionKind.DENY:
            if self.denial is None:
                object.__setattr__(
                    self,
                    "denial",
                    PermissionDenied(self.required_capabilities, self.forbidden_capabilities),
                )
        elif self.denial is not None:
            raise ValueError("only denied decisions may include denial data")

    @property
    def outcome(self) -> PermissionDecisionKind:
        return self.kind

    @property
    def allowed(self) -> bool:
        return self.kind is PermissionDecisionKind.ALLOW

    @property
    def requires_approval(self) -> bool:
        return self.kind is PermissionDecisionKind.APPROVAL_REQUIRED

    @property
    def denied(self) -> bool:
        return self.kind is PermissionDecisionKind.DENY


@dataclass(frozen=True)
class PermissionPolicy:
    """Explicit allow-list policy with an optional approval boundary.

    For a multi-label Tool the deterministic precedence is: all labels in
    ``allowed`` means allow; otherwise any configured approval label makes the
    whole action approval-required; if no approval label is present the Tool
    is directly denied.  This makes ``{"external", "write"}`` approval
    gated when ``external`` is configured for approval, while
    ``{"read", "write"}`` remains denied when ``write`` is unconfigured.
    """

    allowed: frozenset[str] = frozenset()
    approval_required: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed", normalize_capabilities(self.allowed))
        object.__setattr__(self, "approval_required", normalize_capabilities(self.approval_required))

    def decide(self, capabilities: Iterable[str] | Any) -> PermissionDecision:
        """Return allow, approval-required, or deny without invoking a Tool."""

        if hasattr(capabilities, "capabilities") and not isinstance(capabilities, (set, frozenset, list, tuple)):
            capabilities = getattr(capabilities, "capabilities")
        labels = normalize_capabilities(capabilities)
        if labels and labels.issubset(self.allowed):
            return PermissionDecision(PermissionDecisionKind.ALLOW, required_capabilities=labels)

        approval_labels = labels & self.approval_required
        if approval_labels:
            return PermissionDecision(
                PermissionDecisionKind.APPROVAL_REQUIRED,
                required_capabilities=labels,
            )

        return PermissionDecision(
            PermissionDecisionKind.DENY,
            required_capabilities=labels,
            forbidden_capabilities=labels - self.allowed,
        )


@dataclass(frozen=True)
class ApprovalDecision:
    """A caller-supplied approval result; actor is an audit label only."""

    approved: bool
    actor: str = "local_user"
    reason: str | None = None
    action_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.approved, bool):
            raise TypeError("approved must be a boolean")
        if not isinstance(self.actor, str) or not self.actor.strip():
            raise ValueError("actor must be a non-empty string")
        if self.reason is not None and (not isinstance(self.reason, str) or not self.reason.strip()):
            raise ValueError("reason must be a non-empty string when provided")
        if self.action_digest is not None and (
            not isinstance(self.action_digest, str) or not self.action_digest.strip()
        ):
            raise ValueError("action_digest must be a non-empty string when provided")


def canonicalize(value: Any) -> Any:
    """Return a deterministic JSON-compatible representation."""

    if isinstance(value, dict):
        return {str(key): canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return {"__tuple__": [canonicalize(item) for item in value]}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported value in permission digest: {type(value).__name__}")


def compute_action_digest(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    capabilities: Iterable[str],
    run_id: str,
    step: int,
) -> str:
    """Bind the exact proposed Action to its run position and capabilities."""

    payload = {
        "tool_name": tool_name,
        "arguments": canonicalize(arguments),
        "capabilities": sorted(normalize_capabilities(capabilities)),
        "run_id": run_id,
        "step": step,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def action_digest(action: Any, *, capabilities: Iterable[str], run_id: str, step: int) -> str:
    """Convenience wrapper accepting a CallTool-like object."""

    return compute_action_digest(
        tool_name=action.tool_name,
        arguments=action.arguments,
        capabilities=capabilities,
        run_id=run_id,
        step=step,
    )


_DEFAULT_SENSITIVE_MARKERS = (
    "password",
    "token",
    "secret",
    "api_key",
    "access_key",
    "private_key",
    "authorization",
)


def redact(value: Any, *, sensitive_fields: Iterable[str] = ()) -> Any:
    """Recursively project values for audit events without mutating input."""

    markers = tuple(marker.lower() for marker in (*_DEFAULT_SENSITIVE_MARKERS, *sensitive_fields))
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(marker in key_text.lower() for marker in markers):
                result[key] = "[REDACTED]"
            else:
                result[key] = redact(item, sensitive_fields=sensitive_fields)
        return result
    if isinstance(value, list):
        return [redact(item, sensitive_fields=sensitive_fields) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item, sensitive_fields=sensitive_fields) for item in value)
    return value


redact_arguments = redact
