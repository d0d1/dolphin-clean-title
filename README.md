# dolphin-clean-title

[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Status: documentation-only](https://img.shields.io/badge/status-documentation--only-lightgrey.svg)](#what-it-is-intended-to-do)
[![Runtime policy: local-only](https://img.shields.io/badge/runtime%20policy-local--only-2ea44f.svg)](#privacy-and-external-services)

A standalone Linux package intended to remove a trailing `— Dolphin` or `- Dolphin` from Dolphin window titles without modifying Dolphin or depending on a specific taskbar.

## What it is intended to do

The project is intended to clean those suffixes at the window-system boundary
so the cleaned title is exposed to the window manager or compositor. It is
designed to remain independent of Dolphin internals and taskbar
implementations, and to tolerate normal Dolphin and taskbar updates.

The repository currently contains project documentation and policy. Runtime
behavior and distribution details will be documented only when they exist and
have been verified.

## Privacy and external services

- No telemetry
- No analytics
- No network access
- No account requirement
- No payments or subscriptions
- No external service dependencies at runtime

## Docs

- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Tooling](docs/tooling.md)
- [Testing](docs/testing.md)
- [Debugging](docs/debugging.md)
- [Contributing](CONTRIBUTING.md)
- [Agent instructions](AGENTS.md)
