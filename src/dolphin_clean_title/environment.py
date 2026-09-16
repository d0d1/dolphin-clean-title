"""Supported-session detection and user-facing environment errors."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class EnvironmentError(RuntimeError):
    """Raised when the current session cannot support the X11 integration."""


@dataclass(frozen=True)
class SessionInfo:
    session_type: str
    display: str
    wayland_display: str


def session_info(env: Mapping[str, str] | None = None) -> SessionInfo:
    values = os.environ if env is None else env
    return SessionInfo(
        session_type=values.get("XDG_SESSION_TYPE", "").strip().lower(),
        display=values.get("DISPLAY", "").strip(),
        wayland_display=values.get("WAYLAND_DISPLAY", "").strip(),
    )


def validate_x11_session(env: Mapping[str, str] | None = None) -> SessionInfo:
    """Validate that the process is running in a supported X11 session."""

    info = session_info(env)
    if info.session_type and info.session_type != "x11":
        raise EnvironmentError(
            "unsupported session type "
            f"{info.session_type!r}; this release supports X11 sessions only"
        )
    if not info.session_type and info.wayland_display:
        raise EnvironmentError(
            "a Wayland display was detected but XDG_SESSION_TYPE is unset; "
            "this release supports X11 sessions only"
        )
    if not info.display:
        raise EnvironmentError(
            "DISPLAY is not set; start this program from an X11 desktop session"
        )
    return info
