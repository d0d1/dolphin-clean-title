"""Application lifecycle, diagnostics, and the foreground service."""

from __future__ import annotations

import argparse
import logging
import signal
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .environment import EnvironmentError, session_info, validate_x11_session
from .lifecycle import InstanceAlreadyRunning, InstanceLock, stop_running
from .paths import log_path
from .x11 import X11Connection, X11Unavailable, find_x11_library

LOGGER = logging.getLogger(__name__)


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


def check_environment() -> int:
    try:
        info = validate_x11_session()
        with X11Connection(info.display):
            pass
    except (EnvironmentError, X11Unavailable) as exc:
        return _error(str(exc))
    print(f"X11 environment OK ({info.display})")
    return 0


def diagnose() -> int:
    info = session_info()
    print(f"dolphin-clean-title {__version__}")
    print(f"python: {sys.version.split()[0]}")
    print(f"platform: {sys.platform}")
    print(f"XDG_SESSION_TYPE: {info.session_type or '<unset>'}")
    print(f"DISPLAY: {info.display or '<unset>'}")
    print(f"WAYLAND_DISPLAY: {info.wayland_display or '<unset>'}")
    print("supported session: X11 only")
    print(f"libX11: {find_x11_library() or 'not found'}")

    try:
        validated = validate_x11_session()
        with X11Connection(validated.display) as connection:
            matches = connection.matching_windows()
            print("X11 connection: OK")
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


def start_background(verbose: bool, path: str | None) -> int:
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
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return _error(f"cannot start background service: {exc}")
    print("Dolphin Clean Title service started in the background")
    return 0


def run_foreground(verbose: bool, path: str | None) -> int:
    try:
        destination = configure_logging(verbose, path, foreground=True)
    except OSError as exc:
        return _error(f"cannot configure logging: {exc}")
    stop_requested = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    LOGGER.info("starting dolphin-clean-title %s", __version__)
    try:
        info = validate_x11_session()
        LOGGER.info(
            "session type=%s display=%s; supported integration is X11",
            info.session_type or "<unset>",
            info.display,
        )
        with InstanceLock():
            with X11Connection(info.display) as connection:
                LOGGER.info(
                    "connected to X11; monitoring _NET_WM_NAME and WM_NAME "
                    "for Dolphin windows"
                )

                def on_cleaned(result) -> None:
                    LOGGER.info(
                        "rewrote window 0x%x title %r -> %r",
                        result.window,
                        result.original,
                        result.cleaned,
                    )

                connection.run(lambda: stop_requested, on_cleaned)
    except InstanceAlreadyRunning:
        LOGGER.info("another service instance is already running")
        return 0
    except (EnvironmentError, X11Unavailable, OSError) as exc:
        LOGGER.error("%s", exc)
        return _error(f"{exc}; see {destination}")
    LOGGER.info("service stopped")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
        return start_background(args.verbose, args.log_file)
    return run_foreground(args.verbose, args.log_file)
