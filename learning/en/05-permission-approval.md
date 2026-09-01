# Phase 5: Permission Control and Approval

## What this phase teaches

AgentGuard adds four fixed Tool capability labels: `read`, `write`, `external`, and `destructive`. A Tool may carry multiple labels. Registration validates the metadata and rejects blank, non-string, or unknown labels immediately.

Once a `PermissionPolicy` is configured, authorization is fail-closed: a Tool is allowed only when every label is in `allowed`; if at least one label is configured for human approval, the result is `approval_required`; otherwise the action is directly denied. With no policy configured, the existing Runtime and ToolExecutor behavior remains unchanged.

An approval-required Action never calls the Tool before approval. The Runtime marks the state as `WAITING_APPROVAL`, stores the pending Action, capabilities, and action digest in a checkpoint, and waits for an explicit `resume()` call. Resume recomputes and validates the digest before accepting the decision. A missing decision, digest mismatch, or rejection produces no Tool side effect. An approval executes only the original pending Action from the checkpoint, then returns to the Router loop.

The digest is a SHA-256 binding over the Tool name, canonical raw arguments, capability labels, `run_id`, and `step`. Audit events use a recursive redacted argument projection covering names such as password, token, secret, api_key, access_key, private_key, and authorization. The digest is deliberately computed from the unredacted value.

## Verified and deferred

The verified behaviors are capability validation, three-way policy decisions, waiting-checkpoint round trips, explicit approval resume, digest validation, zero Tool side effects before approval, structured events, and the full regression suite:

```text
PYTHONPATH=src pytest -q
83 passed
```

`actor` is a caller-provided audit label, not an authenticated identity. Version one does not implement RBAC, real authentication, an approval UI, a remote approval service, distributed durability, concurrent resource locks, or claims of exactly-once execution or production-grade approval infrastructure.
