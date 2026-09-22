"""XDG paths owned by the user-local installation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

APP_NAME = "dolphin-clean-title"
APP_ID = "com.github.d0d1.DolphinCleanTitle"
DESKTOP_FILE_NAME = f"{APP_ID}.desktop"
LEGACY_DESKTOP_FILE_NAME = f"{APP_NAME}.desktop"
ICON_NAME = APP_ID


def state_dir(env: Mapping[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    state_home = values.get("XDG_STATE_HOME")
    if state_home:
        return Path(state_home) / APP_NAME
    return Path.home() / ".local" / "state" / APP_NAME


def log_path(env: Mapping[str, str] | None = None) -> Path:
    return state_dir(env) / f"{APP_NAME}.log"


def lock_path(env: Mapping[str, str] | None = None) -> Path:
    return state_dir(env) / f"{APP_NAME}.lock"


def pid_path(env: Mapping[str, str] | None = None) -> Path:
    return state_dir(env) / f"{APP_NAME}.pid"


def package_install_id_path() -> Path:
    """Return the per-user association with the installed Debian package."""

    return state_dir() / "package-install-id"
