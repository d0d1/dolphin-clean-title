# Contributing

Contributions should preserve the project's purpose, boundaries, and small
runtime footprint. Before proposing a change, read the authoritative project
documents:

- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Tooling](docs/tooling.md)
- [Testing](docs/testing.md)
- [Debugging](docs/debugging.md)

## Commit messages

Use [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
Use a lowercase type and an optional scope followed by a concise description,
for example `docs: clarify title handling` or `fix: preserve an existing title`.
Use the body and footers when they add useful context, and describe breaking
changes with the Conventional Commits `!` marker or `BREAKING CHANGE:` footer.

## Badge policy

Use three to six badges when each one represents real current project
information or materially improves presentation; use fewer or none when that
standard cannot be met. Do not add placeholder badges, CI badges without CI,
release or package badges without corresponding releases or packages, or
technology badges before the implementation stack is selected.

## Documentation hygiene

Public tracked documentation must contain no internal prose, prompts,
conversation history, raw research notes, or temporary reasoning. Keep
temporary research under the ignored `.agent/` directory and publish only
reviewed, durable conclusions in tracked documentation.

## Changes and review

Keep changes focused and reproducible. Do not add speculative infrastructure,
implementation scaffolding, dependencies, or CI configuration without a
well-supported need and the corresponding project documentation. Explain
user-visible behavior, compatibility considerations, and verification results
in the change description when relevant.
