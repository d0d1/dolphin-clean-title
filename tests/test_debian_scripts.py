import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEBIAN = ROOT / "debian"


class DebianInstallIdentityTests(unittest.TestCase):
    def _script(self, name: str, root: Path) -> Path:
        source = (DEBIAN / name).read_text(encoding="utf-8")
        source = source.replace(
            "/var/lib/dolphin-clean-title", str(root / "var" / "lib" / "dolphin-clean-title")
        )
        path = root / name
        path.write_text(source, encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_postinst_creates_identity_and_upgrade_preserves_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            postinst = self._script("dolphin-clean-title.postinst", root)
            first = subprocess.run(
                [str(postinst), "configure"], capture_output=True, text=True
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            identity = root / "var" / "lib" / "dolphin-clean-title" / "install-id"
            self.assertTrue(identity.is_file())
            first_value = identity.read_text(encoding="ascii")
            self.assertTrue(first_value.strip())

            second = subprocess.run(
                [str(postinst), "configure"], capture_output=True, text=True
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(identity.read_text(encoding="ascii"), first_value)

    def test_postrm_removes_only_the_package_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            postinst = self._script("dolphin-clean-title.postinst", root)
            postrm = self._script("dolphin-clean-title.postrm", root)
            self.assertEqual(
                subprocess.run([str(postinst), "configure"], check=False).returncode,
                0,
            )
            identity = root / "var" / "lib" / "dolphin-clean-title" / "install-id"
            user_state = root / "home" / "user" / ".local" / "state" / "feature-state"
            user_state.parent.mkdir(parents=True)
            user_state.write_text("enabled\n", encoding="utf-8")

            removed = subprocess.run(
                [str(postrm), "remove"], capture_output=True, text=True
            )
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertFalse(identity.exists())
            self.assertTrue(user_state.exists())

    def test_postinst_does_not_overwrite_an_invalid_existing_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = root / "var" / "lib" / "dolphin-clean-title" / "install-id"
            identity.parent.mkdir(parents=True)
            identity.write_text("", encoding="ascii")
            postinst = self._script("dolphin-clean-title.postinst", root)
            result = subprocess.run(
                [str(postinst), "configure"], capture_output=True, text=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(identity.read_text(encoding="ascii"), "")


if __name__ == "__main__":
    unittest.main()
