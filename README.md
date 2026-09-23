# dolphin-clean-title

[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-2ea44f.svg)](#compatibility)
[![Runtime: local-only](https://img.shields.io/badge/runtime-local--only-2ea44f.svg)](#privacy-and-external-services)

A standalone Linux package that removes one trailing `— Dolphin` or `- Dolphin`
from Dolphin window titles without modifying Dolphin or depending on a specific
taskbar.

<img src="docs/images/dolphin-clean-title-ui.png"
    alt="Dolphin Clean Title settings"
    width="450">

## Install

Download the latest `.deb` from [GitHub Releases](https://github.com/d0d1/dolphin-clean-title/releases) and install it:

```bash
sudo apt install ./dolphin-clean-title_0.1.0-1_all.deb
```

## Use

Open **Dolphin Clean Title** from the application launcher and enable the switch.

To disable the feature, turn the switch off or run:

```
dolphin-clean-title disable
```

## Compatibility

Verified on Ubuntu 24.04 LTS with GNOME Wayland and Dolphin 23.08.5. The package requires Python 3.10 or newer, an accessible X11 DISPLAY (Xorg or XWayland), and a working user systemd manager. On Wayland, managed Dolphin GUI windows use XWayland; title cleaning does not apply to native Wayland Dolphin windows. Sessions without XWayland are unsupported.

## Uninstall

```bash
dolphin-clean-title disable
sudo apt remove dolphin-clean-title
```

## Privacy and external services

Dolphin Clean Title runs entirely locally. It has no telemetry or analytics, makes no network requests, requires no account, payments, or subscriptions, and has no external runtime service dependencies.

## Docs

- [Architecture](docs/architecture.md)
- [Development and packaging](docs/development.md)
- [Tooling](docs/tooling.md)
- [Testing](docs/testing.md)
- [Debugging](docs/debugging.md)
- [Contributing](CONTRIBUTING.md)
- [Agent instructions](AGENTS.md)
