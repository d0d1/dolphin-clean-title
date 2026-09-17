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

    @property
    def boundary(self) -> str:
        """Describe the supported window-system boundary for diagnostics."""

        if self.session_type == "wayland":
            return "Wayland desktop with XWayland" if self.display else "native Wayland"
        if self.session_type == "x11":
            return "native X11/Xorg-compatible session"
        if self.display:
            return "X11-compatible display with unknown session type"
        return "unknown window-system boundary"


def session_info(env: Mapping[str, str] | None = None) -> SessionInfo:
    values = os.environ if env is None else env
    return SessionInfo(
        session_type=values.get("XDG_SESSION_TYPE", "").strip().lower(),
        display=values.get("DISPLAY", "").strip(),
        wayland_display=values.get("WAYLAND_DISPLAY", "").strip(),
    )


def validate_x11_session(env: Mapping[str, str] | None = None) -> SessionInfo:
    """Validate that an X11-compatible display is available.

    A Wayland desktop is supported when it exposes an Xwayland ``DISPLAY``.
    The cleaner itself still operates only on X11/Xwayland windows; native
    Wayland Dolphin windows remain outside its reach.
    """

    info = session_info(env)
    if info.session_type not in ("", "x11", "wayland"):
        raise EnvironmentError(
            "unsupported session type "
            f"{info.session_type!r}; supported sessions are X11 or Wayland "
            "with an accessible Xwayland DISPLAY"
        )
    if not info.display and info.session_type == "wayland":
        raise EnvironmentError(
            "Wayland is supported only when Xwayland provides DISPLAY; "
            "DISPLAY is not set"
        )
    if not info.display:
        raise EnvironmentError(
            "DISPLAY is not set; an X11/Xwayland display is required"
        )
    return info
