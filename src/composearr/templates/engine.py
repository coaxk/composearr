"""Template engine for generating best-practice compose files.

Templates are YAML files in the apps/ directory with a _metadata section
that is stripped from the generated output. Variables use ${VAR} syntax
and are substituted during generation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


@dataclass
class TemplateMetadata:
    """Template metadata extracted from _metadata section."""

    name: str
    description: str = ""
    category: str = "other"
    tags: list[str] = field(default_factory=list)
    env_vars: list[dict[str, str]] = field(default_factory=list)
    ports: list[dict[str, str]] = field(default_factory=list)
    volumes_info: list[dict[str, str]] = field(default_factory=list)


@dataclass
class GenerateResult:
    """Result of template generation."""

    compose_path: Path
    env_path: Path | None = None
    variables_used: dict[str, str] = field(default_factory=dict)


class TemplateEngine:
    """Engine for generating compose files from templates.

    Templates live in the apps/ directory alongside this module.
    Each template is a YAML file with a _metadata section and a standard
    Docker Compose structure.
    """

    def __init__(self) -> None:
        self.templates_dir = Path(__file__).parent / "apps"

    def list_templates(self) -> dict[str, TemplateMetadata]:
        """List all available templates with their metadata."""
        templates: dict[str, TemplateMetadata] = {}
        yaml = YAML()

        for template_file in sorted(self.templates_dir.glob("*.yaml")):
            name = template_file.stem
            if name.startswith("_"):
                continue  # Skip internal files

            try:
                data = yaml.load(template_file)
                if not isinstance(data, dict):
                    continue

                meta_raw = data.get("_metadata", {})
                if not isinstance(meta_raw, dict):
                    meta_raw = {}

                templates[name] = TemplateMetadata(
                    name=name,
                    description=meta_raw.get("description", ""),
                    category=meta_raw.get("category", "other"),
                    tags=meta_raw.get("tags", []),
                    env_vars=meta_raw.get("env_vars", []),
                    ports=meta_raw.get("ports", []),
                    volumes_info=meta_raw.get("volumes_info", []),
                )
            except Exception:
                continue  # Skip malformed templates

        return templates

    def get_template(self, name: str) -> TemplateMetadata | None:
        """Get metadata for a specific template."""
        templates = self.list_templates()
        return templates.get(name)

    def generate(
        self,
        template_name: str,
        output_dir: Path,
        variables: dict[str, str] | None = None,
    ) -> GenerateResult:
        """Generate compose files from a template.

        Args:
            template_name: Name of the template (e.g. 'sonarr')
            output_dir: Directory to write generated files
            variables: Variable substitutions (e.g. {'PUID': '1000'})

        Returns:
            GenerateResult with paths to generated files
        """
        template_file = self.templates_dir / f"{template_name}.yaml"
        if not template_file.is_file():
            available = ", ".join(sorted(self.list_templates().keys()))
            raise ValueError(
                f"Template '{template_name}' not found.\n"
                f"Available templates: {available or 'none'}"
            )

        yaml = YAML()
        data = yaml.load(template_file)
        if not isinstance(data, dict):
            raise ValueError(f"Template '{template_name}' is not valid YAML")

        # Extract and remove metadata
        meta_raw = data.pop("_metadata", {})
        if not isinstance(meta_raw, dict):
            meta_raw = {}

        variables = variables or {}

        # Ensure output directory exists
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Convert compose data to string for variable substitution
        yaml_out = YAML()
        yaml_out.default_flow_style = False

        import io
        stream = io.StringIO()
        yaml_out.dump(data, stream)
        compose_str = stream.getvalue()

        # Substitute ${VAR} patterns
        for key, value in variables.items():
            compose_str = compose_str.replace(f"${{{key}}}", str(value))

        # Write compose file
        compose_path = output_dir / "compose.yaml"
        compose_path.write_text(compose_str, encoding="utf-8")

        # Generate .env file from metadata
        env_path = None
        env_vars = meta_raw.get("env_vars", [])
        if env_vars:
            env_path = output_dir / ".env"
            lines = [f"# Environment variables for {template_name}", ""]
            for var in env_vars:
                var_name = var.get("name", "")
                default = variables.get(var_name, var.get("default", ""))
                desc = var.get("description", "")
                if desc:
                    lines.append(f"# {desc}")
                lines.append(f"{var_name}={default}")
                lines.append("")
            env_path.write_text("\n".join(lines), encoding="utf-8")

        return GenerateResult(
            compose_path=compose_path,
            env_path=env_path,
            variables_used=variables,
        )
