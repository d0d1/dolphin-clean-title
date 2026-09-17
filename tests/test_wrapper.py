import importlib.util
import os
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
        self.assertIn("/usr/bin/dolphin \"$@\"", content)
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
