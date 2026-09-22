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

Use `make check` for the full deterministic test and syntax-check suite. The
live X11 integration checks require a usable `DISPLAY`; the pure unit tests
remain useful without a graphical session.

The supported end-user installation is the Debian package described below.
`./install.sh` is retained only as a source-checkout development workflow;
`./install.sh --no-start` is useful for testing staging without starting the
cleaner, and `./uninstall.sh` removes that user-local development installation.
The source installer manages `~/.local/bin/dolphin`, which selects XCB for
ordinary launches and uses transient user-systemd units for FileManager1 GUI
children. It never creates a persistent override for the vendor Dolphin unit.
It refuses unmanaged collisions rather than overwriting them. Successful
source updates retain the three most recent staged releases.

Keep temporary research in `.agent/research/` and generated logs or dumps in
`.artifacts/`.

The production settings app uses the shared lifecycle API rather than
managing activation files or processes itself. Keep its XDG application
launcher installed even when the feature is disabled, and preserve the
configured state across updates. Verify UI changes through the installed
launcher as well as deterministic lifecycle tests; do not introduce a second
state store or a separate UI-only implementation of enable/disable.

## Debian package

The canonical distribution artifact is `dolphin-clean-title`, built for the
Ubuntu 24.04 (`noble`) package boundary. The package installs the command and
Python runtime under `/usr/bin` and `/usr/lib/dolphin-clean-title`, and the
desktop entry under `/usr/share/applications`. Its minimal maintainer scripts
manage only `/var/lib/dolphin-clean-title/install-id`; they never infer a
desktop user, traverse a home directory, or start user processes.

Build the binary package from a clean checkout with the distribution's
`debhelper` and `dpkg-dev` packages available:

```sh
make check
make package
```

The resulting `.deb` is written to the parent directory. Inspect it before
installation:

```sh
dpkg-deb -I ../dolphin-clean-title_0.1.0-1_all.deb
dpkg-deb -c ../dolphin-clean-title_0.1.0-1_all.deb
sha256sum ../dolphin-clean-title_0.1.0-1_all.deb
```

A fresh package install is intentionally disabled. Enabling creates only the
user-local wrapper, autostart entry, state, and current package install-id
association needed by the feature. Package upgrades preserve the system
install-id and user state. Removing the package removes the system identity;
an enabled leftover user state is then stale and the wrapper falls back to
ordinary `/usr/bin/dolphin`. Reinstalling therefore remains disabled until the
user explicitly enables the feature again. Disabling before removal is still
the cleanest cleanup path, while raw removal remains safe without touching a
user home directory. Source-checkout and package installations use separate
paths and do not overwrite each other's files. When switching from a source
checkout to the package, uninstall the source checkout first so its user
desktop entry does not shadow the packaged launcher; the source installer still
refuses unmanaged collisions in its own user-local paths.

Packaged cleaner processes are bound to the install identity that authorized
their start and stop when that identity disappears or changes, even if a fast
remove-and-reinstall cycle recreates the runtime files before the older process
observes their absence. Normal upgrades preserve the identity and do not
invalidate a running cleaner. Source-development processes do not use this
package-generation binding.

## Release and PPA preparation

A maintainer preparing a release should:

1. run `make check` and `make package`;
2. inspect package metadata, file layout, dependencies, and the generated
   checksum;
3. create the matching version tag and manually attach the `.deb` and checksum
   file to a GitHub Release; and
4. for a PPA, build a signed source package with an upstream archive generated
   from that tag, then run `dpkg-buildpackage -S -sa`, verify the resulting
   `.dsc` and source archives, and upload the signed `.changes` file with
   `dput` only after a concrete Launchpad PPA target exists. In the
   `3.0 (quilt)` format, the upstream `.orig.tar.xz` and Debian
   `.debian.tar.xz` are separate inputs; the release checkout must retain its
   `debian/` directory for `dpkg-buildpackage`, while the upstream archive
   intentionally excludes it. This follows the [Debian `dpkg-source` format
   documentation](https://manpages.debian.org/bookworm/dpkg-dev/dpkg-source.1.en.html)
   and the [Debian New Maintainers' Guide](https://www.debian.org/doc/maint-guide/maint-guide.en.pdf).
   From a clean checkout containing the release tag, prepare the source package
   with:

   ```sh
   VERSION=0.1.0
   TAG="v${VERSION}"
   git archive --format=tar \
     --prefix="dolphin-clean-title-${VERSION}/" "$TAG" -- . \
     ':(exclude)debian' \
     | xz -c > "../dolphin-clean-title_${VERSION}.orig.tar.xz"
   dpkg-buildpackage -S -sa
   ```

   Run both commands from the release checkout after the tag exists. The
   generated `.orig.tar.xz` must not contain `debian/`; `dpkg-buildpackage`
   reads the retained checkout's `debian/` directory and generates the Debian
   source archive beside the upstream archive.

The Debian changelog is the package-version source of truth. Keep the upstream
Python version and Debian upstream version aligned; use a Debian revision such
as `-1` for packaging-only rebuilds.

## CI and hosted infrastructure

This project uses no GitHub Actions. If continuous integration becomes
necessary, research CI alternatives first, compare their operational and
maintenance implications, and document the decision before configuration is
added. Any selected alternative must use checks that are reproducible locally.
The exact local command used by CI, if an alternative is later selected, must
remain the source of truth for verification. Do not create CI configuration as
part of preparatory work.

## Change discipline

Keep implementation, packaging, documentation, and diagnostics as separate
concerns. Verify changes with deterministic checks appropriate to the known
implementation stack. Record durable conclusions in tracked documentation and
keep temporary research under the ignored `.agent/research/` directory.

Do not install dependencies or add infrastructure without a documented need
and a selected, researched implementation stack. Use Conventional Commits
1.0.0 for repository history; the detailed commit policy is in
[Contributing](../CONTRIBUTING.md).
