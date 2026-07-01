"""HSN code normalization and hierarchy derivation.

Leading zeros are significant in HSN/ITC(HS) codes (e.g. chapter 09 spices), so
normalization keeps digits only without stripping leading zeros.
"""

from __future__ import annotations

VALID_DIGIT_LEVELS = (2, 4, 6, 8)


class InvalidHsnCodeError(ValueError):
    """Raised when a string cannot be normalized to a valid HSN code."""


def normalize_code(raw: str) -> str:
    """Keep digits only, preserving leading zeros. Does not validate length."""
    return "".join(character for character in (raw or "") if character.isdigit())


def is_valid_level(normalized: str) -> bool:
    return len(normalized) in VALID_DIGIT_LEVELS


def normalize_strict(raw: str) -> str:
    """Normalize and require a 2/4/6/8-digit code."""
    normalized = normalize_code(raw)
    if not normalized:
        raise InvalidHsnCodeError("HSN code must contain digits.")
    if not is_valid_level(normalized):
        raise InvalidHsnCodeError(
            f"HSN code must be 2, 4, 6, or 8 digits; got {len(normalized)} digit(s)."
        )
    return normalized


def digit_level(normalized: str) -> int:
    level = len(normalized)
    if level not in VALID_DIGIT_LEVELS:
        raise InvalidHsnCodeError(f"Unsupported HSN digit level: {level}.")
    return level


def chapter_code(normalized: str) -> str | None:
    return normalized[:2] if len(normalized) >= 2 else None


def heading_code(normalized: str) -> str | None:
    return normalized[:4] if len(normalized) >= 4 else None


def subheading_code(normalized: str) -> str | None:
    return normalized[:6] if len(normalized) >= 6 else None


def parent_code(normalized: str) -> str | None:
    """Parent is the next-shorter level (8->6, 6->4, 4->2, 2->None)."""
    level = len(normalized)
    if level <= 2:
        return None
    return normalized[: level - 2]


def hierarchy(normalized: str) -> dict[str, str | None]:
    return {
        "chapter_code": chapter_code(normalized),
        "heading_code": heading_code(normalized),
        "subheading_code": subheading_code(normalized),
        "parent_code": parent_code(normalized),
    }
