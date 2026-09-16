import unittest

from dolphin_clean_title.environment import EnvironmentError, validate_x11_session


class EnvironmentTests(unittest.TestCase):
    def test_x11_session_requires_display(self):
        with self.assertRaisesRegex(EnvironmentError, "DISPLAY is not set"):
            validate_x11_session({"XDG_SESSION_TYPE": "x11"})

    def test_wayland_is_rejected(self):
        with self.assertRaisesRegex(EnvironmentError, "supports X11 sessions only"):
            validate_x11_session(
                {
                    "XDG_SESSION_TYPE": "wayland",
                    "DISPLAY": ":0",
                    "WAYLAND_DISPLAY": "wayland-0",
                }
            )

    def test_x11_session_is_accepted(self):
        info = validate_x11_session({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"})
        self.assertEqual(info.session_type, "x11")
        self.assertEqual(info.display, ":0")
