"""Application lifecycle, diagnostics, and the foreground service."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .environment import EnvironmentError, session_info, validate_x11_session
from . import feature
from .lifecycle import InstanceAlreadyRunning, InstanceLock, stop_running
from .paths import log_path
from .x11 import X11Connection, X11Unavailable, find_x11_library

LOGGER = logging.getLogger(__name__)
PACKAGED_RUNTIME_ENV = "DOLPHIN_CLEAN_TITLE_PACKAGED_RUNTIME"
PACKAGED_RUNTIME_SENTINEL = Path(
    "/usr/lib/dolphin-clean-title/dolphin_clean_title/__main__.py"
)


def packaged_runtime_available() -> bool:
    """Return whether a package-launched service still has its runtime."""

    if os.environ.get(PACKAGED_RUNTIME_ENV) != "1":
        return True
    return PACKAGED_RUNTIME_SENTINEL.is_file()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dolphin-clean-title",
        description="Remove a trailing Dolphin suffix from X11 Dolphin titles.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--background",
        action="store_true",
        help="start a detached foreground service and return",
    )
    action.add_argument(
        "--stop",
        action="store_true",
        help="stop the user-local service",
    )
    action.add_argument(
        "--check",
        action="store_true",
        help="validate the current X11 environment and exit",
    )
    action.add_argument(
        "--diagnose",
        action="store_true",
        help="print local environment and matching-window diagnostics",
    )
    action.add_argument(
        "--prepare-launch",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--expected-install-id",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="also write debug-level messages to stderr",
    )
    parser.add_argument(
        "--log-file",
        metavar="PATH",
        help="write service logs to PATH instead of the default XDG state path",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("enable", "disable", "status", "ui"),
        help="manage the persistent feature or open its settings window",
    )
    return parser


def configure_logging(verbose: bool, path: str | None, foreground: bool) -> Path:
    destination = Path(path).expanduser() if path else log_path()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(destination, encoding="utf-8")
    ]
    if foreground or verbose:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    return destination


def _error(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def _diagnostic_argument(value: str, index: int) -> str:
    """Keep process diagnostics useful without echoing personal paths."""

    if index == 0 and value == "/usr/bin/dolphin":
        return value
    home = str(Path.home())
    if value == home or value.startswith(f"{home}/"):
        return "~" + value[len(home) :]
    if value.startswith("/"):
        return "<absolute-path>"
    return value


def _dolphin_processes() -> list[tuple[int, str, str]]:
    """Return local Dolphin processes and the backend visible in their env."""

    result: list[tuple[int, str, str]] = []
    proc_root = Path("/proc")
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return result
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            raw_cmdline = (entry / "cmdline").read_bytes()
            command_parts = [part for part in raw_cmdline.split(b"\0") if part]
            if not command_parts:
                continue
            executable = command_parts[0].rsplit(b"/", 1)[-1].lower()
            if executable != b"dolphin":
                continue
            arguments = " ".join(
                _diagnostic_argument(
                    part.decode("utf-8", errors="replace"), index
                )
                for index, part in enumerate(command_parts)
            )
            environment = {}
            for raw_line in (entry / "environ").read_bytes().split(b"\0"):
                if b"=" in raw_line:
                    key, value = raw_line.split(b"=", 1)
                    environment[key.decode(errors="replace")] = value.decode(
                        errors="replace"
                    )
        except OSError:
            continue
        qt_platform = environment.get("QT_QPA_PLATFORM", "")
        if qt_platform == "xcb":
            backend = "X11/XWayland candidate (QT_QPA_PLATFORM=xcb)"
        elif qt_platform == "wayland":
            backend = "native Wayland (QT_QPA_PLATFORM=wayland)"
        elif environment.get("WAYLAND_DISPLAY"):
            backend = "session-selected Wayland candidate; not X11-visible"
        else:
            backend = "backend not exposed by process environment"
        result.append((int(entry.name), arguments, backend))
    return sorted(result)


def check_environment() -> int:
    try:
        info = validate_x11_session()
        with X11Connection(info.display):
            pass
    except (EnvironmentError, X11Unavailable) as exc:
        return _error(str(exc))
    print(f"X11/XWayland environment OK ({info.display}; {info.boundary})")
    return 0


def diagnose() -> int:
    info = session_info()
    print(f"dolphin-clean-title {__version__}")
    print(f"python: {sys.version.split()[0]}")
    print(f"platform: {sys.platform}")
    print(f"XDG_SESSION_TYPE: {info.session_type or '<unset>'}")
    print(f"DISPLAY: {info.display or '<unset>'}")
    print(f"WAYLAND_DISPLAY: {info.wayland_display or '<unset>'}")
    print(f"integration boundary: {info.boundary}")
    print(
        "cleaner visibility: X11/XWayland Dolphin windows; "
        "native-Wayland Dolphin windows are outside the cleaner"
    )
    print(f"libX11: {find_x11_library() or 'not found'}")
    print("Dolphin processes:")
    processes = _dolphin_processes()
    if not processes:
        print("  none visible in /proc")
    for pid, arguments, backend in processes:
        print(f"  pid={pid} backend={backend} command={arguments!r}")

    try:
        validated = validate_x11_session()
        with X11Connection(validated.display) as connection:
            matches = connection.matching_windows()
            print("X11 connection: OK")
            print(f"X11 server: {connection.server_description()}")
            print(f"matching Dolphin windows: {len(matches)}")
            for window in matches:
                title = window.title if window.title is not None else "<unset>"
                print(
                    f"  window=0x{window.window:x} "
                    f"class={window.instance!r}/{window.window_class!r} "
                    f"title={title!r}"
                )
    except (EnvironmentError, X11Unavailable) as exc:
        print(f"diagnosis: unsupported or unavailable ({exc})")
        return 2
    return 0


def start_background(
    verbose: bool,
    path: str | None,
    expected_install_id: str | None = None,
) -> int:
    try:
        authorized_install_id = feature.authorize_service_start(expected_install_id)
        if feature.prepare_service_start(authorized_install_id):
            return 0
    except feature.FeatureError as exc:
        return _error(str(exc))

    try:
        info = validate_x11_session()
        with X11Connection(info.display):
            pass
    except (EnvironmentError, X11Unavailable) as exc:
        return _error(str(exc))

    command = [
        sys.executable,
        "-m",
        "dolphin_clean_title",
        "--foreground",
    ]
    if verbose:
        command.append("--verbose")
    if path:
        command.extend(["--log-file", path])
    if authorized_install_id is not None:
        command.extend(["--expected-install-id", authorized_install_id])
    environment = os.environ.copy()
    if authorized_install_id is not None:
        environment[feature.EXPECTED_INSTALL_ID_ENV] = authorized_install_id
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=environment,
        )
    except OSError as exc:
        return _error(f"cannot start background service: {exc}")
    print("Dolphin Clean Title service started in the background")
    return 0


def run_foreground(
    verbose: bool,
    path: str | None,
    expected_install_id: str | None = None,
) -> int:
    try:
        destination = configure_logging(verbose, path, foreground=True)
    except OSError as exc:
        return _error(f"cannot configure logging: {exc}")
    try:
        expected_install_id = feature.authorize_service_start(expected_install_id)
    except feature.FeatureError as exc:
        LOGGER.error("%s", exc)
        return _error(str(exc))
    if expected_install_id is not None:
        os.environ[feature.EXPECTED_INSTALL_ID_ENV] = expected_install_id
    stop_requested = False
    runtime_missing_logged = False
    install_identity_missing_logged = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    def service_should_stop() -> bool:
        nonlocal install_identity_missing_logged, runtime_missing_logged
        if stop_requested:
            return True
        if not packaged_runtime_available():
            if not runtime_missing_logged:
                LOGGER.warning("packaged runtime disappeared; stopping service")
                runtime_missing_logged = True
            return True
        if not feature.packaged_install_id_matches(expected_install_id):
            if not install_identity_missing_logged:
                LOGGER.warning(
                    "packaged install identity disappeared or changed; stopping service"
                )
                install_identity_missing_logged = True
            return True
        return False

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    LOGGER.info("starting dolphin-clean-title %s", __version__)
    try:
        info = validate_x11_session()
        LOGGER.info(
            "session type=%s display=%s boundary=%s; monitoring X11/Xwayland "
            "windows only",
            info.session_type or "<unset>",
            info.display,
            info.boundary,
        )
        with InstanceLock():
            with X11Connection(info.display) as connection:
                LOGGER.info(
                    "connected to X11 server %s; monitoring _NET_WM_NAME and "
                    "WM_NAME for Dolphin windows",
                    connection.server_description(),
                )

                def on_cleaned(result) -> None:
                    LOGGER.info(
                        "rewrote window 0x%x title %r -> %r",
                        result.window,
                        result.original,
                        result.cleaned,
                    )

                connection.run(service_should_stop, on_cleaned)
    except InstanceAlreadyRunning:
        LOGGER.info("another service instance is already running")
        return 0
    except (EnvironmentError, X11Unavailable, OSError) as exc:
        LOGGER.error("%s", exc)
        return _error(f"{exc}; see {destination}")
    LOGGER.info("service stopped")
    return 0


def run_feature_command(command: str) -> int:
    try:
        if command == "enable":
            feature.enable()
            print("Dolphin Clean Title enabled")
        elif command == "disable":
            feature.disable()
            print("Dolphin Clean Title disabled")
        elif command == "status":
            print("enabled" if feature.is_enabled() else "disabled")
        elif command == "ui":
            from .ui import main as ui_main

            return ui_main()
        return 0
    except feature.FeatureError as exc:
        return _error(str(exc))
    except (ImportError, ValueError) as exc:
        return _error(f"settings UI is unavailable: {exc}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command:
        if (
            args.background
            or args.stop
            or args.check
            or args.diagnose
            or args.prepare_launch
            or args.expected_install_id
            or args.foreground
        ):
            return _error("lifecycle commands cannot be combined with legacy service flags")
        return run_feature_command(args.command)
    if args.prepare_launch:
        try:
            prepared = feature.prepare_launch()
        except feature.FeatureError as exc:
            return _error(str(exc))
        return 0 if prepared else 1
    if args.stop:
        try:
            stopped = stop_running()
        except RuntimeError as exc:
            return _error(str(exc))
        print("Dolphin Clean Title service stopped" if stopped else "service not running")
        return 0
    if args.check:
        return check_environment()
    if args.diagnose:
        return diagnose()
    if args.background:
        return start_background(
            args.verbose, args.log_file, args.expected_install_id
        )
    if args.foreground:
        return run_foreground(
            args.verbose, args.log_file, args.expected_install_id
        )
    if os.environ.get(PACKAGED_RUNTIME_ENV) == "1":
        return start_background(
            args.verbose, args.log_file, args.expected_install_id
        )
    return run_foreground(args.verbose, args.log_file)
