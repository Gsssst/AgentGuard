"""Optional integrations for external Agent frameworks."""

from .approval import (
    ApprovalBatch,
    ApprovalItem,
    NormalizedApproval,
    build_approval_batch,
    normalize_resume_decisions,
)

__all__ = [
    "ApprovalBatch",
    "ApprovalItem",
    "NormalizedApproval",
    "build_approval_batch",
    "normalize_resume_decisions",
]
