"""Persistent, feature-independent diagnostic preferences."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .paths import verbose_logging_path

_VERBOSE_MARKER = b"# dolphin-clean-title-verbose-logging-v1\nverbose\n"


class DiagnosticsError(RuntimeError):
    """Raised when diagnostic preferences cannot be managed safely."""


def _read_verbose(path: Path) -> bool:
    if not os.path.lexists(path):
        return False
    if path.is_symlink() or not path.is_file():
        raise DiagnosticsError(
            "the verbose logging preference collides with another file"
        )
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise DiagnosticsError("cannot read the verbose logging preference") from exc
    if content != _VERBOSE_MARKER:
        raise DiagnosticsError(
            "the verbose logging preference collides with another file"
        )
    return True


def verbose_logging_enabled(path: Path | None = None) -> bool:
    """Return whether verbose logs should be used for cleaner starts."""

    return _read_verbose(path or verbose_logging_path())


def set_verbose_logging(enabled: bool, path: Path | None = None) -> bool:
    """Persist the verbose logging preference without touching feature state."""

    preference = path or verbose_logging_path()
    current = _read_verbose(preference)
    if current == enabled:
        return current
    if not enabled:
        try:
            preference.unlink()
        except OSError as exc:
            raise DiagnosticsError(
                "cannot clear the verbose logging preference"
            ) from exc
        return False

    temporary_name: str | None = None
    try:
        preference.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{preference.name}.", dir=preference.parent
        )
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(_VERBOSE_MARKER)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_name, preference)
        except FileExistsError:
            # Do not replace a file created by another process or an
            # unmanaged collision that appeared after the initial check.
            return _read_verbose(preference)
        return True
    except OSError as exc:
        raise DiagnosticsError(
            f"cannot update the verbose logging preference: {exc}"
        ) from exc
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
