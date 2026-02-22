"""Secret masking for safe display in output."""

from __future__ import annotations


def mask_secret(value: str, show_chars: int = 2) -> str:
    """Mask a secret value for safe display.

    Shows first N and last N characters with asterisks in between.
    Short values are fully masked.
    """
    if not value:
        return "****"

    if len(value) <= show_chars * 2:
        return "*" * len(value)

    return f"{value[:show_chars]}{'*' * (len(value) - show_chars * 2)}{value[-show_chars:]}"
