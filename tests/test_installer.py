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

APPLICATION_DESKTOP = installer.feature.DESKTOP_FILE_NAME
LEGACY_DESKTOP = installer.feature.LEGACY_DESKTOP_FILE_NAME


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
        env["PATH"] = os.pathsep.join(
            [str(Path(home) / ".local" / "bin"), "/usr/bin", "/bin"]
        )
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        manager_stub = Path(home) / ".local" / "bin" / "systemctl"
        manager_stub.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        manager_stub.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--user\" ] && [ \"$2\" = \"show-environment\" ]; then\n"
            "    printf 'HOME=%s\\nPATH=%s\\nDISPLAY=%s\\n' \"$HOME\" \"$PATH\" \"$DISPLAY\"\n"
            "fi\n",
            encoding="utf-8",
        )
        manager_stub.chmod(0o755)
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
            dolphin_wrapper = Path(home) / ".local" / "bin" / "dolphin"
            desktop = Path(env["XDG_CONFIG_HOME"]) / "autostart" / APPLICATION_DESKTOP
            application = (
                Path(env["XDG_DATA_HOME"])
                / "applications"
                / APPLICATION_DESKTOP
            )
            icon = (
                Path(env["XDG_DATA_HOME"])
                / "icons"
                / "hicolor"
                / "scalable"
                / "apps"
                / f"{installer.feature.ICON_NAME}.svg"
            )
            self.assertIn(sys.executable, wrapper.read_text(encoding="utf-8"))
            wrapper_text = dolphin_wrapper.read_text(encoding="utf-8")
            self.assertIn("dolphin-clean-title-dolphin-wrapper-managed", wrapper_text)
            self.assertIn("systemd-run --user", wrapper_text)
            self.assertIn("DOLPHIN_EXECUTABLE=/usr/bin/dolphin", wrapper_text)
            self.assertIn('exec "$DOLPHIN_EXECUTABLE" "$@"', wrapper_text)
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
            self.assertTrue(application.exists())
            self.assertTrue(icon.exists())
            self.assertIn(
                installer.feature.ICON_MARKER,
                icon.read_text(encoding="utf-8"),
            )
            desktop_text = desktop.read_text(encoding="utf-8")
            self.assertIn("X-Dolphin-Clean-Title-Managed=true", desktop_text)
            self.assertIn(f'Exec="{wrapper}"', desktop_text)
            self.assertIn(f"TryExec={wrapper}\n", desktop_text)
            self.assertNotIn(f'TryExec="{wrapper}"', desktop_text)
            application_text = application.read_text(encoding="utf-8")
            self.assertIn("Name=Dolphin Clean Title", application_text)
            self.assertIn(f'Exec="{wrapper}" ui', application_text)
            self.assertIn(f"TryExec={wrapper}\n", application_text)

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
            self.assertFalse(dolphin_wrapper.exists())
            self.assertFalse(desktop.exists())
            self.assertFalse(application.exists())
            self.assertFalse(icon.exists())

    def test_install_migrates_managed_legacy_desktop_entries(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            installed = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            autostart = Path(env["XDG_CONFIG_HOME"]) / "autostart"
            applications = Path(env["XDG_DATA_HOME"]) / "applications"
            current_autostart = autostart / APPLICATION_DESKTOP
            current_application = applications / APPLICATION_DESKTOP
            legacy_autostart = autostart / LEGACY_DESKTOP
            legacy_application = applications / LEGACY_DESKTOP
            current_autostart.rename(legacy_autostart)
            current_application.rename(legacy_application)

            refreshed = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
            self.assertTrue(current_autostart.exists())
            self.assertTrue(current_application.exists())
            self.assertFalse(legacy_autostart.exists())
            self.assertFalse(legacy_application.exists())
            subprocess.run(
                ["sh", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

    def test_uninstall_removes_managed_legacy_desktop_entries(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            installed = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            autostart = Path(env["XDG_CONFIG_HOME"]) / "autostart"
            applications = Path(env["XDG_DATA_HOME"]) / "applications"
            (autostart / APPLICATION_DESKTOP).rename(autostart / LEGACY_DESKTOP)
            (applications / APPLICATION_DESKTOP).rename(applications / LEGACY_DESKTOP)

            uninstalled = subprocess.run(
                ["sh", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(uninstalled.returncode, 0, uninstalled.stderr)
            self.assertFalse((autostart / LEGACY_DESKTOP).exists())
            self.assertFalse((applications / LEGACY_DESKTOP).exists())

    def test_unmanaged_legacy_desktop_entries_are_preserved(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            autostart = Path(env["XDG_CONFIG_HOME"]) / "autostart"
            applications = Path(env["XDG_DATA_HOME"]) / "applications"
            legacy_autostart = autostart / LEGACY_DESKTOP
            legacy_application = applications / LEGACY_DESKTOP
            legacy_autostart.parent.mkdir(parents=True, exist_ok=True)
            legacy_application.parent.mkdir(parents=True, exist_ok=True)
            legacy_autostart.write_text("[Desktop Entry]\nName=Unmanaged\n", encoding="utf-8")
            legacy_application.write_text("[Desktop Entry]\nName=Unmanaged\n", encoding="utf-8")

            installed = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            subprocess.run(
                ["sh", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(legacy_autostart.read_text(encoding="utf-8"), "[Desktop Entry]\nName=Unmanaged\n")
            self.assertEqual(legacy_application.read_text(encoding="utf-8"), "[Desktop Entry]\nName=Unmanaged\n")

    def test_disabled_state_survives_reinstall(self):
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

            installed = Path(home) / ".local" / "bin" / "dolphin-clean-title"
            disabled = subprocess.run(
                [str(installed), "disable"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(disabled.returncode, 0, disabled.stderr)

            refreshed = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
            self.assertEqual(
                subprocess.run(
                    [str(installed), "status"],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                "disabled",
            )
            self.assertFalse(Path(home, ".local", "bin", "dolphin").exists())
            self.assertFalse(
                Path(env["XDG_CONFIG_HOME"], "autostart", APPLICATION_DESKTOP).exists()
            )
            self.assertTrue(
                Path(env["XDG_DATA_HOME"], "applications", APPLICATION_DESKTOP).exists()
            )
            subprocess.run(
                ["sh", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

    def test_default_install_starts_and_restarts_service(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            wrapper = Path(home) / ".local" / "bin" / "dolphin-clean-title"
            dolphin_wrapper = Path(home) / ".local" / "bin" / "dolphin"
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
            self.assertFalse(dolphin_wrapper.exists())
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
            dolphin_wrapper = Path(home) / ".local" / "bin" / "dolphin"
            desktop = (
                Path(env["XDG_CONFIG_HOME"])
                / "autostart"
                / APPLICATION_DESKTOP
            )
            before_target = os.readlink(current)
            before_wrapper = wrapper.read_bytes()
            before_dolphin_wrapper = dolphin_wrapper.read_bytes()
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
            self.assertEqual(dolphin_wrapper.read_bytes(), before_dolphin_wrapper)
            self.assertEqual(desktop.read_bytes(), before_desktop)
            self.assertEqual(len(list((root / "releases").iterdir())), 1)

    def test_release_history_is_bounded(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            for _ in range(installer.RELEASE_RETENTION + 1):
                result = subprocess.run(
                    ["sh", str(ROOT / "install.sh"), "--no-start"],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            root = Path(env["XDG_DATA_HOME"]) / "dolphin-clean-title"
            releases = [
                path
                for path in (root / "releases").iterdir()
                if path.name.startswith("release-")
            ]
            self.assertEqual(len(releases), installer.RELEASE_RETENTION)
            subprocess.run(
                ["sh", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

    def test_install_refuses_nonmanaged_binary(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            wrapper = Path(home) / ".local" / "bin" / "dolphin-clean-title"
            wrapper.parent.mkdir(parents=True, exist_ok=True)
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

    def test_install_refuses_nonmanaged_dolphin_wrapper(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            wrapper = Path(home) / ".local" / "bin" / "dolphin"
            wrapper.parent.mkdir(parents=True, exist_ok=True)
            wrapper.write_text("#!/bin/sh\n", encoding="utf-8")
            result = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite non-managed Dolphin wrapper", result.stderr)

    def test_install_refuses_nonmanaged_application_launcher(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            launcher = (
                Path(env["XDG_DATA_HOME"])
                / "applications"
                / APPLICATION_DESKTOP
            )
            launcher.parent.mkdir(parents=True, exist_ok=True)
            launcher.write_text("[Desktop Entry]\nName=Other App\n", encoding="utf-8")
            result = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite non-managed application launcher", result.stderr)

    def test_install_refuses_nonmanaged_application_icon(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            icon = (
                Path(env["XDG_DATA_HOME"])
                / "icons"
                / "hicolor"
                / "scalable"
                / "apps"
                / f"{installer.feature.ICON_NAME}.svg"
            )
            icon.parent.mkdir(parents=True, exist_ok=True)
            icon.write_text("not the managed icon\n", encoding="utf-8")
            result = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite non-managed application icon", result.stderr)

    def test_transient_units_are_stopped_and_collected(self):
        unit = "dolphin-clean-title-window-123-456.service"
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if command[2] == "list-units":
                output = "" if len(calls) > 1 else f"{unit} loaded active running Dolphin\n"
                return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with mock.patch.object(installer.shutil, "which", return_value="/usr/bin/systemctl"):
            with mock.patch.object(installer.subprocess, "run", side_effect=fake_run):
                installer._stop_transient_units()

        self.assertEqual(calls[0][2:], [
            "list-units",
            "--all",
            "--no-legend",
            "--no-pager",
            "--plain",
            "dolphin-clean-title-window-*.service",
        ])
        self.assertEqual(calls[1], ["systemctl", "--user", "stop", unit])

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
                / APPLICATION_DESKTOP
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

    def test_wayland_with_xwayland_installs(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            env["XDG_SESSION_TYPE"] = "wayland"
            env["WAYLAND_DISPLAY"] = "wayland-0"
            result = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--no-start"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (Path(home) / ".local" / "bin" / "dolphin").exists()
            )
            subprocess.run(
                ["sh", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

    def _wait_for_path(self, path: Path):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if path.exists():
                return
            time.sleep(0.05)
        self.fail(f"timed out waiting for {path}")
