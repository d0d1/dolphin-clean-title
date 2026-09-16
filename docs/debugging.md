# Debugging

When something goes wrong, coding agents should normally be able to obtain
enough local evidence to investigate the cause without asking the user to
diagnose it manually.

Design debugging so agents can diagnose failures with minimal user input.
Diagnostics should be actionable: identify the failing boundary, explain the
next useful check, and avoid requiring a user to infer hidden state.

## Current diagnostics

The service provides actionable file logging, `--verbose` foreground output,
`--check` environment validation, and `--diagnose` inspection of the session,
Python version, libX11 availability, X11 connectivity, X-server kind/vendor
and protocol version, and matching windows.
The default log is under the XDG state directory; use `--log-file` to place a
diagnostic log under `.artifacts/` during development.

Future changes must preserve appropriate support for actionable logging,
environment and version inspection, reproducible checks, test diagnostics,
debug modes, and failure-artifact collection. Debugging must remain local and
privacy-conscious; do not add telemetry, analytics, or network reporting to
improve diagnosis.

Generated diagnostics belong under the ignored `.artifacts/` directory. Keep
durable troubleshooting guidance in tracked documentation, and keep temporary
logs, dumps, screenshots, and other generated outputs out of commits. Do not
create debugging tooling speculatively; add it only when an implemented
boundary needs it and document how an agent can invoke it noninteractively.

## First checks

From a checkout, run `make check`, then use
`PYTHONPATH=src python3 -m dolphin_clean_title --check` or the same module
command with `--foreground` if a foreground trace is needed. For an installed
copy, use `~/.local/bin/dolphin-clean-title --check` and
`~/.local/bin/dolphin-clean-title --diagnose`. Run the service in the
foreground with
`--verbose --log-file .artifacts/dolphin-clean-title.log` and inspect that log
for the session, X11 connection, window identity, property changes, and
rewrites.

If installation fails, preserve the complete command output and inspect the
reported Python, `XDG_SESSION_TYPE`, `DISPLAY`, and libX11 values. A native
Wayland session is an expected unsupported environment for the current
implementation, not a service crash. An Xwayland display can exercise the X11
protocol path, but it is not evidence of native Xorg or native Wayland support.
Do not infer compatibility from a skipped X11 integration test.
