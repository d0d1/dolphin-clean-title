# Architecture

This document defines durable boundaries for the project without selecting an
implementation stack. The project is a standalone Linux package whose purpose
is to remove a trailing `— Dolphin` or `- Dolphin` from Dolphin window titles
without modifying Dolphin or depending on a particular taskbar. The cleaned
title must remain visible to the window manager or compositor and should
survive normal Dolphin and taskbar updates.

## Structural principles

Require clean separation of concerns and a professional structure from the
beginning. Keep title handling, integration boundaries, packaging, and
diagnostics independently understandable when the implementation is added.

Avoid monoliths, circular dependencies, dumping-ground modules, inappropriate
coupling, and unjustified abstractions. Every abstraction should earn its
place by making a real boundary or behavior easier to verify and maintain.

The implementation must not modify Dolphin, patch Dolphin files, or require a
specific taskbar. Integration should target the appropriate window-system
boundary so the cleaned title is exposed to the window manager or compositor.
The design should tolerate ordinary updates to Dolphin and taskbars.

## Runtime constraints

The runtime must have no telemetry, analytics, network access, accounts,
payments, subscriptions, or external service dependencies. It must operate as
a local standalone package and avoid introducing an online control plane.

Implementation technologies and dependencies must be researched and documented
under the policy in [Tooling](tooling.md) before selection, then reflected in
the structure without weakening these boundaries.
