# Phase 5: Permission Control and Approval Boundaries - Discussion Log

> **Audit trail only.** Decisions are captured in `05-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-09-01
**Phase:** 05-permission-control-and-approval-boundaries
**Areas discussed:** Tool capability tags, permission policy, approval lifecycle, audit evidence, approval binding

---

## Tool capability tags

| Option | Description | Selected |
|--------|-------------|----------|
| Risk levels | `low/medium/high`, simple but coarse | |
| Capability tags | `read/write/external/destructive`, composable and explainable | ✓ |
| Capability + risk | Most expressive, but more complex for V1 | |

**User's choice:** Capability tags.
**Notes:** Tags are fixed to four initial values; one Tool may have multiple tags and unknown tags are rejected during registration.

---

## Permission policy

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit allow-list | Enabled policy is fail-closed; unallowed capability is denied | ✓ |
| Deny only destructive | Permissive default, weaker safety boundary | |
| Optional policy only | No policy preserves old behavior; policy is opt-in | ✓ |

**User's choice:** Combine explicit allow-list with optional policy compatibility.
**Notes:** When no policy is configured, Phase 1–4 behavior remains unchanged.

---

## Approval lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Distinguish deny and approval | Forbidden tools fail; approvable tools pause and resume | ✓ |
| Deny all unallowed tools | No human approval flow | |
| Approve all unallowed tools | Too permissive for an initial safety boundary | |

**User's choice:** Distinguish direct denial from approval-required tools.
**Notes:** Pending actions enter `WAITING_APPROVAL`, are checkpointed, and continue through explicit `resume()` after approval.

---

## Audit evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Full arguments | Debuggable but may leak secrets | |
| Redacted arguments | Readable while masking common sensitive fields | ✓ |
| Argument summary only | Strong privacy, weaker operator visibility | |

**User's choice:** Redacted arguments.
**Notes:** Recursive key-name redaction covers password/token/secret/API-key style fields; Tool-specific extra sensitive fields may be added later.

---

## Approval binding

| Option | Description | Selected |
|--------|-------------|----------|
| No binding | Simple but vulnerable to approval reuse or parameter changes | |
| Stable action digest | Bind tool, normalized args, capabilities, run_id, and step | ✓ |
| Full signed token system | Stronger but requires identity/crypto infrastructure | |

**User's choice:** Stable action digest.
**Notes:** Optional `actor` is recorded as an audit label, not authentication; digest mismatch rejects resume.

---

## the agent's Discretion

- Exact Python class names, enum inheritance, error hierarchy, event field order, and hash algorithm.
- Minimal compatibility mapping between `WAITING_APPROVAL`, RunStatus, and checkpoint lifecycle.

## Deferred Ideas

- RBAC/ABAC and real user identity.
- External approval service or UI.
- Resource locks, concurrency, framework adapters, and distributed approval storage.
