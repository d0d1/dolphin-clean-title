import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from dolphin_clean_title import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RuntimeLifecycleTests(unittest.TestCase):
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
                self.assertEqual(app.run_foreground(False, None), 0)

            self.assertEqual(observed, [False, True])

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
