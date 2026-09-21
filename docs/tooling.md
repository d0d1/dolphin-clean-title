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
- The cleaner service and lifecycle layer use only the Python standard
  library, including [`ctypes`](https://docs.python.org/3/library/ctypes.html)
  for the distro's X11 client library. They have no Python package
  dependencies or dependency lockfiles to install. The settings app uses the
  separately documented system GTK4/libadwaita/PyGObject runtime.
- The X11 adapter follows the [Xlib reference](https://www.x.org/releases/current/doc/libX11/libX11/libX11.html)
  for display, property, event, and window operations. It uses the EWMH
  `_NET_WM_NAME` property described by the [Extended Window Manager Hints
  specification](https://specifications.freedesktop.org/wm-spec/latest/ar01s05.html).
- User-session persistence uses an XDG autostart desktop entry following the
  [Desktop Application Autostart Specification](https://specifications.freedesktop.org/autostart/latest/).
- FileManager1 GUI-child lifetime management uses the distro-provided
  `systemd-run --user` command and user systemd manager. The implementation
  uses the locally verified options `--user`, `--unit`, `--collect`,
  `--no-block`, and `--setenv=QT_QPA_PLATFORM=xcb`; it does not pin a systemd
  package version because these are stable command-line features of the
  supported user-systemd interface. Installation inspects the manager with
  `systemctl --user show-environment` and fails clearly when the manager lacks
  the required `PATH` ordering or `DISPLAY`, or when `systemd-run` is
  unavailable.
- The test suite uses Python's standard `unittest` module and a live X11
  integration test. No test framework was added before the implementation
  stack was known.
- The settings app uses the system-provided GTK 4, libadwaita, and PyGObject
  bindings. The verified target machine currently exposes GTK 4.14.5,
  libadwaita 1.5.0, and PyGObject 3.48.2 through its distribution packages;
  these versions are compatibility evidence, not bundled dependency pins.
  They were established locally with a PyGObject probe that reads
  `Gtk.get_major_version()`, `Gtk.get_minor_version()`,
  `Gtk.get_micro_version()`, and the corresponding `Adw` values, plus
  `python3 -c 'import gi; print(gi.__version__)'`, on the verified target
  session; future version changes must repeat that check and consult the linked
  authoritative API documentation.
  The implementation uses the documented GTK 4 and libadwaita APIs and fails
  during installation with an actionable message when those imports are not
  available. The selected APIs are documented by the [GTK 4
  documentation](https://docs.gtk.org/gtk4/), the [libadwaita
  documentation](https://gnome.pages.gitlab.gnome.org/libadwaita/), and the
  [PyGObject documentation](https://pygobject.gnome.org/).
- The Ubuntu 24.04 package declares the distribution runtime packages
  `dolphin`, `python3`, `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`,
  `libgtk-4-1`, `libadwaita-1-0`, `libx11-6`, and `systemd`. Their names and
  candidate versions were checked with `apt-cache policy` on the verified
  Ubuntu 24.04 target: Dolphin `4:23.08.5-0ubuntu4`, Python `3.12.3-0ubuntu2.1`,
  GTK `4.14.5+ds-0ubuntu0.10`, libadwaita `1.5.0-1ubuntu2`, PyGObject
  `3.48.2-1`, libX11 `2:1.8.7-1build1`, and systemd `255.4-1ubuntu8.17`.
  These are compatibility evidence, not hard pins; the authoritative package
  metadata is the [Ubuntu package index](https://packages.ubuntu.com/noble/).
  The package does not vendor or install Python packages from the network.
- The settings application uses the stable reverse-DNS identity
  `com.github.d0d1.DolphinCleanTitle` for its `Adw.Application`, desktop entry,
  icon basename, and AppStream component. This follows the [GNOME application
  ID guidance](https://developer.gnome.org/documentation/tutorials/application-id.html)
  and the [freedesktop Desktop Entry specification](https://specifications.freedesktop.org/desktop-entry/latest-single/);
  the GitHub namespace is appropriate because no owned project domain is
  established.
- Debian packaging uses `dpkg-buildpackage`, `dpkg-deb`, and debhelper
  compatibility level 13. The [Debian Maintainer Guide](https://www.debian.org/doc/manuals/maint-guide/dreq.en.html),
  [Debian Policy control fields](https://www.debian.org/doc/debian-policy/ch-controlfields.html),
  and [debhelper documentation](https://manpages.debian.org/unstable/debhelper/debhelper.7.en.html)
  are the authoritative references for the package metadata and build flow.
  `debhelper-compat (= 13)` is the current stable compatibility baseline for
  the Ubuntu 24.04 source package; it is a build dependency, not a runtime
  dependency. The package is intentionally pure Python/shell and therefore
  uses `Architecture: all` while declaring its architecture-specific runtime
  dependencies explicitly.

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
also requires wrapping each launcher. These facts make it a useful reference
for native Wayland research, but it is not a dependency for this product: the
implemented Wayland-desktop workflow uses XWayland GUI launches and does not
proxy native Wayland title requests.

The [official xdg-shell protocol definition](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/raw/main/stable/xdg-shell/xdg-shell.xml)
defines `xdg_toplevel.set_title` as the metadata used to identify a surface in
a task bar or window list. A native implementation must intercept that client
request before forwarding it to the compositor. The [wl-proxy documentation](https://docs.rs/wl-proxy)
states that its protocol handlers are generated and that an unsupported
protocol requires adding its XML and regenerating the vendored proxy. This
remains relevant only if native Wayland proxying is reconsidered; it is not
part of the current implementation or support claim.

Because the cleaner has no Python package dependencies, a virtual environment
is not required for the current checkout. The settings app intentionally uses
the distribution's GI bindings so that it follows the desktop's GTK and
libadwaita theme/runtime. If future development adds Python packages, use a
project-local or otherwise isolated environment and document the exact
versions and authoritative sources before installation. The installed shell
wrapper uses only POSIX shell utilities and absolute `/usr/bin/dolphin` and
does not add a runtime package dependency.

## Research records

Temporary research belongs under the ignored `.agent/research/` directory.
Record durable tooling conclusions in this document.
