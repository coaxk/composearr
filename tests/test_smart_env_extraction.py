"""Comprehensive tests for Smart Env Extraction feature.

Tests cover:
- Central .env parsing
- Variable-to-stack mapping
- Per-stack .env generation
- Compose file updates
- .gitignore management
- End-to-end workflow
- Edge cases
"""

from __future__ import annotations

from pathlib import Path

import pytest

from composearr.central_env_analyzer import (
    extract_compose_var_references,
    get_extraction_preview,
    is_common_var,
    is_secret_var,
    map_vars_to_stacks,
    match_var_to_stack,
    parse_central_env,
)
from composearr.compose_env_updater import (
    add_env_file_directive,
    get_current_env_file_paths,
    update_env_file_reference,
)
from composearr.gitignore_manager import (
    check_gitignore_status,
    ensure_env_in_gitignore,
)
from composearr.stack_env_generator import (
    generate_env_content,
    write_stack_env,
)


# ── Helpers ──────────────────────────────────────────────────


def _write_env(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _write_compose(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_stack(tmp_path: Path, name: str, compose_content: str) -> Path:
    """Create a stack directory with a compose file."""
    stack_dir = tmp_path / name
    stack_dir.mkdir(parents=True, exist_ok=True)
    _write_compose(stack_dir / "compose.yaml", compose_content)
    return stack_dir


# ══════════════════════════════════════════════════════════════
# Central Env Analyzer Tests
# ══════════════════════════════════════════════════════════════


class TestParseEnv:
    def test_parse_basic_env(self, tmp_path: Path):
        env = _write_env(tmp_path / ".env", "TZ=Australia/Sydney\nPUID=1000\n")
        result = parse_central_env(env)
        assert result == {"TZ": "Australia/Sydney", "PUID": "1000"}

    def test_parse_env_with_comments(self, tmp_path: Path):
        env = _write_env(tmp_path / ".env", "# Common\nTZ=UTC\n# Secret\nAPI_KEY=abc\n")
        result = parse_central_env(env)
        assert "TZ" in result
        assert "API_KEY" in result
        assert len(result) == 2

    def test_parse_env_missing_file(self, tmp_path: Path):
        result = parse_central_env(tmp_path / "nonexistent.env")
        assert result == {}

    def test_parse_env_empty_file(self, tmp_path: Path):
        env = _write_env(tmp_path / ".env", "")
        result = parse_central_env(env)
        assert result == {}

    def test_parse_env_with_quotes(self, tmp_path: Path):
        env = _write_env(tmp_path / ".env", 'MY_VAR="hello world"\n')
        result = parse_central_env(env)
        assert result["MY_VAR"] == "hello world"


class TestVarClassification:
    def test_common_vars(self):
        assert is_common_var("TZ") is True
        assert is_common_var("PUID") is True
        assert is_common_var("PGID") is True
        assert is_common_var("UMASK") is True
        assert is_common_var("API_KEY") is False

    def test_secret_vars(self):
        assert is_secret_var("SONARR_API_KEY") is True
        assert is_secret_var("PLEX_TOKEN") is True
        assert is_secret_var("DB_PASSWORD") is True
        assert is_secret_var("MY_SECRET") is True
        assert is_secret_var("TZ") is False
        assert is_secret_var("DOCKER_HOST") is False

    def test_prefix_matching(self):
        assert match_var_to_stack("SONARR_API_KEY", "sonarr") is True
        assert match_var_to_stack("RADARR_API_KEY", "radarr") is True
        assert match_var_to_stack("RADARR_API_KEY", "sonarr") is False
        assert match_var_to_stack("PLEX_TOKEN", "plex") is True
        assert match_var_to_stack("TZ", "sonarr") is False

    def test_prefix_matching_hyphen_stack(self):
        assert match_var_to_stack("PLEX_AUTO_LANGUAGES_VAR", "plex-auto-languages") is True


class TestExtractComposeRefs:
    def test_extract_interpolation_refs(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp:${APP_VERSION}\n    ports:\n      - ${APP_PORT}:8080\n",
        )
        refs = extract_compose_var_references(compose)
        assert "APP_VERSION" in refs
        assert "APP_PORT" in refs

    def test_extract_env_list_refs(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    environment:\n      - PUID=1000\n      - API_KEY=${SONARR_API_KEY}\n",
        )
        refs = extract_compose_var_references(compose)
        assert "PUID" in refs
        assert "SONARR_API_KEY" in refs

    def test_extract_default_value_refs(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    environment:\n      TZ: ${TZ:-UTC}\n",
        )
        refs = extract_compose_var_references(compose)
        assert "TZ" in refs

    def test_extract_nonexistent_file(self, tmp_path: Path):
        refs = extract_compose_var_references(tmp_path / "nonexistent.yaml")
        assert refs == set()


class TestMapVarsToStacks:
    def test_basic_mapping(self, tmp_path: Path):
        _write_env(tmp_path / ".env", "TZ=UTC\nSONARR_API_KEY=abc\nRADARR_API_KEY=def\n")
        _make_stack(
            tmp_path, "sonarr",
            "services:\n  sonarr:\n    image: sonarr\n    environment:\n      - SONARR_API_KEY=${SONARR_API_KEY}\n",
        )
        _make_stack(
            tmp_path, "radarr",
            "services:\n  radarr:\n    image: radarr\n    environment:\n      - RADARR_API_KEY=${RADARR_API_KEY}\n",
        )

        env_vars = parse_central_env(tmp_path / ".env")
        mapping = map_vars_to_stacks(env_vars, tmp_path)

        # TZ is common — goes to all
        assert "TZ" in mapping["sonarr"]
        assert "TZ" in mapping["radarr"]
        # Prefixed vars go to matching stack
        assert "SONARR_API_KEY" in mapping["sonarr"]
        assert "SONARR_API_KEY" not in mapping["radarr"]
        assert "RADARR_API_KEY" in mapping["radarr"]
        assert "RADARR_API_KEY" not in mapping["sonarr"]

    def test_common_vars_go_to_all(self, tmp_path: Path):
        _write_env(tmp_path / ".env", "TZ=UTC\nPUID=1000\nPGID=1000\n")
        _make_stack(tmp_path, "app1", "services:\n  app:\n    image: app1\n")
        _make_stack(tmp_path, "app2", "services:\n  app:\n    image: app2\n")

        env_vars = parse_central_env(tmp_path / ".env")
        mapping = map_vars_to_stacks(env_vars, tmp_path)

        for stack in ("app1", "app2"):
            assert mapping[stack]["TZ"] == "UTC"
            assert mapping[stack]["PUID"] == "1000"

    def test_unmatched_vars_go_to_all(self, tmp_path: Path):
        _write_env(tmp_path / ".env", "DOCKER_HOST=tcp://localhost:2375\n")
        _make_stack(tmp_path, "app1", "services:\n  app:\n    image: app1\n")
        _make_stack(tmp_path, "app2", "services:\n  app:\n    image: app2\n")

        env_vars = parse_central_env(tmp_path / ".env")
        mapping = map_vars_to_stacks(env_vars, tmp_path)

        assert "DOCKER_HOST" in mapping["app1"]
        assert "DOCKER_HOST" in mapping["app2"]

    def test_referenced_vars_match(self, tmp_path: Path):
        _write_env(tmp_path / ".env", "SPECIAL_VAR=value\n")
        _make_stack(
            tmp_path, "app1",
            "services:\n  app:\n    environment:\n      - SPECIAL_VAR=${SPECIAL_VAR}\n",
        )
        _make_stack(tmp_path, "app2", "services:\n  app:\n    image: app2\n")

        env_vars = parse_central_env(tmp_path / ".env")
        mapping = map_vars_to_stacks(env_vars, tmp_path)

        assert "SPECIAL_VAR" in mapping["app1"]
        # SPECIAL_VAR matched by ref to app1, so it doesn't go to app2
        # app2 has no matched vars at all, so it's excluded from the result
        assert "app2" not in mapping

    def test_empty_stacks_dir(self, tmp_path: Path):
        env_vars = {"TZ": "UTC"}
        mapping = map_vars_to_stacks(env_vars, tmp_path)
        assert mapping == {}

    def test_nonexistent_dir(self, tmp_path: Path):
        env_vars = {"TZ": "UTC"}
        mapping = map_vars_to_stacks(env_vars, tmp_path / "nonexistent")
        assert mapping == {}

    def test_hidden_dirs_skipped(self, tmp_path: Path):
        _write_env(tmp_path / ".env", "TZ=UTC\n")
        # Hidden directory should be skipped
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        _write_compose(hidden / "compose.yaml", "services:\n  app:\n    image: app\n")
        # Normal directory
        _make_stack(tmp_path, "app1", "services:\n  app:\n    image: app\n")

        env_vars = parse_central_env(tmp_path / ".env")
        mapping = map_vars_to_stacks(env_vars, tmp_path)

        assert "app1" in mapping
        assert ".hidden" not in mapping


class TestExtractionPreview:
    def test_preview_categorization(self):
        stack_mapping = {
            "sonarr": {
                "TZ": "UTC",
                "PUID": "1000",
                "SONARR_API_KEY": "abc123",
                "DOCKER_HOST": "tcp://localhost",
            }
        }
        preview = get_extraction_preview(
            {"TZ": "UTC", "PUID": "1000", "SONARR_API_KEY": "abc123", "DOCKER_HOST": "tcp://localhost"},
            stack_mapping,
        )

        cats = preview["sonarr"]
        assert "TZ" in cats["common"]
        assert "PUID" in cats["common"]
        assert "SONARR_API_KEY" in cats["secrets"]
        assert "DOCKER_HOST" in cats["shared"]


# ══════════════════════════════════════════════════════════════
# Stack Env Generator Tests
# ══════════════════════════════════════════════════════════════


class TestGenerateEnvContent:
    def test_basic_generation(self):
        content = generate_env_content("sonarr", {"TZ": "UTC", "SONARR_API_KEY": "abc"})
        assert "# sonarr" in content
        assert "TZ=UTC" in content
        assert "SONARR_API_KEY=abc" in content

    def test_sections_grouped(self):
        content = generate_env_content(
            "myapp",
            {"TZ": "UTC", "PUID": "1000", "MY_API_KEY": "secret", "DEBUG": "true"},
        )
        lines = content.splitlines()
        # Common section comes first
        common_idx = next(i for i, l in enumerate(lines) if l == "# Common")
        # Secrets section
        secrets_idx = next(i for i, l in enumerate(lines) if l == "# Secrets")
        assert common_idx < secrets_idx

    def test_no_header(self):
        content = generate_env_content("app", {"TZ": "UTC"}, include_header=False)
        assert "Generated by ComposeArr" not in content
        assert "TZ=UTC" in content

    def test_header_present(self):
        content = generate_env_content("app", {"TZ": "UTC"}, include_header=True)
        assert "Generated by ComposeArr" in content
        assert "do not commit to git" in content


class TestWriteStackEnv:
    def test_write_new_env(self, tmp_path: Path):
        stack_dir = tmp_path / "myapp"
        stack_dir.mkdir()
        env_path = write_stack_env(stack_dir, "myapp", {"TZ": "UTC", "KEY": "val"})
        assert env_path.exists()
        content = env_path.read_text(encoding="utf-8")
        assert "TZ=UTC" in content

    def test_merge_existing_env(self, tmp_path: Path):
        stack_dir = tmp_path / "myapp"
        stack_dir.mkdir()
        existing = stack_dir / ".env"
        existing.write_text("EXISTING=keep\n", encoding="utf-8")

        write_stack_env(stack_dir, "myapp", {"EXISTING": "keep", "NEW_VAR": "added"}, overwrite=False)
        content = existing.read_text(encoding="utf-8")
        assert "EXISTING=keep" in content
        assert "NEW_VAR=added" in content

    def test_overwrite_existing(self, tmp_path: Path):
        stack_dir = tmp_path / "myapp"
        stack_dir.mkdir()
        existing = stack_dir / ".env"
        existing.write_text("OLD_VAR=old\n", encoding="utf-8")

        write_stack_env(stack_dir, "myapp", {"NEW_VAR": "new"}, overwrite=True)
        content = existing.read_text(encoding="utf-8")
        assert "OLD_VAR" not in content
        assert "NEW_VAR=new" in content

    def test_merge_no_duplicates(self, tmp_path: Path):
        stack_dir = tmp_path / "myapp"
        stack_dir.mkdir()
        existing = stack_dir / ".env"
        existing.write_text("TZ=UTC\nPUID=1000\n", encoding="utf-8")

        write_stack_env(stack_dir, "myapp", {"TZ": "UTC", "PUID": "1000"}, overwrite=False)
        content = existing.read_text(encoding="utf-8")
        # Should not have duplicated entries
        assert content.count("TZ=") == 1


# ══════════════════════════════════════════════════════════════
# Compose Env Updater Tests
# ══════════════════════════════════════════════════════════════


class TestUpdateEnvFileRef:
    def test_update_absolute_path(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n    env_file:\n      - /mnt/c/DockerContainers/.env\n",
        )
        changed = update_env_file_reference(compose)
        assert changed is True
        content = compose.read_text(encoding="utf-8")
        assert ".env" in content
        assert "/mnt/c/DockerContainers/.env" not in content

    def test_skip_relative_path(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n    env_file:\n      - .env\n",
        )
        changed = update_env_file_reference(compose)
        assert changed is False

    def test_update_variable_pattern(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n    env_file:\n      - ${ENV_FILE_PATH:-/default/.env}\n",
        )
        changed = update_env_file_reference(compose)
        assert changed is True

    def test_dry_run(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n    env_file:\n      - /absolute/path/.env\n",
        )
        changed = update_env_file_reference(compose, dry_run=True)
        assert changed is True
        # File should NOT be modified
        content = compose.read_text(encoding="utf-8")
        assert "/absolute/path/.env" in content

    def test_multiple_services(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            (
                "services:\n"
                "  app1:\n"
                "    image: app1\n"
                "    env_file:\n"
                "      - /central/.env\n"
                "  app2:\n"
                "    image: app2\n"
                "    env_file:\n"
                "      - /central/.env\n"
            ),
        )
        changed = update_env_file_reference(compose)
        assert changed is True
        content = compose.read_text(encoding="utf-8")
        assert content.count("/central/.env") == 0

    def test_nonexistent_file(self, tmp_path: Path):
        changed = update_env_file_reference(tmp_path / "nonexistent.yaml")
        assert changed is False

    def test_no_services(self, tmp_path: Path):
        compose = _write_compose(tmp_path / "compose.yaml", "version: '3'\n")
        changed = update_env_file_reference(compose)
        assert changed is False

    def test_string_form_env_file(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n    env_file: /absolute/.env\n",
        )
        changed = update_env_file_reference(compose)
        assert changed is True


class TestAddEnvFileDirective:
    def test_add_to_service_without(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n",
        )
        changed = add_env_file_directive(compose)
        assert changed is True
        content = compose.read_text(encoding="utf-8")
        assert "env_file" in content

    def test_skip_service_with_existing(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n    env_file:\n      - .env\n",
        )
        changed = add_env_file_directive(compose)
        assert changed is False


class TestGetCurrentEnvPaths:
    def test_get_list_paths(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n    env_file:\n      - /mnt/c/.env\n      - ./local.env\n",
        )
        paths = get_current_env_file_paths(compose)
        assert "/mnt/c/.env" in paths
        assert "./local.env" in paths

    def test_get_string_path(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n    env_file: /central/.env\n",
        )
        paths = get_current_env_file_paths(compose)
        assert "/central/.env" in paths

    def test_no_env_file(self, tmp_path: Path):
        compose = _write_compose(
            tmp_path / "compose.yaml",
            "services:\n  app:\n    image: myapp\n",
        )
        paths = get_current_env_file_paths(compose)
        assert paths == []


# ══════════════════════════════════════════════════════════════
# Gitignore Manager Tests
# ══════════════════════════════════════════════════════════════


class TestGitignoreManager:
    def test_create_new_gitignore(self, tmp_path: Path):
        changed = ensure_env_in_gitignore(tmp_path)
        assert changed is True
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert ".env" in content

    def test_update_existing_without_env(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n__pycache__/\n", encoding="utf-8")

        changed = ensure_env_in_gitignore(tmp_path)
        assert changed is True
        content = gitignore.read_text(encoding="utf-8")
        assert ".env" in content
        assert "*.log" in content  # preserved

    def test_skip_if_already_present(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n.env\n", encoding="utf-8")

        changed = ensure_env_in_gitignore(tmp_path)
        assert changed is False

    def test_custom_entries(self, tmp_path: Path):
        changed = ensure_env_in_gitignore(tmp_path, entries=[".env", ".env.local"])
        assert changed is True
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in content
        assert ".env.local" in content


class TestGitignoreStatus:
    def test_no_gitignore(self, tmp_path: Path):
        status = check_gitignore_status(tmp_path)
        assert status["gitignore_exists"] is False
        assert status["env_ignored"] is False

    def test_gitignore_without_env(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
        status = check_gitignore_status(tmp_path)
        assert status["gitignore_exists"] is True
        assert status["env_ignored"] is False

    def test_gitignore_with_env(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("*.log\n.env\n", encoding="utf-8")
        status = check_gitignore_status(tmp_path)
        assert status["gitignore_exists"] is True
        assert status["env_ignored"] is True

    def test_gitignore_with_wildcard_env(self, tmp_path: Path):
        (tmp_path / ".gitignore").write_text("*.env\n", encoding="utf-8")
        status = check_gitignore_status(tmp_path)
        assert status["env_ignored"] is True


# ══════════════════════════════════════════════════════════════
# End-to-End Tests
# ══════════════════════════════════════════════════════════════


class TestEndToEnd:
    def test_full_extraction_workflow(self, tmp_path: Path):
        """End-to-end test: central .env -> per-stack .env files."""
        # Setup: central .env
        _write_env(
            tmp_path / ".env",
            "TZ=Australia/Sydney\n"
            "PUID=1000\n"
            "PGID=1000\n"
            "SONARR_API_KEY=sonarr_secret_123\n"
            "RADARR_API_KEY=radarr_secret_456\n"
            "PLEX_TOKEN=plex_token_789\n",
        )

        # Setup: stack directories with compose files
        _make_stack(
            tmp_path, "sonarr",
            "services:\n  sonarr:\n    image: sonarr\n    env_file:\n      - /mnt/c/DockerContainers/.env\n",
        )
        _make_stack(
            tmp_path, "radarr",
            "services:\n  radarr:\n    image: radarr\n    env_file:\n      - /mnt/c/DockerContainers/.env\n",
        )
        _make_stack(
            tmp_path, "plex",
            "services:\n  plex:\n    image: plex\n    env_file:\n      - /mnt/c/DockerContainers/.env\n",
        )

        # Step 1: Parse central env
        env_vars = parse_central_env(tmp_path / ".env")
        assert len(env_vars) == 6

        # Step 2: Map to stacks
        mapping = map_vars_to_stacks(env_vars, tmp_path)
        assert "sonarr" in mapping
        assert "radarr" in mapping
        assert "plex" in mapping

        # Sonarr should have TZ, PUID, PGID, SONARR_API_KEY
        assert "SONARR_API_KEY" in mapping["sonarr"]
        assert "RADARR_API_KEY" not in mapping["sonarr"]
        assert "TZ" in mapping["sonarr"]

        # Step 3: Write per-stack .env files
        for stack_name, stack_vars in mapping.items():
            stack_dir = tmp_path / stack_name
            write_stack_env(stack_dir, stack_name, stack_vars, overwrite=True)

        # Step 4: Update compose files
        for stack_name in mapping:
            compose = tmp_path / stack_name / "compose.yaml"
            update_env_file_reference(compose)

        # Step 5: Create .gitignore files
        for stack_name in mapping:
            ensure_env_in_gitignore(tmp_path / stack_name)

        # Verify: per-stack .env files exist
        for stack_name in ("sonarr", "radarr", "plex"):
            env_file = tmp_path / stack_name / ".env"
            assert env_file.exists(), f"{stack_name}/.env should exist"

        # Verify: compose files updated
        for stack_name in ("sonarr", "radarr", "plex"):
            paths = get_current_env_file_paths(tmp_path / stack_name / "compose.yaml")
            assert all(not p.startswith("/") for p in paths), f"{stack_name} should use relative paths"

        # Verify: .gitignore created
        for stack_name in ("sonarr", "radarr", "plex"):
            status = check_gitignore_status(tmp_path / stack_name)
            assert status["env_ignored"] is True

    def test_extraction_with_no_stacks(self, tmp_path: Path):
        """Edge case: central .env exists but no stack directories."""
        _write_env(tmp_path / ".env", "TZ=UTC\n")
        env_vars = parse_central_env(tmp_path / ".env")
        mapping = map_vars_to_stacks(env_vars, tmp_path)
        assert mapping == {}

    def test_extraction_preserves_existing_env(self, tmp_path: Path):
        """Edge case: stack already has a .env file — merge, don't overwrite."""
        _write_env(tmp_path / ".env", "TZ=UTC\nNEW_VAR=hello\n")
        stack_dir = _make_stack(
            tmp_path, "myapp",
            "services:\n  app:\n    image: app\n    env_file:\n      - .env\n",
        )
        # Pre-existing .env
        (stack_dir / ".env").write_text("EXISTING=keep_me\n", encoding="utf-8")

        env_vars = parse_central_env(tmp_path / ".env")
        mapping = map_vars_to_stacks(env_vars, tmp_path)
        write_stack_env(stack_dir, "myapp", mapping["myapp"], overwrite=False)

        content = (stack_dir / ".env").read_text(encoding="utf-8")
        assert "EXISTING=keep_me" in content
        assert "NEW_VAR=hello" in content

    def test_extraction_with_docker_compose_yml(self, tmp_path: Path):
        """Edge case: stack uses docker-compose.yml instead of compose.yaml."""
        _write_env(tmp_path / ".env", "TZ=UTC\n")
        stack_dir = tmp_path / "legacy"
        stack_dir.mkdir()
        _write_compose(
            stack_dir / "docker-compose.yml",
            "services:\n  app:\n    image: app\n    env_file:\n      - /central/.env\n",
        )

        env_vars = parse_central_env(tmp_path / ".env")
        mapping = map_vars_to_stacks(env_vars, tmp_path)
        assert "legacy" in mapping
