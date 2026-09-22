import io
import os
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from dolphin_clean_title import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RuntimeLifecycleTests(unittest.TestCase):
    def test_prepare_launch_returns_active_state(self):
        with mock.patch.object(app.feature, "prepare_launch", return_value=True) as prepare:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(app.main(["--prepare-launch"]), 0)
        prepare.assert_called_once_with()

    def test_prepare_launch_returns_inactive_state_without_error(self):
        with mock.patch.object(app.feature, "prepare_launch", return_value=False):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(app.main(["--prepare-launch"]), 1)

    def test_background_passes_authorized_install_id_to_foreground(self):
        info = SimpleNamespace(display=":test")
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    app.feature, "authorize_service_start", return_value="install-a"
                )
            )
            stack.enter_context(
                mock.patch.object(
                    app.feature, "prepare_service_start", return_value=False
                )
            )
            stack.enter_context(
                mock.patch.object(app, "validate_x11_session", return_value=info)
            )
            stack.enter_context(mock.patch.object(app, "X11Connection"))
            popen = stack.enter_context(mock.patch.object(app.subprocess, "Popen"))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(app.start_background(False, None, "install-a"), 0)

        command = popen.call_args.args[0]
        self.assertEqual(command[-2:], ["--expected-install-id", "install-a"])
        self.assertIn("--foreground", command)
        self.assertEqual(
            popen.call_args.kwargs["env"][app.feature.EXPECTED_INSTALL_ID_ENV],
            "install-a",
        )

    def test_packaged_launcher_marks_packaged_runtime(self):
        launcher = (PROJECT_ROOT / "packaging" / "dolphin-clean-title").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "export DOLPHIN_CLEAN_TITLE_PACKAGED_RUNTIME=1",
            launcher,
        )

    def test_packaged_service_stops_when_runtime_disappears(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "__main__.py"
            sentinel.write_text("# packaged runtime\n", encoding="utf-8")
            observed = []

            class FakeConnection:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc_value, _traceback):
                    return None

                def server_description(self):
                    return "test X11 server"

                def run(self, stop_requested, _on_cleaned):
                    observed.append(stop_requested())
                    sentinel.unlink()
                    observed.append(stop_requested())

            with ExitStack() as stack:
                stack.enter_context(
                    mock.patch.dict(
                        os.environ,
                        {app.PACKAGED_RUNTIME_ENV: "1"},
                        clear=False,
                    )
                )
                stack.enter_context(
                    mock.patch.object(app, "PACKAGED_RUNTIME_SENTINEL", sentinel)
                )
                stack.enter_context(
                    mock.patch.object(
                        app,
                        "validate_x11_session",
                        return_value=SimpleNamespace(
                            session_type="x11",
                            display=":test",
                            boundary="X11",
                        ),
                    )
                )
                stack.enter_context(
                    mock.patch.object(app, "configure_logging", return_value=sentinel)
                )
                stack.enter_context(
                    mock.patch.object(
                        app, "X11Connection", return_value=FakeConnection()
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        app, "InstanceLock", return_value=mock.MagicMock()
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        app.feature,
                        "authorize_service_start",
                        return_value="install-a",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        app.feature,
                        "packaged_install_id_matches",
                        return_value=True,
                    )
                )
                self.assertEqual(app.run_foreground(False, None, "install-a"), 0)

            self.assertEqual(observed, [False, True])

    def test_packaged_service_stops_when_install_identity_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "__main__.py"
            system_id = Path(directory) / "install-id"
            sentinel.write_text("# packaged runtime\n", encoding="utf-8")
            system_id.write_text("install-a\n", encoding="ascii")
            observed = []

            class FakeConnection:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc_value, _traceback):
                    return None

                def server_description(self):
                    return "test X11 server"

                def run(self, stop_requested, _on_cleaned):
                    observed.append(stop_requested())
                    system_id.write_text("install-b\n", encoding="ascii")
                    observed.append(stop_requested())

            with ExitStack() as stack:
                stack.enter_context(
                    mock.patch.dict(
                        os.environ,
                        {app.PACKAGED_RUNTIME_ENV: "1"},
                        clear=False,
                    )
                )
                stack.enter_context(
                    mock.patch.object(app, "PACKAGED_RUNTIME_SENTINEL", sentinel)
                )
                stack.enter_context(
                    mock.patch.object(
                        app,
                        "validate_x11_session",
                        return_value=SimpleNamespace(
                            session_type="x11",
                            display=":test",
                            boundary="X11",
                        ),
                    )
                )
                stack.enter_context(
                    mock.patch.object(app, "configure_logging", return_value=sentinel)
                )
                stack.enter_context(
                    mock.patch.object(app, "X11Connection", return_value=FakeConnection())
                )
                stack.enter_context(
                    mock.patch.object(
                        app, "InstanceLock", return_value=mock.MagicMock()
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        app.feature,
                        "authorize_service_start",
                        return_value="install-a",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        app.feature,
                        "system_install_id_path",
                        return_value=system_id,
                    )
                )
                self.assertEqual(app.run_foreground(False, None, "install-a"), 0)

            self.assertEqual(observed, [False, True])

    def test_packaged_no_argument_start_uses_background_authorization(self):
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(
                    os.environ,
                    {app.PACKAGED_RUNTIME_ENV: "1"},
                    clear=False,
                )
            )
            start = stack.enter_context(
                mock.patch.object(app, "start_background", return_value=0)
            )
            self.assertEqual(app.main([]), 0)
        start.assert_called_once_with(False, None, None)

    def test_source_service_does_not_depend_on_packaged_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop(app.PACKAGED_RUNTIME_ENV, None)
                with mock.patch.object(
                    app,
                    "PACKAGED_RUNTIME_SENTINEL",
                    Path(directory) / "missing",
                ):
                    self.assertTrue(app.packaged_runtime_available())


if __name__ == "__main__":
    unittest.main()
