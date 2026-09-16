# Agent instructions

This repository contains the implementation, user-local packaging, tests, and
public documentation. Keep the project small and avoid speculative
scaffolding: add structure only when it supports a real, researched feature or
verification workflow.

## Authoritative project policy

Read and follow these documents before making changes:

- [Architecture](docs/architecture.md) defines boundaries and runtime
  constraints.
- [Development](docs/development.md) defines workflow and infrastructure
  policy.
- [Tooling](docs/tooling.md) defines research, version, dependency, and
  environment policy.
- [Testing](docs/testing.md) defines verification policy.
- [Debugging](docs/debugging.md) defines diagnosis and artifact policy.
- [Contributing](CONTRIBUTING.md) defines commit-message and documentation
  hygiene policy.

These documents are authoritative for their respective subjects. If a change
would conflict with them, update the relevant policy deliberately before
implementing the change.

## Required compliance

- Keep the runtime free of telemetry, analytics, network access, accounts,
  payments, subscriptions, and external service dependencies.
- Keep concerns cleanly separated and avoid monoliths, circular dependencies,
  dumping-ground modules, inappropriate coupling, and unjustified
  abstractions.
- Prefer agent-autonomous, reproducible, deterministic, scriptable,
  noninteractive workflows and automated verification.
- Perform testing and debugging autonomously whenever practical, collecting
  enough local evidence to diagnose failures without routine user assistance.
- Select testing tools only after the implementation stack is known.
- Research technologies, tools, dependencies, and versions before selecting or
  installing them; prefer authoritative sources, latest stable versions, and
  project-local or isolated environments. Document important version choices
  and any reason for using an older version.
- Do not add GitHub Actions. If CI becomes necessary, research alternatives
  before selecting one.
- Keep temporary research under ignored `.agent/research/` and generated
  diagnostics under `.artifacts/`; neither belongs in tracked documentation.
- Design debugging with actionable logs, environment and version diagnostics,
  reproducible checks, and useful failure artifacts once implementation exists.
- Avoid speculative scaffolding and unnecessary dependencies. Prefer the
  project's local or isolated environment when one is appropriate.
- Use Conventional Commits 1.0.0 and keep public tracked documentation free
  of internal prose, prompts, conversation history, raw research notes, and
  temporary reasoning.

Before finishing, verify the change against all authoritative documents and
confirm that no speculative scaffolding or unresearched dependency was added.
