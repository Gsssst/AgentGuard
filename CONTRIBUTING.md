# Contributing to AgentGuard

Thank you for helping make Agent tool execution safer and easier to inspect.
AgentGuard is currently an alpha-stage, learning-first project, so small,
well-tested contributions are especially valuable.

## Development setup

AgentGuard requires Python 3.11 or newer.

```bash
git clone https://github.com/Gsssst/AgentGuard.git
cd AgentGuard
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,langgraph]'
pytest -q
```

The `langgraph` extra is optional for core development but required for the
LangGraph integration tests.

## Before opening a pull request

- Keep the change focused and avoid unrelated refactors.
- Add or update deterministic tests for observable behavior.
- Run `pytest -q` and `git diff --check`.
- Document new public behavior and its known limitations.
- Do not include secrets, raw credentials, or sensitive tool arguments in
  fixtures, logs, screenshots, or error messages.
- For a core reliability boundary, include a deliberate failure scenario and
  update the relevant learning note when appropriate.

## Issues and pull requests

For a bug report, include the AgentGuard version, Python version, a minimal
reproduction, expected behavior, and actual behavior. For a feature proposal,
describe the failure mode or user workflow it addresses before proposing an
implementation.

Pull requests should explain:

1. What changed and why.
2. How the behavior was verified.
3. Which compatibility or safety boundaries remain.

Please report vulnerabilities through the process in [SECURITY.md](SECURITY.md),
not through a public issue.

## Scope

AgentGuard currently focuses on local Python Agent runtimes. Distributed locks,
hosted multi-tenancy, remote authorization, and exactly-once side effects are
outside the v0.3 scope. A proposal in one of these areas should define a narrow,
verifiable first slice.

## License

By contributing, you agree that your contribution will be licensed under the
[Apache License 2.0](LICENSE).
