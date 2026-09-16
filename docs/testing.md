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

Once implementation exists, verification should cover the title suffix rules,
titles that must remain unchanged, window-manager or compositor visibility,
update-resilient integration boundaries, packaging behavior, and runtime
constraints. Define the exact test layout and tools as part of the researched
stack decision and document them with the implementation.
