import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "packaging" / "installer.py"
SPEC = importlib.util.spec_from_file_location("project_installer", INSTALLER_PATH)
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


@unittest.skipUnless(os.environ.get("DISPLAY"), "an X11 display is required")
class InstallerTests(unittest.TestCase):
    def _environment(self, home: str) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = home
        env["XDG_CONFIG_HOME"] = str(Path(home) / "config")
        env["XDG_DATA_HOME"] = str(Path(home) / "data")
        env["XDG_STATE_HOME"] = str(Path(home) / "state")
        env["XDG_SESSION_TYPE"] = "x11"
        env.pop("WAYLAND_DISPLAY", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def test_reinstall_and_uninstall_are_reversible(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            install = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            install_again = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(install_again.returncode, 0, install_again.stderr)

            root = Path(env["XDG_DATA_HOME"]) / "dolphin-clean-title"
            releases = list((root / "releases").iterdir())
            self.assertEqual(len(releases), 2)
            self.assertTrue((root / "current").is_symlink())
            wrapper = Path(home) / ".local" / "bin" / "dolphin-clean-title"
            desktop = Path(env["XDG_CONFIG_HOME"]) / "autostart" / "dolphin-clean-title.desktop"
            self.assertIn(sys.executable, wrapper.read_text(encoding="utf-8"))
            self.assertEqual(
                subprocess.run(
                    [str(wrapper), "--version"],
                    env=env,
                    capture_output=True,
                    text=True,
                ).returncode,
                0,
            )
            self.assertTrue(desktop.exists())
            self.assertIn("X-Dolphin-Clean-Title-Managed=true", desktop.read_text())

            uninstall = subprocess.run(
                ["sh", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertFalse(root.exists())
            self.assertFalse(wrapper.exists())
            self.assertFalse(desktop.exists())

    def test_default_install_starts_and_restarts_service(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            wrapper = Path(home) / ".local" / "bin" / "dolphin-clean-title"
            state = Path(env["XDG_STATE_HOME"])
            pid_file = state / "dolphin-clean-title" / "dolphin-clean-title.pid"
            try:
                first = subprocess.run(
                    ["sh", str(ROOT / "install.sh")],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(first.returncode, 0, first.stderr)
                self._wait_for_path(pid_file)
                first_pid = pid_file.read_text(encoding="ascii").strip()

                second = subprocess.run(
                    ["sh", str(ROOT / "install.sh")],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(second.returncode, 0, second.stderr)
                self._wait_for_path(pid_file)
                second_pid = pid_file.read_text(encoding="ascii").strip()
                self.assertNotEqual(first_pid, second_pid)
            finally:
                subprocess.run(
                    ["sh", str(ROOT / "uninstall.sh")],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
            self.assertFalse(wrapper.exists())
            self.assertFalse(pid_file.exists())

    def test_no_start_stops_an_existing_service(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            state = Path(env["XDG_STATE_HOME"])
            pid_file = state / "dolphin-clean-title" / "dolphin-clean-title.pid"
            try:
                initial = subprocess.run(
                    ["sh", str(ROOT / "install.sh")],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(initial.returncode, 0, initial.stderr)
                self._wait_for_path(pid_file)

                deferred = subprocess.run(
                    ["sh", str(ROOT / "install.sh"), "--no-start"],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(deferred.returncode, 0, deferred.stderr)
                self.assertFalse(
                    pid_file.exists(), "--no-start must not leave an old service alive"
                )
            finally:
                subprocess.run(
                    ["sh", str(ROOT / "uninstall.sh")],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )

    def test_service_start_failure_restores_and_restarts_previous_service(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            initial = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            root = Path(env["XDG_DATA_HOME"]) / "dolphin-clean-title"
            current = root / "current"
            wrapper = Path(home) / ".local" / "bin" / "dolphin-clean-title"
            desktop = (
                Path(env["XDG_CONFIG_HOME"])
                / "autostart"
                / "dolphin-clean-title.desktop"
            )
            before_target = os.readlink(current)
            before_wrapper = wrapper.read_bytes()
            before_desktop = desktop.read_bytes()
            calls = []

            def fake_run_wrapper(path, action):
                calls.append(action)
                if action == "--stop":
                    if calls.count("--stop") == 1:
                        return subprocess.CompletedProcess(
                            [str(path), action],
                            0,
                            stdout="Dolphin Clean Title service stopped\n",
                            stderr="",
                        )
                    return subprocess.CompletedProcess(
                        [str(path), action],
                        0,
                        stdout="service not running\n",
                        stderr="",
                    )
                if action == "--background":
                    if calls.count("--background") == 1:
                        return subprocess.CompletedProcess(
                            [str(path), action],
                            1,
                            stdout="",
                            stderr="injected startup failure",
                        )
                    return subprocess.CompletedProcess(
                        [str(path), action], 0, stdout="", stderr=""
                    )
                raise AssertionError(f"unexpected action: {action}")

            with mock.patch.dict(os.environ, env):
                with mock.patch.object(
                    installer, "_run_wrapper", side_effect=fake_run_wrapper
                ):
                    with mock.patch.object(installer, "_wait_for_service"):
                        with self.assertRaisesRegex(
                            installer.InstallationError,
                            "previous installation was restored and the previous "
                            "service was restarted",
                        ):
                            installer.install(start_service=True)

            self.assertEqual(calls, ["--stop", "--background", "--stop", "--background"])
            self.assertEqual(os.readlink(current), before_target)
            self.assertEqual(wrapper.read_bytes(), before_wrapper)
            self.assertEqual(desktop.read_bytes(), before_desktop)
            self.assertEqual(len(list((root / "releases").iterdir())), 1)

            uninstall = subprocess.run(
                ["sh", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)

    def test_install_refuses_nonmanaged_binary(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            wrapper = Path(home) / ".local" / "bin" / "dolphin-clean-title"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("#!/bin/sh\n", encoding="utf-8")
            result = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite non-managed binary", result.stderr)

    def test_activation_failure_restores_previous_installation(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            initial = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            root = Path(env["XDG_DATA_HOME"]) / "dolphin-clean-title"
            current = root / "current"
            wrapper = Path(home) / ".local" / "bin" / "dolphin-clean-title"
            desktop = (
                Path(env["XDG_CONFIG_HOME"])
                / "autostart"
                / "dolphin-clean-title.desktop"
            )
            before_target = os.readlink(current)
            before_wrapper = wrapper.read_bytes()
            before_desktop = desktop.read_bytes()
            original_atomic_write = installer._atomic_write

            def fail_on_desktop(path, content, mode):
                if path == desktop:
                    raise OSError("injected activation failure")
                return original_atomic_write(path, content, mode)

            with mock.patch.dict(os.environ, env):
                with mock.patch.object(
                    installer, "_atomic_write", side_effect=fail_on_desktop
                ):
                    with self.assertRaisesRegex(
                        installer.InstallationError,
                        "previous installation was restored",
                    ):
                        installer.install(start_service=False)

            self.assertEqual(os.readlink(current), before_target)
            self.assertEqual(wrapper.read_bytes(), before_wrapper)
            self.assertEqual(desktop.read_bytes(), before_desktop)
            releases = list((root / "releases").iterdir())
            self.assertEqual(len(releases), 1)

    def test_wayland_install_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            env["XDG_SESSION_TYPE"] = "wayland"
            result = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("supports X11 sessions only", result.stderr)
            self.assertFalse((Path(env["XDG_DATA_HOME"]) / "dolphin-clean-title").exists())

    def _wait_for_path(self, path: Path):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if path.exists():
                return
            time.sleep(0.05)
        self.fail(f"timed out waiting for {path}")
