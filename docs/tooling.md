# Tooling

This document governs future technology and dependency decisions. It does not
select an implementation stack.

## Research before selection

Research technologies, tools, dependencies, and current stable versions before
selecting them. Prefer authoritative sources and the latest stable versions.
For each important version choice, document the source used to establish the
version. If a non-latest version is required, document the reason and the
source supporting that decision.

Research should consider the project's runtime boundaries, Linux packaging
requirements, update resilience, testability, maintenance cost, and offline
operation. Do not add a dependency just because it is convenient or familiar.

## Environments and dependencies

Prefer project-local or isolated environments over global installation. Agents
may add well-researched dependencies when the implementation requires them and
the decision is documented. Keep dependency resolution reproducible and avoid
untracked machine state as a requirement for development or verification.

No dependencies are added in this documentation-only foundation pass.

## Research records

Temporary research belongs under the ignored `.agent/` directory. Only reviewed
and durable conclusions belong in tracked documentation; public tracked
documentation must not contain raw research notes, prompts, conversation
history, internal prose, or temporary reasoning.
