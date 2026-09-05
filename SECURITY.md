# Security Policy

## Supported versions

AgentGuard is currently an alpha-stage project. Security fixes are applied to
the latest `0.3.x` release line; versions earlier than `0.3` are unsupported.

| Version | Supported |
| --- | --- |
| 0.3.x | Yes |
| < 0.3 | No |

## Reporting a vulnerability

Please do not open a public issue for a vulnerability, exploit, exposed secret,
or report containing sensitive tool arguments. Use GitHub's private security
advisory reporting for this repository instead:

1. Open the repository's **Security** tab.
2. Select **Advisories** and **Report a vulnerability**.
3. Include the affected version, a minimal reproduction, expected impact, and
   any suggested mitigation.

Reports are reviewed on a best-effort basis. Please allow time to reproduce and
assess the issue before publishing details.

## v0.3 security boundaries

AgentGuard v0.3 provides local runtime guardrails; it is not a production
authorization service or security sandbox.

- Resource locks, event sinks, and runtime state are process-local.
- External side effects are not guaranteed to execute exactly once.
- Human-facing approval payloads are redacted, but trusted checkpoint state may
  retain original tool arguments so their approval digest can be recomputed.
- Tool implementations still run with the permissions of the host process.
- There is no tenant isolation, distributed lock, remote policy service, or
  high-availability guarantee.

Applications using AgentGuard must still validate untrusted input, protect
credentials, restrict host permissions, and secure checkpoint and event files.
