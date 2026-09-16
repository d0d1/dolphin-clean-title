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
packaging behavior, lifecycle safety, and runtime constraints:

- Pure title-rule tests verify exact matching, one-suffix removal, and
  unchanged near misses.
- Environment and lifecycle tests verify supported-session detection,
  single-instance locking, stale PID handling, and clean shutdown.
- Packaging tests exercise user-local installation, repeated installation,
  managed-file safety, automatic service restart, and uninstall cleanup in
  temporary XDG directories.
- The live X11 integration test creates controlled X11 windows, changes their
  titles, and verifies that matching Dolphin windows are rewritten while other
  windows are not. It also verifies subsequent title changes and EWMH-visible
  results. It is skipped when no X11 display is available; a skipped live test
  is an environment limitation, not evidence of Wayland support.

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
an X11-compatible server, but does not verify native Xorg behavior, a real
Dolphin build, or native Wayland behavior. Native Wayland has no implementation
or integration test in the current product.
