# Testing

Testing must support autonomous agent execution and diagnosis. Prefer
deterministic, noninteractive automated verification with explicit inputs,
stable expected results, and failure output sufficient to identify the
relevant boundary and diagnose the cause.

Prefer automated verification over routine user testing. Ask the user to test
only when local automated verification cannot exercise a necessary
environment-specific behavior.

Select testing tools only after the implementation stack is known. The choice
must be based on the researched stack and its supported tooling, not on
speculative setup added in advance. Keep test commands reproducible in a clean
checkout and avoid requiring a particular taskbar, account, network service,
or interactive desktop session unless an environment-specific integration
check is explicitly justified.

## Verification levels

The current suite uses Python's standard `unittest` module and is run with
`make check`. It covers the title suffix rules, window-system visibility,
packaging behavior, lifecycle safety, wrapper construction, and runtime
constraints:

- Pure title-rule tests verify exact matching, one-suffix removal, and
  unchanged near misses.
- Environment and lifecycle tests verify supported-session detection,
  single-instance locking, stale PID handling, and clean shutdown.
- Packaging tests exercise user-local installation, repeated installation,
  bounded release retention, managed-file safety for both project launchers,
  current-session and user-manager PATH validation, automatic service restart,
  rollback after activation failure, Wayland-with-XWayland installation, and
  uninstall cleanup in temporary XDG directories.
- Feature-lifecycle tests exercise persistent enable/disable state, idempotent
  transitions, partial-state detection, rollback after failed transitions,
  disabled-state preservation across updates, packaged install-id matching and
  stale-state handling, and the installed application desktop entry. They
  verify that explicit launch preparation starts a missing packaged service,
  while disabled or stale state never starts it. They also verify that the
  authorized install identity is passed through background startup, that a
  previous service generation is stopped before replacement, that every
  packaged start path is authorized, and that a running service stops when its
  install identity changes even if the runtime sentinel remains present.
- The settings-app boundary is tested through the shared lifecycle API and
  desktop-entry content. On the real desktop, launch the installed app through
  its XDG launcher, verify the native switch and action-row focus behavior,
  and exercise enable/disable from the UI while observing `status` and the
  cleaner PID. UI tests must not replace deterministic lifecycle tests.
- Wrapper construction tests verify exact `/usr/bin/dolphin` execution,
  cgroup-context detection, transient `systemd-run` options, collision-safe
  unit naming, shell syntax, and argument-preserving quoting.
- The live X11 integration test creates controlled X11 windows, changes their
  titles, and verifies that matching Dolphin windows are rewritten while other
  windows are not. It also verifies subsequent title changes and EWMH-visible
  results, exact restoration after a suffix-free `WM_NAME` update, and that
  logs identify the XID and outcomes without logging title contents. It is
  skipped when no X11 display is available; a skipped live test is an
  environment limitation, not evidence of native Wayland support.
- Diagnostic-preference tests verify verbose tracing remains selected across
  repeated background starts and direct autostart starts, while remaining
  separate from feature activation state.

The real-machine release verification additionally exercises the installed
wrapper through terminal, desktop-entry, directory-opener, and FileManager1
launches. It verifies XWayland identity, transient-unit separation and
collection, dynamic title cleanup, repeated installation, `--no-start`,
uninstall restoration, and the shell command-cache case. These checks require
the actual graphical session and are not silently substituted by unit tests.

The Debian packaging verification builds the binary package with
`dpkg-buildpackage`, inspects control metadata and the complete file layout,
checks dependency resolution with `apt-get --simulate`, and installs/removes
the package in an isolated reversible dpkg root when host privileges are not
available. It verifies the packaged command path, desktop entry, fresh
disabled state, install-id creation/preservation/removal, and that maintainer
scripts touch only the package-owned system identity rather than user homes.
On a privileged release machine, repeat the same checks with a real local
`.deb` installation and package upgrade.

Every automated failure must retain the command, environment boundary, and
captured service output needed for diagnosis. Routine user testing is not a
substitute for these checks. When a desktop-specific behavior cannot be
exercised locally, document the exact limitation and do not claim it as
verified.

## Evidence boundary

The live X11 test uses the available `DISPLAY` and creates controlled test
windows with Xlib. In the verified environment that display is provided by
Xwayland; the test subprocess sets `XDG_SESSION_TYPE=x11` because it is testing
the X11 protocol path, not claiming that the surrounding desktop is a native
X11 session. The suite therefore demonstrates the title/property mechanism on
an X11-compatible server, while the real-machine checks demonstrate the
managed XCB launch path on GNOME Wayland. Native Xorg behavior and native
Wayland title rewriting remain outside the verified claim.
