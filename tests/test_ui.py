import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SOURCE = ROOT / "src" / "dolphin_clean_title" / "ui.py"


class UIConstructionTests(unittest.TestCase):
    def _tree(self) -> ast.Module:
        return ast.parse(UI_SOURCE.read_text(encoding="utf-8"))

    def test_startup_reads_status_without_reconciliation_or_polling(self):
        source = UI_SOURCE.read_text(encoding="utf-8")
        self.assertIn("self._load_status()", source)
        self.assertIn("result = (feature.status(), None)", source)
        self.assertNotIn("_status_request_id", source)
        self.assertNotIn("show_loading", source)
        self.assertNotIn("ensure_service_if_enabled", source)
        self.assertNotIn("timeout_add", source)
        self.assertNotIn("_poll_status", source)

    def test_switch_row_has_native_layout_and_no_subtitle(self):
        source = UI_SOURCE.read_text(encoding="utf-8")
        self.assertIn("self._switch_row.set_sensitive(False)", source)
        self.assertNotIn("self._switch_row.set_visible(False)", source)
        rows = [
            node
            for node in ast.walk(self._tree())
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "SwitchRow"
        ]
        self.assertEqual(len(rows), 1)
        self.assertNotIn("subtitle", {keyword.arg for keyword in rows[0].keywords})

    def test_status_load_keeps_row_present_while_initial_state_is_unavailable(self):
        source = UI_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("set_visible(False)", source)
        self.assertNotIn("set_visible(True)", source)
        self.assertIn("self._switch_row.set_sensitive(False)", source)
        self.assertIn("self._switch_row.set_sensitive(True)", source)


if __name__ == "__main__":
    unittest.main()
