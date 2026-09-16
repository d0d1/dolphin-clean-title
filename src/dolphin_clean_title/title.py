"""Pure title matching and rewriting rules."""

from __future__ import annotations

SUFFIXES = ("— Dolphin", "- Dolphin")


def clean_title(title: str) -> str:
    """Remove one supported suffix when it occurs at the end of *title*.

    The optional single space immediately before the suffix is formatting
    around the suffix, not part of the application title.
    """

    for suffix in SUFFIXES:
        if title.endswith(suffix):
            prefix = title[: -len(suffix)]
            if prefix.endswith(" "):
                prefix = prefix[:-1]
            return prefix
    return title


def has_supported_suffix(title: str) -> bool:
    """Return whether *title* has a suffix this project is allowed to remove."""

    return clean_title(title) != title
