# Tooling

Apply this policy before selecting or changing the implementation stack. The
current selection and its evidence are recorded below.

## Research before selection

Research technologies, tools, dependencies, and versions before selecting
them. Prefer authoritative sources and use the latest stable versions by
default. Document the source used to establish every important selected
version. Document a justification and supporting source for every non-latest
version.

Research should consider the project's runtime boundaries, Linux packaging
requirements, update resilience, testability, maintenance cost, and offline
operation. Do not add a dependency just because it is convenient or familiar.

## Environments and dependencies

Prefer project-local or isolated environments over global installation. Agents
may add dependencies only when the implementation requires them, they have
been properly researched, and the decision is documented. Keep dependency
resolution reproducible and avoid untracked machine state as a requirement for
development or verification.

## Current selection

- Python 3.10 or newer is the implementation and packaging baseline. Python
  3.14.7 is the latest stable release established for this release candidate
  by the [official Python release page](https://www.python.org/downloads/release/python-3147/).
  The minimum is intentionally older than latest to match common supported
  Linux distributions while using only stable standard-library APIs. This is
  the documented justification for the non-latest minimum; the running
  interpreter must still be checked before installation.
- The runtime uses only the Python standard library, including
  [`ctypes`](https://docs.python.org/3/library/ctypes.html) for the distro's
  X11 client library. There are no third-party runtime dependencies or
  dependency lockfiles to install.
- The X11 adapter follows the [Xlib reference](https://www.x.org/releases/current/doc/libX11/libX11/libX11.html)
  for display, property, event, and window operations. It uses the EWMH
  `_NET_WM_NAME` property described by the [Extended Window Manager Hints
  specification](https://specifications.freedesktop.org/wm-spec/latest/ar01s05.html).
- User-session persistence uses an XDG autostart desktop entry following the
  [Desktop Application Autostart Specification](https://specifications.freedesktop.org/autostart/latest/).
- The test suite uses Python's standard `unittest` module and a live X11
  integration test. No test framework was added before the implementation
  stack was known.

## Evaluated alternatives

The current upstream [Devilspie2 source](https://github.com/kba/devilspie2/blob/master/src/devilspie2.c)
and [documentation](https://github.com/kba/devilspie2/blob/master/README) were
reviewed before retaining the X11 implementation. Its current source connects
window-opened and window-closed signals, and its
[script registration](https://github.com/kba/devilspie2/blob/master/src/script.c)
registers getters such as `get_window_name`; the current
[VERSION file](https://github.com/kba/devilspie2/blob/master/VERSION) reports
0.39. It does not register a title-setting function or a generic title-change
callback. It is useful for general X11 window rules but does not replace this
project's event-driven dynamic title rewrite.

The current [wl-relabel manifest](https://github.com/valentin-morice/wl-relabel/blob/main/Cargo.toml)
and [source](https://github.com/valentin-morice/wl-relabel/blob/main/src/track.rs)
were reviewed as the native Wayland reference. Its current manifest declares
`wl-relabel` 0.1.1, requires Rust 1.89, and uses `wl-proxy` 0.1.4 with
all-protocol support. Its tracker applies title actions when a surface maps;
its late-title test explicitly verifies that an unrewritten later title is
passed through. Its [README](https://github.com/valentin-morice/wl-relabel/blob/main/README.md)
also requires wrapping each launcher. These facts make it a strong starting
point for a future proxy implementation, but not a dependency for the current
X11-only product: it does not yet provide the required per-update suffix
transform or the required normal-launch workflow.

The [official xdg-shell protocol definition](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/raw/main/stable/xdg-shell/xdg-shell.xml)
defines `xdg_toplevel.set_title` as the metadata used to identify a surface in
a task bar or window list. A native implementation must intercept that client
request before forwarding it to the compositor. The [wl-proxy documentation](https://docs.rs/wl-proxy)
states that its protocol handlers are generated and that an unsupported
protocol requires adding its XML and regenerating the vendored proxy. This is
why a future implementation must inventory the protocols used by Dolphin and
test pass-through behavior, rather than treating an `all-protocols` feature as
an unlimited compatibility guarantee. No Wayland stack has been selected for
this repository until the full proxy and launch integration can be verified.

Because the runtime has no third-party dependencies, a virtual environment is
not required for the current checkout. If future development adds packages,
use a project-local or otherwise isolated environment and document the exact
versions and authoritative sources before installation.

## Research records

Temporary research belongs under the ignored `.agent/research/` directory.
Only reviewed and durable conclusions belong in tracked documentation; public
tracked documentation must not contain raw research notes, prompts,
conversation history, internal prose, or temporary reasoning.
