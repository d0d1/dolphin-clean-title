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
files, directories, or hosted infrastructure for possible future tools.

## Local workflow

The implementation is deliberately runnable from a checkout without a
dependency installation. Use `make check` for the full deterministic test and
syntax-check suite. The live X11 integration and packaging tests require a
usable `DISPLAY`; pure unit tests remain useful without it.

Use `./install.sh` to install the current checkout for the current user,
`./install.sh --no-start` when only the files should be activated, and
`./uninstall.sh` to stop the service, collect project-owned transient GUI
units, and remove only files managed by this project. Installation also
manages `~/.local/bin/dolphin`, which selects XCB
for ordinary launches and uses transient user-systemd units for FileManager1
GUI children. It never creates a persistent override for the vendor Dolphin
unit. `--no-start` stops an older running instance and leaves the cleaner
service stopped. Successful updates retain the three most recent staged
releases. `~/.local/bin/dolphin-clean-title --diagnose` reports the
local compatibility boundary, Dolphin process hints, and matching windows.
Keep temporary research in
`.agent/research/` and generated logs or dumps in `.artifacts/`.

The production settings app uses the shared lifecycle API rather than
managing activation files or processes itself. Keep its XDG application
launcher installed even when the feature is disabled, and preserve the
configured state across updates. Verify UI changes through the installed
launcher as well as deterministic lifecycle tests; do not introduce a second
state store or a separate UI-only implementation of enable/disable.

## CI and hosted infrastructure

This project uses no GitHub Actions. If continuous integration becomes
necessary, research CI alternatives first, compare their operational and
maintenance implications, and document the decision before configuration is
added. Any selected alternative must use checks that are reproducible locally.
The exact local command used by CI, if an alternative is later selected, must
remain the source of truth for verification. Do not create CI configuration as
part of preparatory work.

## GitHub topics

Choose five to ten GitHub topics that accurately describe the project as it
currently exists. Use fewer when five strongly relevant topics cannot be
identified. Do not add implementation-language or framework topics before
those technologies are selected, and do not add generic topics merely to reach
a count. Revisit topics when the supported boundary or project purpose
changes; topics must describe the repository today, not an aspirational
roadmap.

## Change discipline

Keep implementation, packaging, documentation, and diagnostics as separate
concerns. Verify changes with deterministic checks appropriate to the known
implementation stack. Record durable conclusions in tracked documentation and
keep temporary research under the ignored `.agent/research/` directory.

Do not install dependencies or add infrastructure without a documented need
and a selected, researched implementation stack. Use Conventional Commits
1.0.0 for repository history; the detailed commit policy is in
[Contributing](../CONTRIBUTING.md).
