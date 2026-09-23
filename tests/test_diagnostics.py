import tempfile
import unittest
from pathlib import Path

from dolphin_clean_title import diagnostics


class DiagnosticsPreferenceTests(unittest.TestCase):
    def test_verbose_preference_is_opt_in_and_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "verbose-logging"

            self.assertFalse(diagnostics.verbose_logging_enabled(path))
            self.assertTrue(diagnostics.set_verbose_logging(True, path))
            self.assertTrue(diagnostics.verbose_logging_enabled(path))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

            self.assertFalse(diagnostics.set_verbose_logging(False, path))
            self.assertFalse(diagnostics.verbose_logging_enabled(path))
            self.assertFalse(path.exists())

    def test_unmanaged_diagnostic_preference_collision_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "verbose-logging"
            original = b"keep this unrelated file\n"
            path.write_bytes(original)

            with self.assertRaisesRegex(diagnostics.DiagnosticsError, "collides"):
                diagnostics.set_verbose_logging(True, path)

            self.assertEqual(path.read_bytes(), original)

    def test_symlink_collision_is_not_followed_or_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text("unrelated\n", encoding="utf-8")
            path = root / "verbose-logging"
            path.symlink_to(target)

            with self.assertRaisesRegex(diagnostics.DiagnosticsError, "collides"):
                diagnostics.set_verbose_logging(False, path)

            self.assertTrue(path.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "unrelated\n")


if __name__ == "__main__":
    unittest.main()
