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

Because the runtime has no third-party dependencies, a virtual environment is
not required for the current checkout. If future development adds packages,
use a project-local or otherwise isolated environment and document the exact
versions and authoritative sources before installation.

## Research records

Temporary research belongs under the ignored `.agent/research/` directory.
Only reviewed and durable conclusions belong in tracked documentation; public
tracked documentation must not contain raw research notes, prompts,
conversation history, internal prose, or temporary reasoning.
