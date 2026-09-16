# dolphin-clean-title

[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Platform: Linux / X11](https://img.shields.io/badge/platform-Linux%20%2F%20X11-2ea44f.svg)](#compatibility)
[![Runtime: local-only](https://img.shields.io/badge/runtime-local--only-2ea44f.svg)](#privacy-and-external-services)

A standalone Linux package that removes a trailing `— Dolphin` or `- Dolphin`
from Dolphin window titles without modifying Dolphin or depending on a
specific taskbar.

## What it does

After installation, a small user-local background service watches X11 window
events and Dolphin title changes. It matches only windows whose `WM_CLASS`
instance or class is exactly `dolphin` (case-insensitively), removes one
supported trailing suffix, and publishes the cleaned value through the EWMH
`_NET_WM_NAME` property. Window managers and compositors that use that
property can therefore display the cleaned title.

Dolphin continues to be launched normally. The service is independent of
Dolphin and taskbar files, so ordinary updates to either do not overwrite it.
Installation is user-local and repeated installation activates a new staged
copy without leaving the previous service running.

## Compatibility

This release candidate supports Linux X11 desktop sessions with:

- Python 3.10 or newer;
- a usable `DISPLAY`; and
- the distro-provided `libX11.so.6` runtime library.

Native Wayland sessions are not supported by this release. The installer
detects that boundary and fails before activation. The service is intended for
window managers or compositors that honor the standard EWMH title property;
behavior outside that boundary has not been claimed or verified.

The repository's full suite has been run with Python 3.12.3 on Linux using an
Xwayland X11 display. Other Python versions and desktop combinations at or
above the enforced baseline require their own verification.

## Install

From a checkout, run:

```sh
./install.sh
```

The installer validates the current session, copies the package into a
versioned user-local data directory, creates an XDG autostart entry, and
starts the service. No manual edits to Dolphin, a taskbar, or a desktop shell
are required. Use `./install.sh --no-start` to install the files without
starting the current session's service.

## Use

Launch Dolphin normally. The service handles new windows and title changes
while navigating. The installed diagnostic commands are:

```sh
~/.local/bin/dolphin-clean-title --check
~/.local/bin/dolphin-clean-title --diagnose
```

The service log is stored under the XDG state directory. For a foreground
diagnostic run, use `--verbose --log-file .artifacts/dolphin-clean-title.log`.

## Uninstall

From the same checkout, run:

```sh
./uninstall.sh
```

This stops the service, restores title properties it still owns on open
windows, and removes the project's XDG autostart entry, wrapper, and staged
data. It preserves files that are not marked as managed by this project,
restoring Dolphin's original title behavior.

## Troubleshooting

- If installation reports that the session is unsupported, check
  `XDG_SESSION_TYPE` and `DISPLAY`. This release requires an X11 desktop
  session; native Wayland sessions are not supported.
- If a title is unchanged, run
  `~/.local/bin/dolphin-clean-title --diagnose` and inspect the reported
  matching windows. Only an exact `dolphin` `WM_CLASS` instance or class is
  handled, and only the two documented suffixes are removed.
- If the service is not active, run
  `~/.local/bin/dolphin-clean-title --check`, then inspect the log under the
  XDG state directory. A foreground trace can be collected with
  `~/.local/bin/dolphin-clean-title --verbose --log-file .artifacts/dolphin-clean-title.log`.
- If setup refuses to overwrite a file, preserve that file and review whether
  it is an existing non-managed wrapper, autostart entry, or data directory.
  The installer refuses such collisions rather than deleting user data.

## Privacy and external services

- No telemetry
- No analytics
- No network access
- No account requirement
- No payments or subscriptions
- No external service dependencies at runtime

## Docs

- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Tooling](docs/tooling.md)
- [Testing](docs/testing.md)
- [Debugging](docs/debugging.md)
- [Contributing](CONTRIBUTING.md)
- [Agent instructions](AGENTS.md)
