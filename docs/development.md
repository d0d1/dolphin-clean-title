# Development

## Workflow policy

Prefer agent-autonomous, reproducible, noninteractive workflows. Commands
should be runnable from a clean checkout, have explicit inputs, and produce
diagnostics that an agent can inspect without requiring a user to drive a GUI
or answer routine questions.

Prefer agent maintainability over human convenience when software quality is
not harmed. Keep procedures explicit, local, scriptable, and easy to repeat.

Do not create speculative infrastructure. Add structure only when an approved
implementation or a demonstrated workflow requires it; do not add placeholder
files or directories for possible future tools.

## CI and hosted infrastructure

This project uses no GitHub Actions. If continuous integration becomes
necessary, research CI alternatives first, compare their operational and
maintenance implications, and document the decision before configuration is
added. Do not create CI configuration as part of preparatory work.

## GitHub topics

Choose five to ten GitHub topics that accurately describe the project as it
currently exists. Use fewer when five strongly relevant topics cannot be
identified. Do not add implementation-language or framework topics before
those technologies are selected, and do not add generic topics merely to
reach a count.

## Change discipline

Keep implementation, packaging, documentation, and diagnostics as separate
concerns. Verify changes with deterministic checks appropriate to the known
implementation stack. Record durable conclusions in tracked documentation and
keep temporary research under the ignored `.agent/` directory.

Do not install dependencies or scaffold implementation, test, or tooling
directories without a documented need and a selected, researched
implementation stack.
