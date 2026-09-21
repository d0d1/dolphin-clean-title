# dolphin-clean-title

[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-2ea44f.svg)](#compatibility)
[![Runtime: local-only](https://img.shields.io/badge/runtime-local--only-2ea44f.svg)](#privacy-and-external-services)

A standalone Linux package that removes one trailing `— Dolphin` or `- Dolphin`
from Dolphin window titles without modifying Dolphin or depending on a specific
taskbar.

<img src="docs/images/dolphin-clean-title-ui.png"
    alt="Dolphin Clean Title settings"
    width="450">

## Install

Dolphin Clean Title is preparing its first packaged release for Ubuntu 24.04 LTS.

For development and source-build instructions, see [Development and packaging](docs/development.md).

## Use

Open `Dolphin Clean Title` from the application launcher and enable the switch.
Then launch Dolphin normally from the launcher, a terminal, a directory opener,
or FileManager1. The title cleaner starts automatically for the session.

To disable the feature, turn the switch off or run:

```sh
dolphin-clean-title disable
```

## Compatibility

The verified release boundary is Ubuntu 24.04 LTS on Linux with Dolphin,
Python 3.10+, a usable X11 or XWayland `DISPLAY`, and a user systemd manager.
GNOME Wayland with XWayland is verified. Native Wayland Dolphin windows and
Wayland sessions without XWayland are outside the supported boundary.

## Uninstall

Disabling the feature first is the cleanest removal path, but removal while it
is enabled is also safe:

```sh
dolphin-clean-title disable
sudo apt remove dolphin-clean-title
```

The package does not run maintainer scripts that modify a user's home
directory. If the package is removed while the feature is enabled, the
running packaged cleaner detects that its runtime is gone and stops; the
remaining user-local Dolphin wrapper also falls back to ordinary
`/usr/bin/dolphin` launches. Reinstalling the package restores the packaged
runtime without replacing the user's activation state.

## Privacy and external services

- No telemetry
- No analytics
- No network access
- No account requirement
- No payments or subscriptions
- No external service dependencies at runtime

The optional `Report a Problem` action only delegates an explicitly requested
issue page to the default browser; the application itself makes no request.

## Docs

- [Architecture](docs/architecture.md)
- [Development and packaging](docs/development.md)
- [Tooling](docs/tooling.md)
- [Testing](docs/testing.md)
- [Debugging](docs/debugging.md)
- [Contributing](CONTRIBUTING.md)
- [Agent instructions](AGENTS.md)
