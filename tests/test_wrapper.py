import importlib.util
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "packaging" / "installer.py"
SPEC = importlib.util.spec_from_file_location("wrapper_installer", INSTALLER_PATH)
installer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


class WrapperConstructionTests(unittest.TestCase):
    def test_wrapper_is_valid_shell_and_has_both_launch_paths(self):
        content = installer._dolphin_wrapper_content()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dolphin"
            path.write_text(content, encoding="utf-8")
            result = subprocess.run(
                ["sh", "-n", str(path)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/proc/self/cgroup", content)
        self.assertIn("plasma-dolphin.service", content)
        self.assertIn("systemd-run --user", content)
        self.assertIn("--collect --no-block", content)
        self.assertIn("--setenv=QT_QPA_PLATFORM=xcb", content)
        self.assertIn('DOLPHIN_EXECUTABLE=/usr/bin/dolphin', content)
        self.assertIn('exec "$DOLPHIN_EXECUTABLE" "$@"', content)
        self.assertIn("export QT_QPA_PLATFORM=xcb", content)

    def test_wrapper_never_resolves_dolphin_through_path(self):
        content = installer._dolphin_wrapper_content()
        self.assertNotIn("systemd-run.* dolphin", content)
        self.assertNotIn("exec dolphin", content)
        self.assertNotIn("command dolphin", content)

    def test_wrapper_preserves_argument_boundaries_without_eval_or_splitting(self):
        content = installer._dolphin_wrapper_content()
        self.assertGreaterEqual(content.count('"$@"'), 2)
        self.assertNotIn("$*", content)
        self.assertNotIn("eval ", content)

    def test_transient_unit_name_is_collision_safe(self):
        content = installer._dolphin_wrapper_content()
        self.assertIn('$(date +%s%N)-$$', content)
        self.assertIn('unit="dolphin-clean-title-window-', content)

    def test_context_detection_uses_the_exact_service_cgroup_component(self):
        content = installer._dolphin_wrapper_content()
        self.assertIn("*/plasma-dolphin.service|*/plasma-dolphin.service/*", content)
        self.assertNotIn('case "$@"', content)

    def test_package_removal_while_enabled_falls_back_and_reinstall_reactivates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = root / "dolphin-wrapper"
            system_command = root / "usr" / "bin" / "dolphin-clean-title"
            user_command = root / "home" / ".local" / "bin" / "dolphin-clean-title"
            dolphin = root / "usr" / "bin" / "dolphin"
            cgroup_file = root / "proc" / "self" / "cgroup"
            ensure_log = root / "ensure.log"
            system_command.parent.mkdir(parents=True)

            def write_system_command() -> None:
                system_command.write_text(
                    "#!/bin/sh\n"
                    f"printf '%s\\n' \"$1\" >> {shlex.quote(str(ensure_log))}\n",
                    encoding="utf-8",
                )
                system_command.chmod(0o755)

            write_system_command()
            dolphin.parent.mkdir(parents=True, exist_ok=True)
            cgroup_file.parent.mkdir(parents=True)
            cgroup_file.write_text(
                "0::/user.slice/user-1000.slice/user@1000.service/app.slice/test.scope\n",
                encoding="utf-8",
            )
            dolphin.write_text(
                "#!/bin/sh\n"
                "printf 'QT_QPA_PLATFORM=%s\\n' \"${QT_QPA_PLATFORM-<unset>}\"\n"
                "printf 'ARG=%s\\n' \"$1\"\n",
                encoding="utf-8",
            )
            dolphin.chmod(0o755)
            wrapper.write_text(
                installer._dolphin_wrapper_content(
                    system_command=system_command,
                    user_command=user_command,
                    dolphin_executable=dolphin,
                    cgroup_file=cgroup_file,
                ),
                encoding="utf-8",
            )
            wrapper.chmod(0o755)

            environment = os.environ.copy()
            environment.pop("QT_QPA_PLATFORM", None)

            installed = subprocess.run(
                [str(wrapper), "/tmp"],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("QT_QPA_PLATFORM=xcb", installed.stdout)
            self.assertIn("ARG=/tmp", installed.stdout)
            self.assertEqual(
                ensure_log.read_text(encoding="utf-8"), "--prepare-launch\n"
            )

            system_command.unlink()
            removed = subprocess.run(
                [str(wrapper), "/usr"],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("QT_QPA_PLATFORM=<unset>", removed.stdout)
            self.assertIn("ARG=/usr", removed.stdout)
            self.assertEqual(
                ensure_log.read_text(encoding="utf-8"), "--prepare-launch\n"
            )

            write_system_command()
            reinstalled = subprocess.run(
                [str(wrapper), "/var/tmp"],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("QT_QPA_PLATFORM=xcb", reinstalled.stdout)
            self.assertIn("ARG=/var/tmp", reinstalled.stdout)
            self.assertEqual(
                ensure_log.read_text(encoding="utf-8"),
                "--prepare-launch\n--prepare-launch\n",
            )

    def test_wrapper_launches_dolphin_when_recovery_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = root / "dolphin-wrapper"
            system_command = root / "usr" / "bin" / "dolphin-clean-title"
            dolphin = root / "usr" / "bin" / "dolphin"
            cgroup_file = root / "proc" / "self" / "cgroup"
            system_command.parent.mkdir(parents=True)
            system_command.write_text(
                "#!/bin/sh\necho startup failed >&2\nexit 7\n", encoding="utf-8"
            )
            system_command.chmod(0o755)
            dolphin.parent.mkdir(parents=True, exist_ok=True)
            dolphin.write_text(
                "#!/bin/sh\n"
                "printf 'QT_QPA_PLATFORM=%s\\n' \"${QT_QPA_PLATFORM-<unset>}\"\n"
                "printf 'ARG=%s\\n' \"$1\"\n",
                encoding="utf-8",
            )
            dolphin.chmod(0o755)
            cgroup_file.parent.mkdir(parents=True)
            cgroup_file.write_text("0::/user.slice/test.scope\n", encoding="utf-8")
            wrapper.write_text(
                installer._dolphin_wrapper_content(
                    system_command=system_command,
                    dolphin_executable=dolphin,
                    cgroup_file=cgroup_file,
                ),
                encoding="utf-8",
            )
            wrapper.chmod(0o755)

            result = subprocess.run(
                [str(wrapper), "/tmp"],
                env=os.environ.copy(),
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("QT_QPA_PLATFORM=<unset>", result.stdout)
            self.assertIn("ARG=/tmp", result.stdout)
            self.assertIn("could not prepare the cleaner", result.stderr)
            self.assertIn("startup failed", result.stderr)

    def test_packaged_inactive_prepare_falls_back_without_forcing_xcb(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = root / "dolphin-wrapper"
            system_command = root / "usr" / "bin" / "dolphin-clean-title"
            dolphin = root / "usr" / "bin" / "dolphin"
            system_command.parent.mkdir(parents=True)
            system_command.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$1\" > "
                + shlex.quote(str(root / "prepare.log"))
                + "\n"
                "exit 1\n",
                encoding="utf-8",
            )
            system_command.chmod(0o755)
            dolphin.write_text(
                "#!/bin/sh\n"
                "printf 'QT_QPA_PLATFORM=%s\\n' \"${QT_QPA_PLATFORM-<unset>}\"\n",
                encoding="utf-8",
            )
            dolphin.chmod(0o755)
            wrapper.write_text(
                installer._dolphin_wrapper_content(
                    system_command=system_command,
                    dolphin_executable=dolphin,
                ),
                encoding="utf-8",
            )
            wrapper.chmod(0o755)

            result = subprocess.run(
                [str(wrapper), "/tmp"], capture_output=True, text=True
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("QT_QPA_PLATFORM=<unset>", result.stdout)
            self.assertEqual(
                (root / "prepare.log").read_text(encoding="utf-8"),
                "--prepare-launch\n",
            )

    def test_path_validation_requires_user_bin_before_usr_bin(self):
        with tempfile.TemporaryDirectory() as home:
            original_home = os.environ.get("HOME")
            os.environ["HOME"] = home
            try:
                good = {
                    "PATH": f"{home}/.local/bin:/usr/bin:/bin",
                }
                installer._validate_launch_path(good)
                with self.assertRaisesRegex(installer.InstallationError, "precede"):
                    installer._validate_launch_path(
                        {"PATH": f"/usr/bin:{home}/.local/bin"}
                    )
                with self.assertRaisesRegex(installer.InstallationError, "not in PATH"):
                    installer._validate_launch_path({"PATH": "/usr/bin:/bin"})
            finally:
                if original_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = original_home


if __name__ == "__main__":
    unittest.main()
