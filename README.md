# dolphin-clean-title

[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-2ea44f.svg)](#compatibility)
[![Runtime: local-only](https://img.shields.io/badge/runtime-local--only-2ea44f.svg)](#privacy-and-external-services)

A standalone Linux package that removes one trailing `— Dolphin` or `- Dolphin`
from Dolphin window titles without modifying Dolphin or depending on a specific
taskbar.

## What it does

The package installs a managed user-local `dolphin` wrapper and a title-cleaning
service. Ordinary Dolphin launches continue to use the normal command, but the
wrapper selects Qt's XCB backend so the resulting window is visible to the
X11/XWayland title cleaner.

FileManager1 remains owned by the distro's native-Wayland
`/usr/bin/dolphin --daemon`. When that daemon launches a GUI child, the wrapper
recognizes the service cgroup and re-launches the child in a unique transient
user-systemd service. This keeps the XWayland window alive after the daemon's
activation process exits without creating an extra Home window.

The cleaner matches only Dolphin windows (`WM_CLASS=dolphin`) and removes only
one matching trailing suffix. It follows title changes while navigating and
publishes the cleaned value through `_NET_WM_NAME`.

The installed `Dolphin Clean Title` settings app provides a native GNOME
settings window for enabling or disabling the feature. The app and its
launcher remain installed when the feature is disabled. The command-line
equivalents are:

```sh
~/.local/bin/dolphin-clean-title enable
~/.local/bin/dolphin-clean-title disable
~/.local/bin/dolphin-clean-title status
~/.local/bin/dolphin-clean-title ui
```

Native Wayland Dolphin windows are deliberately outside the cleaner's reach.
On a Wayland desktop, Dolphin is supported when an accessible XWayland display
is available and the managed wrapper can be found before `/usr/bin` in `PATH`.

## Compatibility

The supported boundary is Linux with:

- Python 3.10 or newer;
- Dolphin installed as executable `/usr/bin/dolphin`;
- a usable `DISPLAY` backed by X11 or XWayland;
- `systemd-run --user` and a functioning user systemd manager; and
- the distro-provided `libX11.so.6` runtime library.

The settings app additionally requires the distribution's GTK4, libadwaita,
and PyGObject packages. The installer checks those imports before installing
the app.

Both native X11/Xorg-compatible sessions and Wayland desktops with XWayland
are supported by the implementation. The current real-machine end-to-end
verification covers GNOME Wayland with XWayland. Native Xorg and other desktop
combinations should be verified separately. A Wayland session without
`DISPLAY` is unsupported. Native-Wayland Dolphin windows are not rewritten.

## Install

From a checkout, run:

```sh
./install.sh
```

The installer validates Python, `/usr/bin/dolphin`, the X11/XWayland display,
the user systemd manager, `systemd-run`, and the required `PATH` ordering in
both the current session and user manager before it writes anything. It
installs the cleaner, the managed `~/.local/bin/dolphin` wrapper, and an XDG
autostart entry, and a `Dolphin Clean Title` application launcher.
It does not edit Dolphin, its desktop entry, FileManager1,
`plasma-dolphin.service`, Qt, GNOME Shell, or any taskbar files.

The installer retains the three most recent staged releases for safe repeated
updates and rollback recovery.

Use `./install.sh --no-start` to install the files while leaving the cleaner
stopped. The Dolphin wrapper is still installed so normal launches use the
selected XCB path after installation.

## Use

After installation, launch Dolphin normally from the application launcher, a
terminal, a directory opener, or FileManager1. The native FileManager1 daemon
is left unchanged; GUI children created through that path are placed in
temporary user-systemd units and cleaned up automatically when they exit.

The installed diagnostics are:

```sh
~/.local/bin/dolphin-clean-title --check
~/.local/bin/dolphin-clean-title --diagnose
```

The cleaner log is stored under the XDG state directory. For a foreground
diagnostic run, use:

```sh
~/.local/bin/dolphin-clean-title --verbose \
  --log-file .artifacts/dolphin-clean-title.log
```

If a shell resolved `dolphin` before installation, refresh that shell's
command cache before testing the wrapper:

```sh
hash -r                 # POSIX shells that support hash
rehash                  # shells that provide rehash instead
```

## Uninstall

From the same checkout, run:

```sh
./uninstall.sh
```

Uninstall stops the cleaner and any project-owned transient GUI units, removes
only the project's managed wrapper and data, and leaves distro-owned Dolphin
and FileManager1 files untouched. It does not remove non-managed files that
collide with project paths.

## Troubleshooting

- If installation reports that `DISPLAY` is unavailable, the session has no
  usable X11/XWayland boundary. Native Wayland alone is not sufficient.
- If installation reports a `PATH` problem, ensure `~/.local/bin` precedes
  `/usr/bin` in the graphical session environment. Refresh already-running
  shell command caches with `hash -r` or `rehash`.
- If FileManager1 windows do not appear, check that the user systemd manager's
  environment also contains the managed-wrapper directory before `/usr/bin`.
  Inspect transient units with `systemctl --user list-units --all` while a
  Dolphin window is open.
- If a title is unchanged, run `~/.local/bin/dolphin-clean-title --diagnose`.
  Only an exact case-insensitive Dolphin `WM_CLASS` instance or class is
  handled, and only the two documented suffixes are removed.
- If the settings app cannot read or change the feature state, it leaves the
  switch unavailable and shows the actionable local error instead of guessing
  the state.
- If the cleaner is not active, run `~/.local/bin/dolphin-clean-title --check`
  and inspect the XDG state log. Use the foreground command above for a local
  trace.
- If setup refuses to overwrite a file, preserve that file and review whether
  it is an existing non-managed Dolphin wrapper, cleaner launcher, autostart
  entry, or data directory. The installer refuses such collisions.

## Privacy and external services

- No telemetry
- No analytics
- No network access
- No account requirement
- No payments or subscriptions
- No external service dependencies at runtime

The `Report a Problem` row only hands the configured issue URL to the default
browser after an explicit activation. The application does not send telemetry,
diagnostics, or background network requests.

## Docs

- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Tooling](docs/tooling.md)
- [Testing](docs/testing.md)
- [Debugging](docs/debugging.md)
- [Contributing](CONTRIBUTING.md)
- [Agent instructions](AGENTS.md)
