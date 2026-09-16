import ctypes
import ctypes.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from dolphin_clean_title.x11 import X11Connection

ROOT = Path(__file__).resolve().parents[1]


class X11TestWindow:
    def __init__(self, display_name: str, instance: str, window_class: str):
        library = ctypes.util.find_library("X11") or "libX11.so.6"
        self.lib = ctypes.CDLL(library)
        c_display = ctypes.c_void_p
        c_window = ctypes.c_ulong
        c_atom = ctypes.c_ulong
        self.lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.lib.XOpenDisplay.restype = c_display
        self.lib.XCloseDisplay.argtypes = [c_display]
        self.lib.XCloseDisplay.restype = ctypes.c_int
        self.lib.XDefaultScreen.argtypes = [c_display]
        self.lib.XDefaultScreen.restype = ctypes.c_int
        self.lib.XRootWindow.argtypes = [c_display, ctypes.c_int]
        self.lib.XRootWindow.restype = c_window
        self.lib.XInternAtom.argtypes = [c_display, ctypes.c_char_p, ctypes.c_int]
        self.lib.XInternAtom.restype = c_atom
        self.lib.XCreateSimpleWindow.argtypes = [
            c_display,
            c_window,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            c_window,
            c_window,
        ]
        self.lib.XCreateSimpleWindow.restype = c_window
        self.lib.XChangeProperty.argtypes = [
            c_display,
            c_window,
            c_atom,
            c_atom,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
        ]
        self.lib.XChangeProperty.restype = ctypes.c_int
        self.lib.XMapWindow.argtypes = [c_display, c_window]
        self.lib.XMapWindow.restype = ctypes.c_int
        self.lib.XDestroyWindow.argtypes = [c_display, c_window]
        self.lib.XDestroyWindow.restype = ctypes.c_int
        self.lib.XFlush.argtypes = [c_display]
        self.lib.XFlush.restype = ctypes.c_int

        self.display = self.lib.XOpenDisplay(display_name.encode())
        if not self.display:
            raise unittest.SkipTest("cannot open the X11 display")
        screen = self.lib.XDefaultScreen(self.display)
        root = self.lib.XRootWindow(self.display, screen)
        self.window = self.lib.XCreateSimpleWindow(
            self.display, root, 10, 10, 200, 80, 0, 0, 0
        )
        string_atom = self.lib.XInternAtom(self.display, b"STRING", 0)
        wm_class = self.lib.XInternAtom(self.display, b"WM_CLASS", 0)
        class_data = f"{instance}\0{window_class}\0".encode()
        self._change(wm_class, string_atom, class_data)
        self.net_wm_name = self.lib.XInternAtom(self.display, b"_NET_WM_NAME", 0)
        self.utf8_string = self.lib.XInternAtom(self.display, b"UTF8_STRING", 0)
        self.wm_name = self.lib.XInternAtom(self.display, b"WM_NAME", 0)
        self.string_atom = self.lib.XInternAtom(self.display, b"STRING", 0)

    def _change(self, property_atom, type_atom, data: bytes):
        buffer_type = ctypes.c_ubyte * max(len(data), 1)
        buffer = buffer_type()
        if data:
            buffer[: len(data)] = data
        self.lib.XChangeProperty(
            self.display,
            self.window,
            property_atom,
            type_atom,
            8,
            0,
            buffer,
            len(data),
        )

    def set_title(self, title: str) -> None:
        self._change(self.net_wm_name, self.utf8_string, title.encode())
        self.lib.XFlush(self.display)

    def set_wm_title(self, title: str) -> None:
        self._change(self.wm_name, self.string_atom, title.encode())
        self.lib.XFlush(self.display)

    def show(self) -> None:
        self.lib.XMapWindow(self.display, self.window)
        self.lib.XFlush(self.display)

    def close(self) -> None:
        if self.display:
            self.lib.XDestroyWindow(self.display, self.window)
            self.lib.XFlush(self.display)
            self.lib.XCloseDisplay(self.display)
            self.display = None


@unittest.skipUnless(os.environ.get("DISPLAY"), "an X11 display is required")
class X11IntegrationTests(unittest.TestCase):
    def test_rewrites_dolphin_titles_and_leaves_other_windows_alone(self):
        with tempfile.TemporaryDirectory() as state:
            env = os.environ.copy()
            # A Wayland desktop may provide an Xwayland DISPLAY. Force the
            # service's X11 path here so this remains an X11 protocol test;
            # native-session detection is covered separately.
            env["XDG_SESSION_TYPE"] = "x11"
            env.pop("WAYLAND_DISPLAY", None)
            env["XDG_STATE_HOME"] = state
            env["PYTHONPATH"] = str(ROOT / "src")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            log_path = Path(state) / "service.log"
            daemon = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "dolphin_clean_title",
                    "--foreground",
                    "--verbose",
                    "--log-file",
                    str(log_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            dolphin = X11TestWindow(env["DISPLAY"], "dolphin", "Dolphin")
            other = X11TestWindow(env["DISPLAY"], "not-dolphin", "Other")
            observer = X11Connection(env["DISPLAY"])
            try:
                self.assertRegex(
                    observer.server_description(),
                    r"^(Xwayland|X11 server): .+ \(protocol [0-9]+\.[0-9]+\)$",
                )
                dolphin.set_title("Home — Dolphin")
                other.set_title("Other - Dolphin")
                dolphin.show()
                other.show()
                self._wait_for_title(observer, dolphin.window, "Home", daemon)
                self._wait_for_title(observer, other.window, "Other - Dolphin", daemon)

                dolphin.set_wm_title("Videos — Dolphin")
                self._wait_for_title(observer, dolphin.window, "Videos", daemon)
                dolphin.set_wm_title("Music")
                self._wait_for_title(observer, dolphin.window, "Music", daemon)
                dolphin.set_title("Pictures - Dolphin")
                self._wait_for_title(observer, dolphin.window, "Pictures", daemon)
                dolphin.set_title("Home — Dolphin — Dolphin")
                self._wait_for_title(observer, dolphin.window, "Home — Dolphin", daemon)
                dolphin.set_title("Home — dolphin")
                self._wait_for_title(observer, dolphin.window, "Home — dolphin", daemon)
            finally:
                observer.close()
                dolphin.close()
                other.close()
                daemon.terminate()
                try:
                    daemon.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    daemon.kill()
                    daemon.wait(timeout=5)
                if daemon.stdout:
                    daemon.stdout.close()
                if daemon.stderr:
                    daemon.stderr.close()
            self.assertIsNotNone(log_path)
            log = log_path.read_text(encoding="utf-8")
            self.assertIn("rewrote window", log)
            self.assertIn("connected to X11", log)

    def test_graceful_stop_restores_owned_title(self):
        with tempfile.TemporaryDirectory() as state:
            env = os.environ.copy()
            env["XDG_SESSION_TYPE"] = "x11"
            env.pop("WAYLAND_DISPLAY", None)
            env["XDG_STATE_HOME"] = state
            env["PYTHONPATH"] = str(ROOT / "src")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            daemon = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "dolphin_clean_title",
                    "--foreground",
                    "--log-file",
                    str(Path(state) / "service.log"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            dolphin = X11TestWindow(env["DISPLAY"], "dolphin", "Dolphin")
            observer = X11Connection(env["DISPLAY"])
            try:
                dolphin.set_title("Home — Dolphin")
                dolphin.show()
                self._wait_for_title(observer, dolphin.window, "Home", daemon)
                daemon.terminate()
                daemon.wait(timeout=5)
                self._wait_for_title(
                    observer, dolphin.window, "Home — Dolphin", None
                )
            finally:
                observer.close()
                dolphin.close()
                if daemon.poll() is None:
                    daemon.terminate()
                    daemon.wait(timeout=5)
                if daemon.stdout:
                    daemon.stdout.close()
                if daemon.stderr:
                    daemon.stderr.close()

    def test_installed_service_rewrites_and_uninstalls_cleanly(self):
        with tempfile.TemporaryDirectory() as state:
            env = os.environ.copy()
            env["HOME"] = str(Path(state) / "home")
            env["XDG_CONFIG_HOME"] = str(Path(state) / "config")
            env["XDG_DATA_HOME"] = str(Path(state) / "data")
            env["XDG_STATE_HOME"] = str(Path(state) / "state")
            env["XDG_SESSION_TYPE"] = "x11"
            env.pop("WAYLAND_DISPLAY", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            Path(env["HOME"]).mkdir()
            installed = subprocess.run(
                [str(ROOT / "install.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            wrapper = Path(env["HOME"]) / ".local" / "bin" / "dolphin-clean-title"
            daemon = None
            dolphin = X11TestWindow(env["DISPLAY"], "dolphin", "Dolphin")
            observer = X11Connection(env["DISPLAY"])
            try:
                dolphin.set_title("Home — Dolphin")
                dolphin.show()
                self._wait_for_title(observer, dolphin.window, "Home", daemon)
                uninstalled = subprocess.run(
                    [str(ROOT / "uninstall.sh")],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(uninstalled.returncode, 0, uninstalled.stderr)
                self._wait_for_title(
                    observer, dolphin.window, "Home — Dolphin", daemon
                )
                self.assertFalse(wrapper.exists())
            finally:
                observer.close()
                dolphin.close()
                if wrapper.exists():
                    subprocess.run(
                        [str(ROOT / "uninstall.sh")],
                        cwd=ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                    )

    def _wait_for_title(self, observer, window, expected, daemon):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if daemon is not None and daemon.poll() is not None:
                stderr = daemon.stderr.read() if daemon.stderr else ""
                self.fail(f"daemon exited early: {stderr}")
            info = observer.window_info(window)
            if info and info.title == expected:
                return
            time.sleep(0.05)
        info = observer.window_info(window)
        self.fail(f"timed out waiting for {expected!r}; got {info!r}")
