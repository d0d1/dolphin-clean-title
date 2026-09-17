#!/usr/bin/env python3
"""User-local installation and removal for Dolphin Clean Title."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE = PROJECT_ROOT / "src" / "dolphin_clean_title"
APP_NAME = "dolphin-clean-title"
MANAGED_MARKER = "# dolphin-clean-title-managed"
DOLPHIN_WRAPPER_MARKER = "# dolphin-clean-title-dolphin-wrapper-managed"
DATA_MARKER = "managed-by-dolphin-clean-title"
RELEASE_RETENTION = 3

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dolphin_clean_title.environment import EnvironmentError, validate_x11_session
from dolphin_clean_title.paths import log_path, pid_path
from dolphin_clean_title.x11 import X11Connection, X11Unavailable


class InstallationError(RuntimeError):
    """Raised for an actionable installation or removal failure."""


@dataclass(frozen=True)
class PathSnapshot:
    kind: str
    content: bytes | str
    mode: int


def _xdg_path(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable)
    if not value:
        return fallback
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise InstallationError(f"{variable} must be an absolute path: {path}")
    return path


def data_root() -> Path:
    return _xdg_path("XDG_DATA_HOME", Path.home() / ".local" / "share") / APP_NAME


def config_home() -> Path:
    return _xdg_path("XDG_CONFIG_HOME", Path.home() / ".config")


def bin_path() -> Path:
    return Path.home() / ".local" / "bin" / APP_NAME


def dolphin_path() -> Path:
    return Path.home() / ".local" / "bin" / "dolphin"


def desktop_path() -> Path:
    return config_home() / "autostart" / f"{APP_NAME}.desktop"


def _path_entry(path_entry: str) -> str:
    return os.path.normpath(os.path.abspath(os.path.expanduser(path_entry or ".")))


def _validate_launch_path(env: dict[str, str] | None = None) -> None:
    values = os.environ if env is None else env
    path_value = values.get("PATH", "")
    entries = [_path_entry(entry) for entry in path_value.split(os.pathsep)]
    user_bin = _path_entry(str(dolphin_path().parent))
    system_bin = _path_entry("/usr/bin")
    try:
        user_index = entries.index(user_bin)
    except ValueError as exc:
        raise InstallationError(
            f"{dolphin_path().parent} is not in PATH; add it before installing "
            "so normal Dolphin launches can reach the managed wrapper"
        ) from exc
    try:
        system_index = entries.index(system_bin)
    except ValueError as exc:
        raise InstallationError(
            "/usr/bin is not in PATH; cannot verify Dolphin wrapper precedence"
        ) from exc
    if user_index >= system_index:
        raise InstallationError(
            f"{dolphin_path().parent} must precede /usr/bin in PATH; "
            "update the graphical session environment and retry"
        )


def _user_manager_environment() -> dict[str, str]:
    """Read the environment inherited by user-systemd services."""

    if shutil.which("systemctl") is None:
        raise InstallationError(
            "systemctl is required to inspect the user-systemd launch environment"
        )
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise InstallationError(
            f"cannot inspect the user-systemd launch environment: {exc}"
        ) from exc
    if result.returncode != 0:
        raise InstallationError(
            "cannot inspect the user-systemd launch environment: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    environment: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            environment[key] = value
    return environment


def _validate_user_manager_environment() -> None:
    environment = _user_manager_environment()
    manager_home = environment.get("HOME")
    if manager_home and _path_entry(manager_home) != _path_entry(str(Path.home())):
        raise InstallationError(
            "the user-systemd manager has a different HOME than this session; "
            "start installation from the same graphical user session"
        )
    _validate_launch_path(environment)
    if not environment.get("DISPLAY"):
        raise InstallationError(
            "the user-systemd manager does not expose DISPLAY; FileManager1 "
            "Dolphin windows cannot reach X11/XWayland"
        )


def _preflight() -> None:
    if sys.version_info < (3, 10):
        raise InstallationError(
            "Python 3.10 or newer is required; "
            f"found {sys.version.split()[0]}"
        )
    _validate_launch_path()
    if shutil.which("systemd-run") is None:
        raise InstallationError(
            "systemd-run is required for FileManager1 Dolphin windows; "
            "install the user-systemd runtime and retry"
        )
    dolphin_executable = Path("/usr/bin/dolphin")
    if not dolphin_executable.is_file() or not os.access(dolphin_executable, os.X_OK):
        raise InstallationError(
            "this release requires an executable /usr/bin/dolphin; "
            "the installed Dolphin path is outside the supported boundary"
        )
    _validate_user_manager_environment()
    try:
        info = validate_x11_session()
        with X11Connection(info.display):
            pass
    except (EnvironmentError, X11Unavailable) as exc:
        raise InstallationError(str(exc)) from exc


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


def _snapshot(path: Path) -> PathSnapshot | None:
    if not os.path.lexists(path):
        return None
    if path.is_symlink():
        return PathSnapshot("symlink", os.readlink(path), 0)
    if not path.is_file():
        raise InstallationError(
            f"refusing to replace unexpected non-file activation path: {path}"
        )
    return PathSnapshot(
        "file",
        path.read_bytes(),
        stat.S_IMODE(path.stat().st_mode),
    )


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


def _desktop_exec(path: Path) -> str:
    escaped = str(path).replace(chr(92), chr(92) * 2)
    escaped = escaped.replace(chr(34), chr(92) + chr(34))
    escaped = escaped.replace(chr(36), chr(92) + chr(36))
    escaped = escaped.replace(chr(96), chr(92) + chr(96))
    return f'"{escaped}"'


def _desktop_try_exec(path: Path) -> str:
    """Render the executable path required by the desktop TryExec key."""

    return str(path)


def _service_wrapper_content(root: Path, python_executable: str) -> str:
    from shlex import quote

    return f"""#!/bin/sh
{MANAGED_MARKER}
set -eu
APP_ROOT={quote(str(root))}
PYTHON={quote(python_executable)}
export PYTHONPATH="$APP_ROOT${{PYTHONPATH:+:$PYTHONPATH}}"
exec "$PYTHON" -m dolphin_clean_title "$@"
"""


def _dolphin_wrapper_content() -> str:
    return f'''#!/bin/sh
{DOLPHIN_WRAPPER_MARKER}
set -eu

if [ ! -r /proc/self/cgroup ]; then
    echo "dolphin-clean-title: cannot inspect /proc/self/cgroup; refusing to launch Dolphin" >&2
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
done < /proc/self/cgroup

if $in_filemanager_service; then
    unit="dolphin-clean-title-window-$(date +%s%N)-$$"
    if output=$(systemd-run --user --unit="$unit" --collect --no-block \\
        --setenv=QT_QPA_PLATFORM=xcb /usr/bin/dolphin "$@" 2>&1); then
        exit 0
    else
        status=$?
        echo "dolphin-clean-title: could not start transient unit $unit.service" >&2
        [ -z "$output" ] || echo "$output" >&2
        exit "$status"
    fi
fi

export QT_QPA_PLATFORM=xcb
exec /usr/bin/dolphin "$@"
'''


def _desktop_content(wrapper: Path) -> str:
    return f"""[Desktop Entry]
Type=Application
Name=Dolphin Clean Title
Comment=Remove the trailing Dolphin suffix from X11 Dolphin window titles
Exec={_desktop_exec(wrapper)}
TryExec={_desktop_try_exec(wrapper)}
Terminal=false
X-Dolphin-Clean-Title-Managed=true
"""


def _is_managed(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return False
    return (
        MANAGED_MARKER in content
        or DOLPHIN_WRAPPER_MARKER in content
        or "X-Dolphin-Clean-Title-Managed=true" in content
    )


def _run_wrapper(wrapper: Path, action: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(wrapper), action],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise InstallationError(f"cannot run {wrapper} {action}: {exc}") from exc


def _transient_unit_names() -> list[str]:
    """Return loaded transient GUI units owned by this project."""

    if shutil.which("systemctl") is None:
        return []
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "list-units",
                "--all",
                "--no-legend",
                "--no-pager",
                "--plain",
                "dolphin-clean-title-window-*.service",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise InstallationError(f"cannot inspect project transient units: {exc}") from exc
    if result.returncode != 0:
        raise InstallationError(
            "cannot inspect project transient units: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    names = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        unit = fields[0]
        if (
            unit.startswith("dolphin-clean-title-window-")
            and unit.endswith(".service")
        ):
            names.append(unit)
    return names


def _stop_transient_units(timeout: float = 5.0) -> None:
    """Stop project-owned GUI units and wait for --collect to unload them."""

    units = _transient_unit_names()
    if not units:
        return
    try:
        result = subprocess.run(
            ["systemctl", "--user", "stop", *units],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise InstallationError(f"cannot stop project transient units: {exc}") from exc
    if result.returncode != 0:
        raise InstallationError(
            "could not stop project transient units: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not set(_transient_unit_names()).intersection(units):
            return
        time.sleep(0.05)
    remaining = ", ".join(_transient_unit_names())
    raise InstallationError(
        "project transient units did not become collectible within "
        f"{timeout:g} seconds: {remaining or ', '.join(units)}"
    )


def _prune_releases(releases: Path, current: Path) -> None:
    """Keep a small rollback history without growing user data forever."""

    candidates = sorted(
        (
            path
            for path in releases.iterdir()
            if path.name.startswith("release-") and path.is_dir()
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    current_target = None
    if current.is_symlink():
        try:
            current_target = current.resolve(strict=False)
        except OSError:
            current_target = None
    keep = set(candidates[:RELEASE_RETENTION])
    if current_target is not None:
        keep.add(current_target)
    for path in candidates:
        if path not in keep:
            shutil.rmtree(path)


def _wait_for_service(timeout: float = 5.0) -> None:
    pid_file = pid_path()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pid_file.exists():
            return
        time.sleep(0.05)
    raise InstallationError(
        f"service did not become ready within {timeout:g} seconds; "
        f"inspect {log_path()}"
    )


def _assert_managed_or_absent(path: Path, label: str) -> None:
    if os.path.lexists(path) and not _is_managed(path):
        raise InstallationError(f"refusing to overwrite non-managed {label}: {path}")


def _rollback_activation(
    *,
    activation_paths: dict[str, Path],
    snapshots: dict[str, PathSnapshot | None],
    current_temporary: Path,
    final_release: Path,
    root: Path,
    releases: Path,
    root_was_present: bool,
) -> None:
    """Restore activation paths and remove the newly staged release."""
    current_temporary.unlink(missing_ok=True)
    try:
        for name, path in activation_paths.items():
            _restore(path, snapshots[name])
        shutil.rmtree(final_release, ignore_errors=True)
        if not root_was_present:
            try:
                releases.rmdir()
                root.rmdir()
            except OSError:
                pass
    except (OSError, InstallationError) as exc:
        raise InstallationError(
            f"activation failed ({exc}) and rollback also failed; inspect {root}"
        ) from exc


def _rollback_failed_service_start(
    *,
    cause: str,
    wrapper: Path,
    previous_service_running: bool,
    service_stop_succeeded: bool,
    activation_paths: dict[str, Path],
    snapshots: dict[str, PathSnapshot | None],
    current_temporary: Path,
    final_release: Path,
    root: Path,
    releases: Path,
    root_was_present: bool,
) -> None:
    """Roll back a failed service transition and report any recovery failure."""
    cleanup_problem = ""
    if service_stop_succeeded:
        try:
            cleanup = _run_wrapper(wrapper, "--stop")
            if cleanup.returncode != 0:
                cleanup_problem = (
                    "could not stop the failed new service: "
                    f"{cleanup.stderr.strip() or cleanup.stdout.strip()}"
                )
        except InstallationError as exc:
            cleanup_problem = f"could not stop the failed new service: {exc}"

    try:
        _rollback_activation(
            activation_paths=activation_paths,
            snapshots=snapshots,
            current_temporary=current_temporary,
            final_release=final_release,
            root=root,
            releases=releases,
            root_was_present=root_was_present,
        )
    except InstallationError as rollback_error:
        raise InstallationError(f"{cause}; {rollback_error}") from rollback_error

    restart_problem = ""
    if previous_service_running:
        restored_wrapper = activation_paths["wrapper"]
        try:
            restarted = _run_wrapper(restored_wrapper, "--background")
            if restarted.returncode != 0:
                restart_problem = (
                    "could not restart the previous service: "
                    f"{restarted.stderr.strip() or restarted.stdout.strip()}"
                )
            else:
                _wait_for_service()
        except (InstallationError, OSError) as exc:
            restart_problem = f"could not restart the previous service: {exc}"

    recovery = "previous installation was restored"
    if previous_service_running and not restart_problem:
        recovery += " and the previous service was restarted"
    problems = "; ".join(
        problem for problem in (cleanup_problem, restart_problem) if problem
    )
    if problems:
        recovery += f"; {problems}"
    raise InstallationError(f"{cause}; {recovery}")


def install(start_service: bool = True) -> int:
    _preflight()
    root = data_root()
    wrapper = bin_path()
    dolphin_wrapper = dolphin_path()
    desktop = desktop_path()
    releases = root / "releases"
    root_was_present = os.path.lexists(root)
    if os.path.lexists(root):
        marker = root / ".managed"
        try:
            managed_data = marker.read_text(encoding="utf-8").strip() == DATA_MARKER
        except (FileNotFoundError, OSError):
            managed_data = False
        if not managed_data:
            raise InstallationError(f"refusing to overwrite non-managed data directory: {root}")
    _assert_managed_or_absent(wrapper, "binary")
    _assert_managed_or_absent(dolphin_wrapper, "Dolphin wrapper")
    _assert_managed_or_absent(desktop, "autostart entry")
    activation_paths = {
        "wrapper": wrapper,
        "dolphin_wrapper": dolphin_wrapper,
        "desktop": desktop,
        "marker": root / ".managed",
        "current": root / "current",
    }
    snapshots = {name: _snapshot(path) for name, path in activation_paths.items()}
    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    releases.mkdir(mode=0o700, parents=True, exist_ok=True)

    stage = Path(tempfile.mkdtemp(prefix=f".{APP_NAME}-", dir=root.parent))
    release_name = f"release-{time.time_ns()}-{os.getpid()}"
    staged_release = stage / release_name
    final_release = releases / release_name
    try:
        shutil.copytree(
            SOURCE_PACKAGE,
            staged_release / "dolphin_clean_title",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.move(str(staged_release), str(final_release))
    except OSError as exc:
        raise InstallationError(f"cannot stage the installation: {exc}") from exc
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    current = root / "current"
    current_temporary = root / f".current-{os.getpid()}.tmp"
    try:
        current_temporary.unlink(missing_ok=True)
        os.symlink(final_release, current_temporary, target_is_directory=True)
        _atomic_write(
            wrapper,
            _service_wrapper_content(current, sys.executable),
            0o755,
        )
        _atomic_write(dolphin_wrapper, _dolphin_wrapper_content(), 0o755)
        _atomic_write(desktop, _desktop_content(wrapper), 0o644)
        _atomic_write(root / ".managed", f"{DATA_MARKER}\n", 0o600)
        os.replace(current_temporary, current)
    except (InstallationError, OSError) as exc:
        try:
            _rollback_activation(
                activation_paths=activation_paths,
                snapshots=snapshots,
                current_temporary=current_temporary,
                final_release=final_release,
                root=root,
                releases=releases,
                root_was_present=root_was_present,
            )
        except InstallationError as rollback_error:
            raise rollback_error from exc
        raise InstallationError(
            f"installation files were staged but could not be activated; "
            f"the previous installation was restored: {exc}"
        ) from exc

    service_stop_succeeded = False
    previous_service_running = False
    try:
        stopped = _run_wrapper(wrapper, "--stop")
        if stopped.returncode != 0:
            raise InstallationError(
                f"could not stop the previous service: "
                f"{stopped.stderr.strip() or stopped.stdout.strip()}"
            )
        service_stop_succeeded = True
        previous_service_running = "service stopped" in stopped.stdout.lower()
        if start_service:
            started = _run_wrapper(wrapper, "--background")
            if started.returncode != 0:
                raise InstallationError(
                    "the new service could not start: "
                    f"{started.stderr.strip() or started.stdout.strip()}"
                )
            _wait_for_service()
            print(f"installed and started {APP_NAME}")
        else:
            print(f"installed {APP_NAME}; service start deferred")
    except (InstallationError, OSError) as exc:
        _rollback_failed_service_start(
            cause=str(exc),
            wrapper=wrapper,
            previous_service_running=previous_service_running,
            service_stop_succeeded=service_stop_succeeded,
            activation_paths=activation_paths,
            snapshots=snapshots,
            current_temporary=current_temporary,
            final_release=final_release,
            root=root,
            releases=releases,
            root_was_present=root_was_present,
        )
    print(f"binary: {wrapper}")
    print(f"autostart: {desktop}")
    try:
        _prune_releases(releases, current)
    except OSError as exc:
        print(f"warning: could not prune old releases: {exc}", file=sys.stderr)
    return 0


def uninstall() -> int:
    root = data_root()
    wrapper = bin_path()
    dolphin_wrapper = dolphin_path()
    desktop = desktop_path()
    if os.path.lexists(wrapper) and _is_managed(wrapper):
        stopped = _run_wrapper(wrapper, "--stop")
        if stopped.returncode != 0:
            raise InstallationError(
                f"could not stop the service before uninstalling: "
                f"{stopped.stderr.strip() or stopped.stdout.strip()}"
            )
    elif os.path.lexists(wrapper):
        print(f"preserving non-managed file {wrapper}")

    marker = root / ".managed"
    managed_data = False
    try:
        managed_data = marker.read_text(encoding="utf-8").strip() == DATA_MARKER
    except FileNotFoundError:
        pass
    if managed_data:
        _stop_transient_units()

    if os.path.lexists(desktop) and _is_managed(desktop):
        desktop.unlink()
    elif os.path.lexists(desktop):
        print(f"preserving non-managed file {desktop}")

    if root.exists() and managed_data:
        shutil.rmtree(root)
    elif root.exists():
        print(f"preserving non-managed directory {root}")

    if os.path.lexists(wrapper) and _is_managed(wrapper):
        wrapper.unlink()
    if os.path.lexists(dolphin_wrapper) and _is_managed(dolphin_wrapper):
        dolphin_wrapper.unlink()
    print(f"uninstalled {APP_NAME}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument(
        "--no-start",
        action="store_true",
        help="install autostart files without starting the current session",
    )
    subparsers.add_parser("uninstall")
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            return install(not args.no_start)
        return uninstall()
    except (InstallationError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
