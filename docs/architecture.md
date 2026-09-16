# Architecture

This document defines the durable boundaries of the implementation. The
project is a standalone Linux package that removes one trailing `— Dolphin` or
`- Dolphin` suffix from Dolphin window titles without modifying Dolphin or
depending on a particular taskbar.

## Support boundary and integration

The current release candidate supports X11 desktop sessions with a usable
`DISPLAY` and the distro-provided `libX11.so.6`. Native Wayland sessions are
not supported: an external client cannot use the Wayland application protocol
to rewrite another client's title. The installer and service reject an
unsupported session before activation.

The service observes the X11 root window and subscribes to window lifecycle
and title-property changes. It identifies a Dolphin window only when its
`WM_CLASS` instance or class is exactly `dolphin`, case-insensitively. For a
matching window, it reads `_NET_WM_NAME` (falling back to `WM_NAME`) and writes
the cleaned value to `_NET_WM_NAME`. That is the EWMH-facing title consumed by
window managers and compositors that implement the standard. New windows,
navigation-driven title changes, and repeated updates are handled by the same
event loop. The service changes no Dolphin or taskbar files.

Installation is user-local. A versioned release directory and an atomic
`current` link keep ordinary updates from overwriting the active service, and
an XDG autostart entry starts the service while Dolphin itself continues to be
launched normally.

## Structural principles

Require professional structural quality from the beginning.

Require clean separation of concerns. Give each component a clear
responsibility: title rules are pure logic; session validation is separate
from X11 access; the X11 adapter owns window events and EWMH properties; the
application owns lifecycle and diagnostics; packaging owns installation and
removal; and tests exercise each boundary.

Avoid monoliths, circular dependencies, dumping-ground modules, inappropriate
coupling, and unjustified abstractions. Every abstraction should earn its
place by making a real boundary or behavior easier to verify and maintain.

The implementation must not modify Dolphin, patch Dolphin files, or require a
specific taskbar. Integration must target the appropriate window-system
boundary so the cleaned title is exposed to the window manager or compositor.
The design must tolerate ordinary updates to Dolphin and taskbars.

## Runtime constraints

The runtime must have no telemetry, analytics, network access, accounts,
payments, subscriptions, or external service dependencies. It must operate as
a local standalone package and avoid introducing an online control plane.

Changes to the stack or runtime boundary must follow the research and version
policy in [Tooling](tooling.md) without weakening these boundaries.
