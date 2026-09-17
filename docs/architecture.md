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
payments, subscriptions, or external service dependencies. It must remain a
local standalone package and tolerate ordinary Dolphin and taskbar updates.
