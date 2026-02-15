"""Shannon entropy analysis for secret detection."""

from __future__ import annotations

import math
import re
from collections import Counter

# Values that look high-entropy but are common config, not secrets
_FALSE_POSITIVE_PATTERNS = re.compile(
    r"^("
    r"/[a-zA-Z0-9/_.-]+|"  # File paths
    r"https?://[^\s]+|"  # URLs
    r"[a-z][a-z0-9]*\.[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)*|"  # Domain-like (com.example.app)
    r"[a-z]+(-[a-z]+)+-[a-z]+|"  # kebab-case words
    r"[a-z]+(_[a-z]+)+_[a-z]+|"  # snake_case words
    r"[A-Za-z]+/[A-Za-z_]+"  # Timezone-like (Australia/Sydney, America/New_York)
    r")$",
    re.IGNORECASE,
)


def calculate_shannon_entropy(value: str) -> float:
    """Calculate normalized Shannon entropy of a string.

    Returns a value between 0.0 (all same character) and 1.0 (maximum entropy).
    Empty strings return 0.0.
    """
    if not value or len(value) < 2:
        return 0.0

    counts = Counter(value)
    length = len(value)
    raw_entropy = -sum(
        (count / length) * math.log2(count / length)
        for count in counts.values()
    )

    # Normalize: max possible entropy for this length is log2(min(length, charset_size))
    # Use charset_size = number of unique chars observed for normalization
    max_entropy = math.log2(min(length, 256))
    if max_entropy == 0:
        return 0.0

    return min(raw_entropy / max_entropy, 1.0)


def is_likely_secret(value: str, threshold: float = 0.75, min_length: int = 16) -> tuple[bool, float]:
    """Determine if a value is likely a secret based on entropy.

    Returns (is_secret, entropy_score).
    """
    if not value or len(value) < min_length:
        return False, 0.0

    # Skip obvious non-secrets
    if _FALSE_POSITIVE_PATTERNS.match(value):
        return False, 0.0

    entropy = calculate_shannon_entropy(value)
    return entropy >= threshold, entropy


def rate_secret_strength(value: str) -> tuple[str, float]:
    """Rate a secret's strength based on length and entropy.

    Returns (rating, entropy) where rating is 'weak', 'medium', or 'strong'.
    """
    if not value:
        return "weak", 0.0

    entropy = calculate_shannon_entropy(value)
    length = len(value)

    # Combine length and entropy for rating
    if length < 12 or entropy < 0.5:
        return "weak", entropy
    elif length < 24 or entropy < 0.7:
        return "medium", entropy
    else:
        return "strong", entropy
