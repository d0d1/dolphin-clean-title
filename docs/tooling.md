# Tooling

Apply this policy before selecting or changing the implementation stack.

## Research before selection

Research technologies, tools, dependencies, and versions before selecting them.
Prefer authoritative sources and use the latest stable versions by default.
Document the source used to establish every important selected version.
Document a justification and supporting source for every non-latest version.

Research should consider the project's runtime boundaries, Linux packaging
requirements, update resilience, testability, maintenance cost, and offline
operation. Do not add a dependency just because it is convenient or familiar.

## Environments and dependencies

Prefer project-local or isolated environments over global installation. Agents
may add dependencies only when the implementation requires them, they have
been properly researched, and the decision is documented. Keep dependency
resolution reproducible and avoid untracked machine state as a requirement for
development or verification.

## Research records

Temporary research belongs under the ignored `.agent/research/` directory,
within `.agent/`. Only reviewed and durable conclusions belong in tracked
documentation; public tracked documentation must not contain raw research
notes, prompts, conversation history, internal prose, or temporary reasoning.
