import unittest

from dolphin_clean_title.title import (
    clean_title,
    has_supported_suffix,
    split_supported_suffix,
)


class TitleRuleTests(unittest.TestCase):
    def test_supported_suffixes_are_removed(self):
        cases = {
            "Home — Dolphin": "Home",
            "Home— Dolphin": "Home",
            "Home - Dolphin": "Home",
            "Home- Dolphin": "Home",
            "Dolphin — Dolphin": "Dolphin",
        }
        for original, expected in cases.items():
            with self.subTest(original=original):
                self.assertEqual(clean_title(original), expected)
                self.assertTrue(has_supported_suffix(original))

    def test_only_one_trailing_suffix_is_removed(self):
        self.assertEqual(clean_title("Home — Dolphin — Dolphin"), "Home — Dolphin")

    def test_nonmatching_titles_are_unchanged(self):
        cases = (
            "",
            "Home",
            "Home — dolphin",
            "Home – Dolphin",
            "Home - Dolphin ",
            "Dolphin",
            "Home — Dolphin —",
        )
        for title in cases:
            with self.subTest(title=title):
                self.assertEqual(clean_title(title), title)
                self.assertFalse(has_supported_suffix(title))

    def test_suffix_split_preserves_exact_separator_and_spacing(self):
        for title in (
            "Home — Dolphin",
            "Home - Dolphin",
            "Home— Dolphin",
            "Home  — Dolphin",
        ):
            with self.subTest(title=title):
                split = split_supported_suffix(title)
                self.assertIsNotNone(split)
                assert split is not None
                base, suffix = split
                self.assertEqual(base + suffix, title)
