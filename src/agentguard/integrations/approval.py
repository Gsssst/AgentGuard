"""Pure contracts used by the LangGraph approval bridge.

The objects in this module are deliberately framework agnostic.  They carry
only the review projection and the original digest binding; LangGraph owns
checkpointing and delivers the untrusted resume value back to the adapter.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from agentguard.domain.actions import CallTool
from agentguard.runtime.permission import ApprovalDecision, action_digest, redact
from agentguard.runtime.resources import ResourceAccess


PAYLOAD_VERSION = "agentguard.approval.v1"


def _jsonable(value: Any) -> Any:
    """Return a deterministic JSON-compatible copy for public projections."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


@dataclass(frozen=True)
class ApprovalItem:
    """One independently decidable call in an approval projection."""

    tool_call_id: str
    tool_name: str
    arguments: Mapping[str, Any]
    capabilities: tuple[str, ...]
    resources: tuple[Mapping[str, str], ...]
    action_digest: str
    input_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.tool_call_id, str) or not self.tool_call_id.strip():
            raise ValueError("tool_call_id must be a non-empty string")
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")
        if not isinstance(self.arguments, Mapping):
            raise TypeError("arguments must be a mapping")
        if not isinstance(self.action_digest, str) or not self.action_digest.strip():
            raise ValueError("action_digest must be a non-empty string")
        if not isinstance(self.input_index, int) or self.input_index < 0:
            raise ValueError("input_index must be a non-negative integer")
        object.__setattr__(self, "arguments", _jsonable(dict(self.arguments)))
        object.__setattr__(self, "capabilities", tuple(sorted(str(item) for item in self.capabilities)))
        normalized_resources = tuple(
            {"id": str(item.get("id", "")), "access": str(item.get("access", ""))}
            for item in self.resources
        )
        object.__setattr__(self, "resources", normalized_resources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "arguments": _jsonable(self.arguments),
            "capabilities": list(self.capabilities),
            "resources": [dict(item) for item in self.resources],
            "action_digest": self.action_digest,
            "input_index": self.input_index,
        }


@dataclass(frozen=True)
class ApprovalBatch:
    """Versioned, JSON-serializable interrupt payload."""

    batch_id: str
    items: tuple[ApprovalItem, ...]
    payload_version: str = PAYLOAD_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.batch_id, str) or not self.batch_id.strip():
            raise ValueError("batch_id must be a non-empty string")
        if not isinstance(self.payload_version, str) or not self.payload_version.strip():
            raise ValueError("payload_version must be a non-empty string")
        object.__setattr__(self, "items", tuple(self.items))
        ids = [item.tool_call_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("approval items must have unique tool_call_id values")

    @property
    def pending_count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_version": self.payload_version,
            "batch_id": self.batch_id,
            "pending_count": self.pending_count,
            "items": [item.to_dict() for item in self.items],
        }

    # A mapping-like convenience keeps the DTO pleasant to use with tests and
    # LangGraph state while preserving a typed public contract.
    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]


@dataclass(frozen=True)
class NormalizedApproval:
    """Fail-closed interpretation of one resume entry."""

    tool_call_id: str
    approved: bool = False
    actor: str = "unknown"
    reason: str = "missing approval decision"
    action_digest: str | None = None
    digest_valid: bool = False
    valid: bool = False
    error: str | None = None

    @property
    def decision(self) -> ApprovalDecision:
        return ApprovalDecision(
            approved=self.approved and self.valid,
            actor=self.actor,
            reason=self.reason,
            action_digest=self.action_digest,
        )


def _stable_batch_id(run_id: str, items: Iterable[ApprovalItem]) -> str:
    material = {
        "run_id": run_id,
        "calls": [
            {"id": item.tool_call_id, "digest": item.action_digest, "index": item.input_index}
            for item in items
        ],
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return "approval-" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def build_approval_batch(
    pending: Iterable[Any],
    *,
    run_id: str,
    batch_id: str | None = None,
) -> ApprovalBatch:
    """Build a redacted projection while hashing the original arguments."""

    items: list[ApprovalItem] = []
    for entry in pending:
        if not isinstance(entry, tuple) or len(entry) not in (4, 5):
            raise TypeError("pending entries must be (index, tool_call_id, action, capabilities, resources)")
        if len(entry) == 5:
            index, tool_call_id, action, capabilities, resources = entry
        else:
            index, tool_call_id, action, metadata = entry
            capabilities = getattr(metadata, "capabilities", metadata)
            resources = getattr(metadata, "resources", {})
        digest = action_digest(action, capabilities=capabilities, run_id=run_id, step=index)
        resource_summary = tuple(
            {"id": str(resource_id), "access": (access.value if isinstance(access, ResourceAccess) else str(access))}
            for resource_id, access in sorted(resources.items(), key=lambda pair: str(pair[0]))
        )
        items.append(
            ApprovalItem(
                tool_call_id=tool_call_id,
                tool_name=action.tool_name,
                arguments=redact(action.arguments),
                capabilities=tuple(capabilities),
                resources=resource_summary,
                action_digest=digest,
                input_index=index,
            )
        )
    resolved_id = batch_id or _stable_batch_id(run_id, items)
    return ApprovalBatch(batch_id=resolved_id, items=tuple(items))


def normalize_resume_decisions(
    resume: Any,
    expected: ApprovalBatch | Iterable[ApprovalItem],
) -> dict[str, NormalizedApproval]:
    """Normalize untrusted resume data, defaulting every missing call to deny.

    Unknown keys and malformed entries are represented as per-call invalid
    decisions only when they correspond to an expected call.  They never
    authorize another call and do not prevent valid sibling decisions from
    being used.
    """

    items = expected.items if isinstance(expected, ApprovalBatch) else tuple(expected)
    raw = resume if isinstance(resume, Mapping) else {}
    normalized: dict[str, NormalizedApproval] = {}
    for item in items:
        entry = raw.get(item.tool_call_id)
        if entry is None:
            normalized[item.tool_call_id] = NormalizedApproval(tool_call_id=item.tool_call_id)
            continue
        if isinstance(entry, ApprovalDecision):
            entry = {
                "approved": entry.approved,
                "actor": entry.actor,
                "reason": entry.reason,
                "action_digest": entry.action_digest,
            }
        if not isinstance(entry, Mapping) or not isinstance(entry.get("approved"), bool):
            normalized[item.tool_call_id] = NormalizedApproval(
                tool_call_id=item.tool_call_id,
                reason="malformed approval decision",
                error="malformed",
            )
            continue
        actor = entry.get("actor", "unknown")
        reason = entry.get("reason")
        digest = entry.get("action_digest")
        malformed_actor = not isinstance(actor, str) or not actor.strip()
        malformed_reason = reason is not None and (not isinstance(reason, str) or not reason.strip())
        if malformed_actor:
            actor = "unknown"
        if malformed_reason:
            reason = "malformed approval decision"
        elif not isinstance(reason, str) or not reason.strip():
            reason = "approved" if entry["approved"] else "denied"
        digest_valid = isinstance(digest, str) and digest == item.action_digest
        approved = bool(entry["approved"])
        valid = (digest_valid and not malformed_actor and not malformed_reason) if approved else not malformed_actor and not malformed_reason
        normalized[item.tool_call_id] = NormalizedApproval(
            tool_call_id=item.tool_call_id,
            approved=approved and digest_valid and valid,
            actor=actor,
            reason=reason if valid else "approval digest mismatch",
            action_digest=digest if isinstance(digest, str) else None,
            digest_valid=digest_valid,
            valid=valid,
            error=None if valid else ("malformed" if malformed_actor or malformed_reason else "digest_mismatch"),
        )
    return normalized


__all__ = [
    "PAYLOAD_VERSION",
    "ApprovalItem",
    "ApprovalBatch",
    "NormalizedApproval",
    "build_approval_batch",
    "normalize_resume_decisions",
]
