"""Pure title matching and rewriting rules."""

from __future__ import annotations

SUFFIXES = ("— Dolphin", "- Dolphin")


def split_supported_suffix(title: str) -> tuple[str, str] | None:
    """Return the cleaned base and exact observed suffix form, if supported.

    The optional single space immediately before the suffix is formatting
    around the suffix, not part of the application title. The returned suffix
    includes all original separator spacing so ``base + suffix`` reconstructs
    the input exactly.
    """

    for suffix in SUFFIXES:
        if title.endswith(suffix):
            prefix = title[: -len(suffix)]
            if prefix.endswith(" "):
                prefix = prefix[:-1]
            return prefix, title[len(prefix) :]
    return None


def clean_title(title: str) -> str:
    """Remove one supported suffix when it occurs at the end of *title*."""

    split = split_supported_suffix(title)
    return split[0] if split is not None else title


def has_supported_suffix(title: str) -> bool:
    """Return whether *title* has a suffix this project is allowed to remove."""

    return split_supported_suffix(title) is not None
