"""Persistent feature activation and user-local integration management."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Mapping

from .environment import EnvironmentError, validate_x11_session
from .paths import (
    APP_ID,
    APP_NAME,
    DESKTOP_FILE_NAME,
    ICON_NAME,
    log_path,
    pid_path,
    state_dir,
)
from .x11 import X11Connection, X11Unavailable

MANAGED_MARKER = "# dolphin-clean-title-managed"
DOLPHIN_WRAPPER_MARKER = "# dolphin-clean-title-dolphin-wrapper-managed"
SYSTEM_COMMAND_MARKER = "# dolphin-clean-title-system-command"
DESKTOP_MARKER = "X-Dolphin-Clean-Title-Managed=true"
DATA_MARKER = "managed-by-dolphin-clean-title"
STATE_MARKER = "# dolphin-clean-title-state-v1"
REPORT_URL = "https://github.com/d0d1/dolphin-clean-title/issues/new"

_TRANSITION_LOCK = Lock()


class FeatureError(RuntimeError):
    """Raised when the persistent feature state cannot be changed safely."""


@dataclass(frozen=True)
class PathSnapshot:
    kind: str
    content: bytes | str
    mode: int


@dataclass(frozen=True)
class FeatureStatus:
    enabled: bool


def _xdg_path(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable)
    if not value:
        return fallback
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise FeatureError(f"{variable} must be an absolute path")
    return path


def data_home() -> Path:
    return _xdg_path("XDG_DATA_HOME", Path.home() / ".local" / "share")


def data_root() -> Path:
    return data_home() / APP_NAME


def config_home() -> Path:
    return _xdg_path("XDG_CONFIG_HOME", Path.home() / ".config")


def bin_path() -> Path:
    return Path.home() / ".local" / "bin" / APP_NAME


def system_command_path() -> Path:
    return Path("/usr/bin") / APP_NAME


def _has_marker(path: Path, marker: str) -> bool:
    try:
        return marker in path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return False


def command_path() -> Path:
    """Return the installed command used for lifecycle service control."""

    user_command = bin_path()
    if _has_marker(user_command, MANAGED_MARKER):
        return user_command
    system_command = system_command_path()
    if _has_marker(system_command, SYSTEM_COMMAND_MARKER):
        return system_command
    return user_command


def dolphin_path() -> Path:
    return Path.home() / ".local" / "bin" / "dolphin"


def autostart_path() -> Path:
    return config_home() / "autostart" / DESKTOP_FILE_NAME


def application_desktop_path() -> Path:
    return data_home() / "applications" / DESKTOP_FILE_NAME


def feature_state_path() -> Path:
    return state_dir() / "feature-state"


def _path_entry(path_entry: str) -> str:
    return os.path.normpath(os.path.abspath(os.path.expanduser(path_entry or ".")))


def _validate_launch_path(env: Mapping[str, str] | None = None) -> None:
    values = os.environ if env is None else env
    entries = [_path_entry(entry) for entry in values.get("PATH", "").split(os.pathsep)]
    user_bin = _path_entry(str(dolphin_path().parent))
    system_bin = _path_entry("/usr/bin")
    try:
        user_index = entries.index(user_bin)
    except ValueError as exc:
        raise FeatureError(
            "the managed Dolphin wrapper directory is not in PATH"
        ) from exc
    try:
        system_index = entries.index(system_bin)
    except ValueError as exc:
        raise FeatureError("/usr/bin is not in PATH") from exc
    if user_index >= system_index:
        raise FeatureError(
            "the managed Dolphin wrapper directory must precede /usr/bin in PATH"
        )


def _user_manager_environment() -> dict[str, str]:
    if shutil.which("systemctl") is None:
        raise FeatureError("systemctl is required to inspect the user session")
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise FeatureError(f"cannot inspect the user session: {exc}") from exc
    if result.returncode != 0:
        raise FeatureError(
            "cannot inspect the user session: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    environment: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            environment[key] = value
    return environment


def validate_activation_environment() -> None:
    """Validate the environment required to enable title cleaning now."""

    _validate_launch_path()
    if shutil.which("systemd-run") is None:
        raise FeatureError("systemd-run is required for FileManager1 Dolphin windows")
    dolphin_executable = Path("/usr/bin/dolphin")
    if not dolphin_executable.is_file() or not os.access(dolphin_executable, os.X_OK):
        raise FeatureError("this installation requires executable /usr/bin/dolphin")

    manager_environment = _user_manager_environment()
    manager_home = manager_environment.get("HOME")
    if manager_home and _path_entry(manager_home) != _path_entry(str(Path.home())):
        raise FeatureError("the user-systemd manager belongs to a different session")
    _validate_launch_path(manager_environment)
    if not manager_environment.get("DISPLAY"):
        raise FeatureError("the user-systemd manager does not expose DISPLAY")

    try:
        info = validate_x11_session()
        with X11Connection(info.display):
            pass
    except (EnvironmentError, X11Unavailable) as exc:
        raise FeatureError(str(exc)) from exc


def _desktop_exec(path: Path) -> str:
    escaped = str(path).replace(chr(92), chr(92) * 2)
    escaped = escaped.replace(chr(34), chr(92) + chr(34))
    escaped = escaped.replace(chr(36), chr(92) + chr(36))
    escaped = escaped.replace(chr(96), chr(92) + chr(96))
    return f'"{escaped}"'


def _desktop_try_exec(path: Path) -> str:
    return str(path)


def service_wrapper_content(root: Path, python_executable: str) -> str:
    from shlex import quote

    return f"""#!/bin/sh
{MANAGED_MARKER}
set -eu
APP_ROOT={quote(str(root))}
PYTHON={quote(python_executable)}
export PYTHONPATH="$APP_ROOT${{PYTHONPATH:+:$PYTHONPATH}}"
exec "$PYTHON" -m dolphin_clean_title "$@"
"""


def dolphin_wrapper_content(
    *,
    system_command: Path | None = None,
    user_command: Path | None = None,
    dolphin_executable: Path | None = None,
    cgroup_file: Path | None = None,
) -> str:
    from shlex import quote

    system_command = system_command or system_command_path()
    user_command = user_command or bin_path()
    dolphin_executable = dolphin_executable or Path("/usr/bin/dolphin")
    cgroup_file = cgroup_file or Path("/proc/self/cgroup")

    return f'''#!/bin/sh
{DOLPHIN_WRAPPER_MARKER}
set -eu

SYSTEM_COMMAND={quote(str(system_command))}
USER_COMMAND={quote(str(user_command))}
DOLPHIN_EXECUTABLE={quote(str(dolphin_executable))}
CGROUP_FILE={quote(str(cgroup_file))}

# Package removal must not leave the user's Dolphin launcher forcing XCB.
if [ ! -x "$SYSTEM_COMMAND" ] && [ ! -x "$USER_COMMAND" ]; then
    exec "$DOLPHIN_EXECUTABLE" "$@"
fi

if [ ! -r "$CGROUP_FILE" ]; then
    echo "dolphin-clean-title: cannot inspect $CGROUP_FILE; refusing to launch Dolphin" >&2
    exit 2
fi

in_filemanager_service=false
while IFS= read -r cgroup_line; do
    case "$cgroup_line" in
        */plasma-dolphin.service|*/plasma-dolphin.service/*)
            in_filemanager_service=true
            break
            ;;
    esac
done < "$CGROUP_FILE"

if $in_filemanager_service; then
    unit="dolphin-clean-title-window-$(date +%s%N)-$$"
    if output=$(systemd-run --user --unit="$unit" --collect --no-block \\
        --setenv=QT_QPA_PLATFORM=xcb "$DOLPHIN_EXECUTABLE" "$@" 2>&1); then
        exit 0
    else
        status=$?
        echo "dolphin-clean-title: could not start transient unit $unit.service" >&2
        [ -z "$output" ] || echo "$output" >&2
        exit "$status"
    fi
fi

export QT_QPA_PLATFORM=xcb
exec "$DOLPHIN_EXECUTABLE" "$@"
'''


def autostart_content(wrapper: Path) -> str:
    return f"""[Desktop Entry]
Type=Application
Name=Dolphin Clean Title
Comment=Remove the trailing Dolphin suffix from X11 Dolphin window titles
Exec={_desktop_exec(wrapper)}
TryExec={_desktop_try_exec(wrapper)}
Terminal=false
X-GNOME-Autostart-enabled=true
{DESKTOP_MARKER}
"""


def application_desktop_content(wrapper: Path) -> str:
    return f"""[Desktop Entry]
Type=Application
Name=Dolphin Clean Title
Comment=Configure Dolphin title cleaning
Exec={_desktop_exec(wrapper)} ui
TryExec={_desktop_try_exec(wrapper)}
Icon={ICON_NAME}
Terminal=false
Categories=Utility;Settings;
StartupNotify=true
StartupWMClass={APP_ID}
X-GNOME-Application-ID={APP_ID}
{DESKTOP_MARKER}
"""


def is_managed(path: Path) -> bool:
    if path.is_symlink():
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return False
    if path == feature_state_path():
        markers = (STATE_MARKER,)
    elif path == application_desktop_path():
        markers = (DESKTOP_MARKER,)
    elif path == dolphin_path():
        markers = (DOLPHIN_WRAPPER_MARKER,)
    elif path == autostart_path():
        markers = (DESKTOP_MARKER,)
    elif path == bin_path():
        markers = (MANAGED_MARKER,)
    elif path == system_command_path():
        markers = (SYSTEM_COMMAND_MARKER,)
    else:
        markers = (MANAGED_MARKER, DOLPHIN_WRAPPER_MARKER, DESKTOP_MARKER)
    return any(marker in content for marker in markers)


def _snapshot(path: Path) -> PathSnapshot | None:
    if not os.path.lexists(path):
        return None
    if path.is_symlink():
        return PathSnapshot("symlink", os.readlink(path), 0)
    if not path.is_file():
        raise FeatureError(f"refusing to replace unexpected activation path: {path.name}")
    return PathSnapshot("file", path.read_bytes(), path.stat().st_mode & 0o777)


def _restore(path: Path, snapshot: PathSnapshot | None) -> None:
    if os.path.lexists(path):
        path.unlink()
    if snapshot is None:
        return
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if snapshot.kind == "symlink":
        os.symlink(snapshot.content, path)
    else:
        _atomic_write_bytes(path, snapshot.content, snapshot.mode)


def _atomic_write_bytes(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write(path: Path, content: str, mode: int) -> None:
    _atomic_write_bytes(path, content.encode("utf-8"), mode)


def _read_state() -> bool | None:
    path = feature_state_path()
    if not os.path.lexists(path):
        return None
    if not is_managed(path):
        raise FeatureError("the persistent feature state collides with another file")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise FeatureError("cannot read the persistent feature state") from exc
    if lines == [STATE_MARKER, "enabled"]:
        return True
    if lines == [STATE_MARKER, "disabled"]:
        return False
    raise FeatureError("the persistent feature state is invalid")


def _write_state(enabled: bool) -> None:
    _atomic_write(
        feature_state_path(),
        f"{STATE_MARKER}\n{'enabled' if enabled else 'disabled'}\n",
        0o600,
    )


def _activation_kind(path: Path) -> str:
    if not os.path.lexists(path):
        return "absent"
    return "managed" if is_managed(path) else "collision"


def _activation_state() -> bool:
    kinds = (_activation_kind(dolphin_path()), _activation_kind(autostart_path()))
    if "collision" in kinds:
        raise FeatureError("a non-managed Dolphin activation file blocks this change")
    if kinds == ("managed", "managed"):
        return True
    if kinds == ("absent", "absent"):
        return False
    raise FeatureError(
        "managed Dolphin activation is incomplete and does not match the "
        "persistent state"
    )


def _require_installed() -> None:
    if not is_managed(command_path()):
        raise FeatureError("Dolphin Clean Title is not installed")


def status() -> FeatureStatus:
    _require_installed()
    configured = _read_state()
    active = _activation_state()
    if configured is None:
        configured = active
    if active != configured:
        raise FeatureError("managed activation does not match the persistent state")
    return FeatureStatus(enabled=configured)


def is_enabled() -> bool:
    return status().enabled


def _run_service(action: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(command_path()), action],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise FeatureError(f"cannot control the cleaner service: {exc}") from exc


def _service_running() -> bool:
    try:
        raw_pid = pid_path().read_text(encoding="ascii").strip()
        pid = int(raw_pid)
        command_line = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (FileNotFoundError, OSError, ValueError):
        return False
    return pid > 0 and b"dolphin_clean_title" in command_line


def _wait_for_service(timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _service_running():
            return
        time.sleep(0.05)
    raise FeatureError("the cleaner service did not become ready")


def _stop_after_failed_enable() -> None:
    if not _service_running():
        return
    result = _run_service("--stop")
    if result.returncode != 0:
        raise FeatureError("the failed enable operation left the cleaner running")


def enable() -> FeatureStatus:
    """Enable title cleaning and persist that choice."""

    with _TRANSITION_LOCK:
        current = status()
        if current.enabled:
            if not _service_running():
                validate_activation_environment()
                started = _run_service("--background")
                if started.returncode != 0:
                    raise FeatureError(
                        "the cleaner service could not start: "
                        f"{started.stderr.strip() or started.stdout.strip()}"
                    )
                _wait_for_service()
            return status()

        validate_activation_environment()
        snapshots = {
            "dolphin": _snapshot(dolphin_path()),
            "autostart": _snapshot(autostart_path()),
            "state": _snapshot(feature_state_path()),
        }
        try:
            _atomic_write(dolphin_path(), dolphin_wrapper_content(), 0o755)
            _atomic_write(
                autostart_path(), autostart_content(command_path()), 0o644
            )
            _write_state(True)
            started = _run_service("--background")
            if started.returncode != 0:
                raise FeatureError(
                    "the cleaner service could not start: "
                    f"{started.stderr.strip() or started.stdout.strip()}"
                )
            _wait_for_service()
            return status()
        except (FeatureError, OSError) as exc:
            try:
                _stop_after_failed_enable()
                _restore(dolphin_path(), snapshots["dolphin"])
                _restore(autostart_path(), snapshots["autostart"])
                _restore(feature_state_path(), snapshots["state"])
            except (FeatureError, OSError) as rollback_error:
                raise FeatureError(
                    f"enable failed ({exc}); rollback also failed: {rollback_error}"
                ) from rollback_error
            raise FeatureError(f"enable failed; previous state restored: {exc}") from exc


def _restore_enabled_after_failed_disable() -> None:
    if _service_running():
        return
    started = _run_service("--background")
    if started.returncode == 0:
        _wait_for_service()


def disable() -> FeatureStatus:
    """Disable title cleaning while leaving the application installed."""

    with _TRANSITION_LOCK:
        current = status()
        if not current.enabled:
            if _service_running():
                stopped = _run_service("--stop")
                if stopped.returncode != 0:
                    raise FeatureError(
                        "the cleaner service could not stop: "
                        f"{stopped.stderr.strip() or stopped.stdout.strip()}"
                    )
            return current

        snapshots = {
            "dolphin": _snapshot(dolphin_path()),
            "autostart": _snapshot(autostart_path()),
            "state": _snapshot(feature_state_path()),
        }
        stopped = _run_service("--stop")
        if stopped.returncode != 0:
            raise FeatureError(
                "the cleaner service could not stop: "
                f"{stopped.stderr.strip() or stopped.stdout.strip()}"
            )
        try:
            dolphin_path().unlink()
            autostart_path().unlink()
            _write_state(False)
            return status()
        except (FeatureError, OSError) as exc:
            try:
                _restore(dolphin_path(), snapshots["dolphin"])
                _restore(autostart_path(), snapshots["autostart"])
                _restore(feature_state_path(), snapshots["state"])
                _restore_enabled_after_failed_disable()
            except (FeatureError, OSError) as rollback_error:
                raise FeatureError(
                    f"disable failed ({exc}); rollback also failed: {rollback_error}"
                ) from rollback_error
            raise FeatureError(f"disable failed; previous state restored: {exc}") from exc


def install_state_default() -> bool:
    """Return the state to preserve when staging or refreshing an install."""

    configured = _read_state()
    if configured is not None:
        return configured
    # Older releases had no state file but always installed both activation
    # paths. A new checkout with no activation paths is a fresh enabled install.
    if os.path.lexists(dolphin_path()) or os.path.lexists(autostart_path()):
        return _activation_state()
    return True


def write_install_state(enabled: bool) -> None:
    _write_state(enabled)
