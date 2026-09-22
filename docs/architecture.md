# Architecture

This document defines the durable implementation boundaries for
dolphin-clean-title.

## Runtime boundary

The project has two cooperating user-local pieces:

1. A Python standard-library service connects to the X11 protocol through the
   distro's `libX11.so.6`, observes Dolphin windows and title-property changes,
   and publishes cleaned `_NET_WM_NAME` values.
2. A managed `~/.local/bin/dolphin` wrapper selects Qt's XCB backend for
   Dolphin GUI processes. Ordinary launches execute `/usr/bin/dolphin`
   directly. A wrapper process inside the vendor `plasma-dolphin.service`
   cgroup starts `/usr/bin/dolphin` in a uniquely named transient user-systemd
   service so the GUI process does not inherit the daemon's short-lived
   activation cgroup.

The installed settings application is a separate presentation layer. Its
libadwaita window calls a shared feature-lifecycle API for `enable`, `disable`,
`is_enabled`, and `status`; it does not edit activation files or manage
processes directly. The lifecycle layer owns persistent enabled/disabled
state, collision checks, rollback, and service transitions. A managed desktop
entry launches the settings app through the installed command wrapper and is
kept when the feature is disabled.

The Debian package installs the command, Python runtime, settings launcher,
and a system-owned install identity under `/var/lib/dolphin-clean-title`.
Its minimal `postinst`/`postrm` scripts create, preserve, or remove only that
system file; they never infer a desktop user, traverse a home directory, or
start a user process. The lifecycle API accepts either the managed
source-checkout command or the managed packaged command; activation files and
state remain user-specific in both cases. A fresh package install has no
activation and reports disabled until the user enables it.

Packaged enabled state is associated with the current system install identity.
An enabled state with a missing or mismatched per-user identity is stale and
is treated as disabled; it is never reactivated implicitly. Explicit enable
writes the current identity, while explicit disable clears it. This makes a
remove-and-reinstall cycle safe without package scripts modifying user state.

Every packaged cleaner start is authorized against the current enabled state
and carries the exact install identity that authorized it into the foreground
process. The foreground process binds itself to that identity, checks it while
running, and stops before further rewriting if the identity disappears,
becomes invalid, or changes. This covers explicit enable, launch preparation,
autostart, and direct packaged service starts; source-checkout services remain
outside this package-generation boundary. The runtime sentinel remains an
additional fail-closed defense, and service readiness identifies the expected
generation rather than trusting only a PID.

The vendor `plasma-dolphin.service` and its FileManager1 D-Bus service file
remain untouched. The native `/usr/bin/dolphin --daemon` therefore continues to
use the desktop's native Wayland backend. The wrapper changes only the GUI
children that it launches.

Transient GUI units use `--user`, `--no-block`, `--collect`, and
`QT_QPA_PLATFORM=xcb`. Their commands use the absolute `/usr/bin/dolphin`
path, preventing wrapper recursion. Unit names combine a high-resolution time
value and the wrapper PID to avoid collisions.

## Support boundary

The cleaner operates at the X11/XWayland boundary. Supported environments are:

- native X11/Xorg-compatible sessions with a usable `DISPLAY`; and
- Wayland desktops with a usable XWayland `DISPLAY`, a user systemd manager,
  `systemd-run --user`, `/usr/bin/dolphin`, and `~/.local/bin` before `/usr/bin`
  in the relevant launch `PATH`.

Native Wayland Dolphin windows are explicitly outside the cleaner's reach.
The project does not proxy the native Wayland protocol and does not pretend to
rewrite a Wayland client's `xdg_toplevel.set_title` requests. On a Wayland
desktop, the supported workflow is to launch Dolphin GUI windows through the
managed XCB wrapper while leaving the native FileManager1 daemon alone.

The installer rejects sessions without a usable X11/XWayland display and
rejects launch environments where the managed wrapper cannot precede
`/usr/bin`. It also requires `systemd-run` for the FileManager1 child path.
The settings app is available only when the installed GTK4, libadwaita, and
PyGObject runtime can be imported; a failed state read or transition is shown
as an error and never presented as a guessed switch state.

## Title-cleaning behavior

The title rule is pure logic: remove exactly one trailing `— Dolphin` or
`- Dolphin`, including one optional separating space immediately before the
suffix. Other case, punctuation, whitespace, and embedded occurrences remain
unchanged.

The X11 adapter identifies a window only when its `WM_CLASS` instance or class
is exactly `dolphin`, case-insensitively. It reads `_NET_WM_NAME`, falling back
to `WM_NAME`, subscribes to new-window and property events, and rewrites the
EWMH title seen by window managers and compositors that honor the standard.
It tracks titles it changed so a clean shutdown can restore the last title it
still owns. It does not edit Dolphin, Qt, a desktop entry, a taskbar, or a
desktop shell.

## Structural principles

Require professional structural quality from the beginning. Keep title rules,
session validation, X11 access, application lifecycle, wrapper generation,
installation, diagnostics, and tests as distinct responsibilities.

Avoid monoliths, circular dependencies, dumping-ground modules, inappropriate
coupling, and unjustified abstractions. Every abstraction must make a real
boundary or behavior easier to verify and maintain.

The runtime must have no telemetry, analytics, network access, accounts,
payments, subscriptions, or external service dependencies. The explicit
`Report a Problem` action may hand its fixed issue URL to the user's default
browser through Gio; no request is made automatically by this project. It must
remain a local standalone package and tolerate ordinary Dolphin and taskbar
updates.
