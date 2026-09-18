import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dolphin_clean_title import feature


class FeatureLifecycleTests(unittest.TestCase):
    def _environment(self, home: str) -> dict[str, str]:
        return {
            "HOME": home,
            "XDG_CONFIG_HOME": str(Path(home) / "config"),
            "XDG_DATA_HOME": str(Path(home) / "data"),
            "XDG_STATE_HOME": str(Path(home) / "state"),
            "PATH": os.pathsep.join(
                [str(Path(home) / ".local" / "bin"), "/usr/bin", "/bin"]
            ),
        }

    def _install_runtime(self, env: dict[str, str], enabled: bool) -> None:
        with mock.patch.dict(os.environ, env, clear=False):
            feature.bin_path().parent.mkdir(parents=True, exist_ok=True)
            feature.bin_path().write_text(
                "#!/bin/sh\n# dolphin-clean-title-managed\n", encoding="utf-8"
            )
            feature.bin_path().chmod(0o755)
            feature.application_desktop_path().parent.mkdir(
                parents=True, exist_ok=True
            )
            feature.application_desktop_path().write_text(
                "X-Dolphin-Clean-Title-Managed=true\n", encoding="utf-8"
            )
            feature.write_install_state(enabled)
            if enabled:
                feature.dolphin_path().write_text(
                    feature.dolphin_wrapper_content(), encoding="utf-8"
                )
                feature.autostart_path().parent.mkdir(parents=True, exist_ok=True)
                feature.autostart_path().write_text(
                    feature.autostart_content(feature.bin_path()), encoding="utf-8"
                )

    def test_enable_from_disabled_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            with mock.patch.dict(os.environ, env, clear=False):
                self._install_runtime(env, enabled=False)
                with mock.patch.object(feature, "validate_activation_environment"):
                    with mock.patch.object(
                        feature,
                        "_run_service",
                        return_value=subprocess.CompletedProcess([], 0, "", ""),
                    ) as run_service:
                        with mock.patch.object(feature, "_wait_for_service"):
                            with mock.patch.object(feature, "_service_running", return_value=False):
                                self.assertTrue(feature.enable().enabled)
                self.assertTrue(feature.is_enabled())
                self.assertTrue(feature.dolphin_path().exists())
                self.assertTrue(feature.autostart_path().exists())
                run_service.reset_mock()
                with mock.patch.object(feature, "_service_running", return_value=True):
                    self.assertTrue(feature.enable().enabled)
                run_service.assert_not_called()

    def test_disable_from_enabled_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            with mock.patch.dict(os.environ, env, clear=False):
                self._install_runtime(env, enabled=True)
                with mock.patch.object(
                    feature,
                    "_run_service",
                    return_value=subprocess.CompletedProcess([], 0, "", ""),
                ) as run_service:
                    self.assertFalse(feature.disable().enabled)
                    self.assertFalse(feature.dolphin_path().exists())
                    self.assertFalse(feature.autostart_path().exists())
                    self.assertTrue(feature.application_desktop_path().exists())
                    self.assertEqual(run_service.call_args.args, ("--stop",))
                    run_service.reset_mock()
                    with mock.patch.object(feature, "_service_running", return_value=False):
                        self.assertFalse(feature.disable().enabled)
                    run_service.assert_not_called()

    def test_status_rejects_partial_activation(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            with mock.patch.dict(os.environ, env, clear=False):
                self._install_runtime(env, enabled=True)
                feature.autostart_path().unlink()
                with self.assertRaisesRegex(feature.FeatureError, "does not match"):
                    feature.status()

    def test_enable_failure_restores_disabled_state(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            with mock.patch.dict(os.environ, env, clear=False):
                self._install_runtime(env, enabled=False)
                failed = subprocess.CompletedProcess([], 1, "", "startup failed")
                with mock.patch.object(feature, "validate_activation_environment"):
                    with mock.patch.object(feature, "_run_service", return_value=failed):
                        with mock.patch.object(feature, "_service_running", return_value=False):
                            with self.assertRaisesRegex(feature.FeatureError, "restored"):
                                feature.enable()
                self.assertFalse(feature.is_enabled())
                self.assertFalse(feature.dolphin_path().exists())
                self.assertFalse(feature.autostart_path().exists())

    def test_disable_failure_restores_enabled_state(self):
        with tempfile.TemporaryDirectory() as home:
            env = self._environment(home)
            with mock.patch.dict(os.environ, env, clear=False):
                self._install_runtime(env, enabled=True)
                with mock.patch.object(
                    feature,
                    "_run_service",
                    return_value=subprocess.CompletedProcess([], 0, "", ""),
                ):
                    with mock.patch.object(
                        feature, "_write_state", side_effect=feature.FeatureError("disk full")
                    ):
                        with mock.patch.object(feature, "_service_running", return_value=False):
                            with mock.patch.object(feature, "_wait_for_service"):
                                with self.assertRaisesRegex(feature.FeatureError, "restored"):
                                    feature.disable()
                self.assertTrue(feature.is_enabled())
                self.assertTrue(feature.dolphin_path().exists())
                self.assertTrue(feature.autostart_path().exists())

    def test_report_url_and_application_desktop_entry_are_stable(self):
        wrapper = Path("/home/example/.local/bin/dolphin-clean-title")
        content = feature.application_desktop_content(wrapper)
        self.assertIn("Name=Dolphin Clean Title", content)
        self.assertIn(f'Exec="{wrapper}" ui', content)
        self.assertIn(f"TryExec={wrapper}", content)
        self.assertEqual(
            feature.REPORT_URL,
            "https://github.com/d0d1/dolphin-clean-title/issues/new",
        )
