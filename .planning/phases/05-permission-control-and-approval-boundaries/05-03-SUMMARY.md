# Phase 5 Wave 3 Summary

- Added canonical SHA-256 action binding over Tool, raw canonical arguments, capabilities, run ID, and step.
- Added recursive, case-insensitive audit redaction for common secret field names.
- Added permission and approval event vocabulary.
- Extended `ReliabilityReport` with evidence-derived permission, approval, and waiting counters.
- Added aligned Chinese and English learning notes with verified behavior and explicit limitations.

Verification: `PYTHONPATH=src pytest -q` -> 85 passed. Digest input remains unredacted for binding integrity; audit projections remain redacted.
