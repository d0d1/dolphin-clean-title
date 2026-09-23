import unittest
from unittest import mock

from dolphin_clean_title.x11 import CleanResult, OwnedTitle, WindowInfo, X11Connection


class X11DiagnosticTraceTests(unittest.TestCase):
    def _connection(self):
        connection = X11Connection.__new__(X11Connection)
        connection.net_wm_name = 10
        connection.wm_name = 11
        connection.wm_class = 12
        connection._ignored_property_events = {}
        connection._owned_titles = {}
        connection._get_text = mock.Mock(return_value=None)
        connection.set_net_title = mock.Mock()
        return connection

    def test_wm_class_notifications_are_identified_explicitly(self):
        connection = self._connection()
        info = WindowInfo(0x123, "dolphin", "Dolphin", "Home — Dolphin")

        with self.assertLogs("dolphin_clean_title.x11", level="DEBUG") as logs:
            result = connection._apply_title(info, connection.wm_class)

        self.assertEqual(result, CleanResult(0x123, "Home — Dolphin", "Home"))
        self.assertTrue(
            any("source=WM_CLASS" in line for line in logs.output), logs.output
        )

    def test_ignored_self_property_events_log_atom_and_remaining_count(self):
        connection = self._connection()
        connection._ignored_property_events[(0x123, connection.net_wm_name)] = 2

        with self.assertLogs("dolphin_clean_title.x11", level="DEBUG") as logs:
            self.assertTrue(
                connection._consume_ignored_property_event(
                    0x123, connection.net_wm_name
                )
            )
            self.assertTrue(
                connection._consume_ignored_property_event(
                    0x123, connection.net_wm_name
                )
            )

        self.assertFalse(
            connection._consume_ignored_property_event(0x123, connection.net_wm_name)
        )
        self.assertEqual(
            connection._ignored_property_events, {}
        )
        self.assertIn("window 0x123", logs.output[0])
        self.assertIn("property=_NET_WM_NAME", logs.output[0])
        self.assertIn("atom=10", logs.output[0])
        self.assertIn("remaining_ignore_count=1", logs.output[0])
        self.assertIn("remaining_ignore_count=0", logs.output[1])

    def test_restoration_trace_identifies_changed_fields_without_values(self):
        connection = self._connection()
        owned = OwnedTitle(None, "Home", " - Dolphin", "Home")
        connection._owned_titles[0x123] = owned
        connection._get_text.side_effect = ("Home", "Music")

        with self.assertLogs("dolphin_clean_title.x11", level="DEBUG") as logs:
            connection._apply_title(
                WindowInfo(0x123, "dolphin", "Dolphin", "Music"),
                connection.wm_name,
            )
            connection._apply_title(
                WindowInfo(0x123, "dolphin", "Dolphin", "Videos — Dolphin"),
                connection.net_wm_name,
            )

        self.assertIn(
            "restore_base_changed=yes restore_suffix_changed=no "
            "cleaned_title_changed=yes",
            logs.output[1],
        )
        self.assertIn(
            "restore_base_changed=yes restore_suffix_changed=yes "
            "cleaned_title_changed=yes",
            logs.output[3],
        )
        self.assertNotIn("Music", "\n".join(logs.output))
        self.assertNotIn("Videos", "\n".join(logs.output))

    def test_initial_refresh_delivers_rewrite_result_once(self):
        connection = self._connection()
        info = WindowInfo(0x123, "dolphin", "Dolphin", "Home — Dolphin")
        result = CleanResult(0x123, "Home — Dolphin", "Home")
        connection._get_window_ids = mock.Mock(return_value={0x123})
        connection._subscribe = mock.Mock()
        connection.window_info = mock.Mock(return_value=info)
        connection.rewrite_if_needed = mock.Mock(return_value=result)
        callback = mock.Mock()

        self.assertEqual(connection.refresh(set(), callback), {0x123})

        callback.assert_called_once_with(result)


if __name__ == "__main__":
    unittest.main()
