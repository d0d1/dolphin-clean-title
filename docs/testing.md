# Testing

Testing must support autonomous agent execution and diagnosis. Prefer
deterministic, noninteractive automated verification with explicit inputs,
stable expected results, and failure output that identifies the relevant
boundary.

Select testing tools only after the implementation stack is known. The choice
must be based on the researched stack and its supported tooling, not on
speculative setup added in advance. Keep test commands reproducible in a clean
checkout and avoid requiring a particular taskbar, account, network service,
or interactive desktop session unless an environment-specific integration
check is explicitly justified.

Once implementation exists, verification should cover the title suffix rules,
titles that must remain unchanged, window-manager or compositor visibility,
update-resilient integration boundaries, packaging behavior, and runtime
constraints. The exact test layout and tools remain intentionally undecided.
