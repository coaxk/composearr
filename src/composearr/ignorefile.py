"""Parser for .composearrignore files (gitignore-style patterns)."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path


class IgnoreFileParser:
    """Parse and apply .composearrignore patterns.

    Supports gitignore-style patterns:
    - Blank lines are ignored
    - Lines starting with # are comments
    - Standard glob patterns (*, ?, [abc])
    - ** matches any number of directories
    - Leading / anchors to the root directory
    - Trailing / matches only directories
    - ! negates a pattern (un-ignores)
    """

    def __init__(self) -> None:
        self._patterns: list[tuple[bool, str]] = []  # (negated, pattern)

    def parse(self, content: str) -> None:
        """Parse ignore file content and add patterns."""
        for line in content.splitlines():
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            negated = False
            if line.startswith("!"):
                negated = True
                line = line[1:]
            # Strip leading/trailing whitespace from pattern
            line = line.strip()
            if line:
                self._patterns.append((negated, line))

    def is_ignored(self, path: str) -> bool:
        """Check if a relative path should be ignored.

        Args:
            path: Relative path (forward slashes) to check.

        Returns:
            True if the path should be ignored.
        """
        ignored = False
        # Normalize path separators
        path = path.replace("\\", "/")

        for negated, pattern in self._patterns:
            if self._matches(path, pattern):
                ignored = not negated
        return ignored

    def _matches(self, path: str, pattern: str) -> bool:
        """Check if a path matches a pattern."""
        # Handle directory-only patterns (trailing /)
        dir_only = pattern.endswith("/")
        if dir_only:
            pattern = pattern.rstrip("/")

        # Handle anchored patterns (leading /)
        anchored = pattern.startswith("/")
        if anchored:
            pattern = pattern.lstrip("/")

        # Directory patterns match the directory and anything under it
        if dir_only:
            # Match exact dir name or path starting with dir/
            path_parts = path.split("/")
            if anchored:
                return path_parts[0] == pattern or path.startswith(pattern + "/")
            else:
                return pattern in path_parts or any(
                    path[i:].startswith(pattern + "/")
                    for i in range(len(path))
                    if i == 0 or path[i - 1] == "/"
                )

        # Convert ** patterns to regex-compatible form
        if "**" in pattern:
            # First convert glob ? and * (single) to placeholders
            # so they don't collide with regex syntax
            work = pattern.replace("?", "\x00QUESTION\x00")
            # Replace ** patterns with regex equivalents
            work = work.replace("**/", "\x00STARSTARSLASH\x00")
            work = work.replace("/**", "\x00SLASHSTARSTAR\x00")
            work = work.replace("**", "\x00STARSTAR\x00")
            # Replace remaining single * (glob)
            work = work.replace("*", "[^/]*")
            # Restore ** placeholders
            work = work.replace("\x00STARSTARSLASH\x00", "(.+/)?")
            work = work.replace("\x00SLASHSTARSTAR\x00", "(/.*)?")
            work = work.replace("\x00STARSTAR\x00", ".*")
            # Restore ? placeholder
            work = work.replace("\x00QUESTION\x00", "[^/]")
            # Escape dots in the remaining literal text
            regex_pattern = work
            if anchored:
                regex_pattern = "^" + regex_pattern
            else:
                regex_pattern = "(^|.*/)" + regex_pattern
            regex_pattern += "$"
            try:
                return bool(re.match(regex_pattern, path))
            except re.error:
                return False

        # Simple pattern matching
        if anchored:
            return fnmatch.fnmatch(path, pattern)
        else:
            # Match against filename or any path component
            if "/" in pattern:
                return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, "*/" + pattern)
            else:
                # Match against the filename or any path segment
                filename = path.rsplit("/", 1)[-1]
                return fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(path, pattern)


def load_ignore_file(root_path: Path) -> IgnoreFileParser:
    """Load .composearrignore from a directory, if it exists.

    Args:
        root_path: The root directory to look for .composearrignore.

    Returns:
        An IgnoreFileParser (empty if no file found).
    """
    parser = IgnoreFileParser()
    ignore_file = root_path / ".composearrignore"
    if ignore_file.is_file():
        try:
            content = ignore_file.read_text(encoding="utf-8")
            parser.parse(content)
        except OSError:
            pass  # Gracefully handle unreadable files
    return parser
