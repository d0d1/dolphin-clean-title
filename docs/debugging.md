# Debugging

Design debugging so agents can diagnose failures with minimal user input.
Diagnostics should be actionable: identify the failing boundary, explain the
next useful check, and avoid requiring a user to infer hidden state.

Once implementation exists, require actionable logging, environment and
version diagnostics, reproducible checks, and useful failure artifacts. Keep
diagnostics local and privacy-conscious; do not add telemetry, analytics, or
network reporting to improve diagnosis.

Generated diagnostics belong under the ignored `.artifacts/` directory. Keep
durable troubleshooting guidance in tracked documentation, and keep temporary
logs, dumps, screenshots, and other generated outputs out of commits. The
eventual commands and artifact formats should be documented after the
implementation stack and runtime integration are selected.
