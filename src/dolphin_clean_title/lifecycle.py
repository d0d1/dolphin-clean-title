"""Single-instance locking and clean process shutdown."""

from __future__ import annotations

import errno
import fcntl
import os
import signal
import time
from pathlib import Path
from typing import Mapping

from .paths import lock_path, pid_path, state_dir


class InstanceAlreadyRunning(RuntimeError):
    """Raised when another cleaner instance owns the lock."""


class InstanceLock:
    """Hold a user-local advisory lock and a pid file for the daemon lifetime."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = env
        self._lock_file = None
        self._pid = os.getpid()

    def __enter__(self) -> "InstanceLock":
        directory = state_dir(self._env)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._lock_file = lock_path(self._env).open("a+", encoding="ascii")
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock_file.close()
            self._lock_file = None
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise InstanceAlreadyRunning from exc
            raise

        pid_file = pid_path(self._env)
        temporary = pid_file.with_name(f".{pid_file.name}.{self._pid}.tmp")
        try:
            temporary.write_text(f"{self._pid}\n", encoding="ascii")
            os.chmod(temporary, 0o600)
            os.replace(temporary, pid_file)
        except BaseException:
            temporary.unlink(missing_ok=True)
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pid_file = pid_path(self._env)
        try:
            if pid_file.read_text(encoding="ascii").strip() == str(self._pid):
                pid_file.unlink()
        except FileNotFoundError:
            pass
        finally:
            if self._lock_file is not None:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
                self._lock_file = None


def _pid_belongs_to_service(pid: int) -> bool:
    try:
        command_line = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    return b"dolphin_clean_title" in command_line


def stop_running(env: Mapping[str, str] | None = None, timeout: float = 5.0) -> bool:
    """Ask the running daemon to stop and wait for its pid file to disappear."""

    pid_file = pid_path(env)
    try:
        raw_pid = pid_file.read_text(encoding="ascii").strip()
        pid = int(raw_pid)
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"cannot read daemon pid file {pid_file}: {exc}") from exc

    if pid <= 0:
        raise RuntimeError(f"daemon pid file {pid_file} contains an invalid pid")
    if not _pid_belongs_to_service(pid):
        try:
            if pid_file.read_text(encoding="ascii").strip() == str(pid):
                pid_file.unlink()
        except FileNotFoundError:
            pass
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        try:
            pid_file.unlink()
        except FileNotFoundError:
            pass
        return False
    except PermissionError as exc:
        raise RuntimeError(f"cannot stop daemon pid {pid}: {exc}") from exc

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_file.exists():
            return True
        time.sleep(0.05)
    raise RuntimeError(
        f"daemon pid {pid} did not stop within {timeout:g} seconds; "
        f"inspect {pid_file}"
    )
