"""CA0xx — Image rules."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from composearr.models import LintIssue, Scope, Severity
from composearr.rules.base import BaseRule
from composearr.scanner.parser import find_line_number

if TYPE_CHECKING:
    from composearr.models import ComposeFile

# Module-level flag to control network usage
_network_enabled: bool = True


def set_network_enabled(enabled: bool) -> None:
    """Enable or disable network features for tag analysis."""
    global _network_enabled
    _network_enabled = enabled


class NoLatestTag(BaseRule):
    id = "CA001"
    name = "no-latest-tag"
    severity = Severity.WARNING
    scope = Scope.SERVICE
    description = "Image uses :latest or has no tag"
    category = "images"

    # Tags that are effectively unpinned
    _UNPINNED_TAGS = {"latest", "rolling", "nightly", "edge", "dev", "master", "main"}

    def check_service(
        self,
        service_name: str,
        service_config: dict,
        compose_file: ComposeFile,
    ) -> list[LintIssue]:
        image = service_config.get("image")
        if not image:
            return []

        image_str = str(image)

        # Parse image reference: [registry/]name[:tag][@digest]
        # If there's a digest, it's pinned regardless of tag
        if "@sha256:" in image_str:
            return []

        # Split off tag
        # Handle registry prefix (contains /) and tag (after last :)
        if ":" in image_str:
            tag = image_str.rsplit(":", 1)[1]
        else:
            tag = None

        if tag is None or tag.lower() in self._UNPINNED_TAGS:
            line = find_line_number(compose_file.raw_content, "image:", image_str)
            reason = f"uses :{tag}" if tag else "has no tag (defaults to :latest)"
            fix = self._get_tag_suggestion(image_str)
            return [
                self._make_issue(
                    f"Image {reason}",
                    str(compose_file.path),
                    line=line,
                    service=service_name,
                    fix_available=True,
                    suggested_fix=fix,
                    learn_more="https://docs.docker.com/compose/compose-file/05-services/#image",
                )
            ]

        return []

    _WHY = ":latest can pull breaking changes without warning, making rollbacks difficult"

    @staticmethod
    def _get_tag_suggestion(image: str) -> str:
        """Try to suggest a specific tag using the tag analyzer."""
        why = NoLatestTag._WHY

        if not _network_enabled:
            return f"Pin to a specific version tag \u2014 {why}"

        try:
            from composearr.analyzers.tag_analyzer import analyze_image

            suggestion = analyze_image(image)
            if suggestion and suggestion.recommended_tag:
                base = image.rsplit(":", 1)[0] if ":" in image else image
                return (
                    f"Pin to {base}:{suggestion.recommended_tag} "
                    f"({suggestion.reasoning}) \u2014 {why}"
                )
        except Exception:
            pass

        return (
            f"Pin to a specific version tag \u2014 {why}. "
            f"Check the image's registry for stable releases"
        )
