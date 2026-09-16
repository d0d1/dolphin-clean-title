# Architecture

This document defines the durable boundaries of the implementation. The
project is a standalone Linux package that removes one trailing `— Dolphin` or
`- Dolphin` suffix from Dolphin window titles without modifying Dolphin or
depending on a particular taskbar.

## Support boundary and integration

The current implementation targets X11-compatible desktop sessions with a
usable `DISPLAY` and the distro-provided `libX11.so.6`. The repository's live
integration evidence is an Xwayland display with controlled X11 test windows;
native Xorg sessions and a real Dolphin process have not been verified here.
Native Wayland sessions are not supported: the standard Wayland application
protocol does not provide an external client with a way to rewrite another
client's title. The installer and service reject an unsupported session before
activation.

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

## Existing solutions and the Wayland decision

The X11 service remains justified as a focused component for this exact
behavior. The current upstream [Devilspie2 documentation](https://github.com/kba/devilspie2/blob/master/README)
describes Lua scripts running on window open and close, while its
[event setup](https://github.com/kba/devilspie2/blob/master/src/devilspie2.c)
and [script registration](https://github.com/kba/devilspie2/blob/master/src/script.c)
provide window-name getters but no title setter or title-change handler. A
window-open rule or a one-shot property command therefore cannot reliably
maintain a suffix-free title through navigation. This service instead listens
for the relevant X11 property events and publishes the cleaned EWMH value.

Native Wayland is deliberately not implemented yet. The current
[wl-relabel proxy](https://github.com/valentin-morice/wl-relabel/blob/main/src/proxy.rs)
is the closest researched architecture: it proxies a client connection and
handles `xdg_toplevel.set_title`, but its current
[tracker](https://github.com/valentin-morice/wl-relabel/blob/main/src/track.rs)
withholds identity messages until mapping and applies rule actions at that
point. Its own tests document that later title changes pass through when not
statically rewritten, and its [documented workflow](https://github.com/valentin-morice/wl-relabel/blob/main/README.md)
requires wrapping every launcher. That is not sufficient for a dynamic suffix
transformation or for launching Dolphin normally.

If native Wayland support is pursued, the smallest credible path is to extend
or adopt the protocol-transport approach used by wl-relabel and its
`wl-proxy` dependency, not to create an unrelated socket proxy. The extension
must transform every Dolphin `xdg_toplevel.set_title` request, preserve the
other protocols Dolphin uses, and account for the generated-protocol boundary
in wl-proxy: an interface not included in the proxy's generated set can be
dropped before an application handler sees it. The implementation must first
establish Dolphin's actual native-Wayland app ID across the supported KDE/Qt
matrix, then provide a verified launch integration that does not require users
to edit third-party desktop or taskbar files. Native Wayland support is not
claimed until those conditions are tested end to end.

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
