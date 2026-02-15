"""Explain command — detailed rule documentation."""

from __future__ import annotations

from composearr.models import Severity

# Detailed rule explanations — keyed by rule ID
RULE_DOCS: dict[str, dict] = {
    "CA001": {
        "why": (
            "Using :latest or no tag means your container image can change without "
            "warning. A Docker pull or rebuild could introduce breaking changes, "
            "security vulnerabilities, or incompatible versions across your stack."
        ),
        "scenarios": [
            "Auto-update tools (Watchtower, Ouroboros) pull :latest and restart — your app breaks at 3am",
            "You recreate a container months later and get a completely different version",
            "Two nodes in a cluster pull :latest at different times and run different versions",
        ],
        "fix_examples": [
            ("Pin to a specific version tag", "image: linuxserver/sonarr:4.0.14"),
            ("Pin to a major version (LinuxServer convention)", "image: lscr.io/linuxserver/sonarr:latest\n# Better: image: lscr.io/linuxserver/sonarr:4.0.14"),
            ("Use SHA digest for maximum reproducibility", "image: nginx@sha256:abc123def456..."),
        ],
        "related": ["CA003"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#image",
            "https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/",
        ],
    },
    "CA003": {
        "why": (
            "Images from unknown or untrusted registries may contain malware, "
            "crypto miners, or backdoors. Stick to well-known registries like "
            "Docker Hub, GHCR, LSCR, or your own verified private registry."
        ),
        "scenarios": [
            "A typosquatted registry (e.g. ghrc.io instead of ghcr.io) serves a malicious image",
            "An obscure registry goes offline and your stack can't pull images",
            "A community registry has no vulnerability scanning or image signing",
        ],
        "fix_examples": [
            ("Use Docker Hub official images", "image: nginx:1.25"),
            ("Use LinuxServer.io (LSCR)", "image: lscr.io/linuxserver/sonarr:4.0.14"),
            ("Use GitHub Container Registry", "image: ghcr.io/linuxserver/sonarr:4.0.14"),
        ],
        "related": ["CA001"],
        "learn_more": [
            "https://docs.docker.com/docker-hub/official_images/",
            "https://docs.docker.com/docker-hub/repos/manage/hub-images/trusted-content/",
        ],
    },
    "CA101": {
        "why": (
            "Hardcoded secrets in compose files end up in version control, backups, "
            "and logs. Anyone with file access can read them. Use environment variables "
            "from a .env file or Docker secrets instead."
        ),
        "scenarios": [
            "You push your compose file to GitHub and expose database passwords",
            "A backup of your Docker directory leaks credentials",
            "Team members who only need read access to compose files can see all secrets",
        ],
        "fix_examples": [
            ("Move secrets to .env file", "# .env\nDB_PASSWORD=your_secret_here\n\n# compose.yaml\nenvironment:\n  DB_PASSWORD: ${DB_PASSWORD}"),
            ("Use Docker secrets (Swarm mode)", "secrets:\n  db_password:\n    file: ./db_password.txt\nservices:\n  app:\n    secrets:\n      - db_password"),
        ],
        "related": [],
        "learn_more": [
            "https://docs.docker.com/compose/how-tos/use-secrets/",
            "https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/",
        ],
    },
    "CA201": {
        "why": (
            "Without a healthcheck, Docker has no way to know if your application "
            "is actually working. The container may be running but the app inside "
            "could be crashed, hung, or unresponsive. Healthchecks enable automatic "
            "restart and proper load balancing."
        ),
        "scenarios": [
            "Sonarr crashes but the container stays 'running' — you don't notice for days",
            "A database connection pool exhausts and the app hangs but Docker reports healthy",
            "depends_on with condition: service_healthy can't work without a healthcheck defined",
        ],
        "fix_examples": [
            ("HTTP healthcheck for *arr services", "healthcheck:\n  test: curl -sf http://localhost:8989/api/v3/health || exit 1\n  interval: 30s\n  timeout: 10s\n  retries: 3"),
            ("Command healthcheck for databases", "healthcheck:\n  test: pg_isready -U postgres\n  interval: 30s\n  timeout: 10s\n  retries: 5"),
            ("TCP healthcheck fallback", "healthcheck:\n  test: [\"CMD-SHELL\", \"nc -z localhost 8080 || exit 1\"]\n  interval: 30s\n  timeout: 10s\n  retries: 3"),
        ],
        "related": ["CA202"],
        "learn_more": [
            "https://docs.docker.com/reference/dockerfile/#healthcheck",
            "https://docs.docker.com/compose/compose-file/05-services/#healthcheck",
        ],
    },
    "CA202": {
        "why": (
            "Setting healthcheck.test to NONE or using 'exit 0' effectively disables "
            "the healthcheck. This defeats the purpose of health monitoring and can "
            "mask real application failures."
        ),
        "scenarios": [
            "A template includes healthcheck: NONE to override a Dockerfile healthcheck",
            "Someone uses 'exit 0' as a placeholder and forgets to replace it",
        ],
        "fix_examples": [
            ("Replace with a real healthcheck", "healthcheck:\n  test: curl -sf http://localhost:8080/health || exit 1\n  interval: 30s\n  timeout: 10s\n  retries: 3"),
        ],
        "related": ["CA201"],
        "learn_more": [
            "https://docs.docker.com/reference/dockerfile/#healthcheck",
        ],
    },
    "CA203": {
        "why": (
            "Without a restart policy, containers that crash or exit stay stopped. "
            "After a host reboot, none of your services will start automatically. "
            "Use 'unless-stopped' for most services."
        ),
        "scenarios": [
            "Your server reboots after a power outage — all services stay down until you manually start them",
            "An OOM kill stops a container and it never comes back",
            "A transient error crashes the app once but it would work on retry",
        ],
        "fix_examples": [
            ("Add restart policy (recommended)", "services:\n  sonarr:\n    image: linuxserver/sonarr:4.0.14\n    restart: unless-stopped"),
            ("For development services", "restart: \"no\"  # Only for dev/test containers"),
        ],
        "related": ["CA201"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#restart",
            "https://docs.docker.com/reference/cli/docker/container/run/#restart",
        ],
    },
    "CA301": {
        "why": (
            "Two services binding to the same host port will cause one of them to "
            "fail at startup. Docker can't share a port between containers unless "
            "you use different host IPs."
        ),
        "scenarios": [
            "qBittorrent and SABnzbd both try to use port 8080",
            "Two services from different compose files conflict because you didn't notice the overlap",
            "A service uses a common port (3000, 8080) that another service also needs",
        ],
        "fix_examples": [
            ("Change one service's host port", "ports:\n  - \"8081:8080\"  # Changed from 8080 to avoid conflict"),
            ("Use different host IPs", "ports:\n  - \"127.0.0.1:8080:80\"  # Service A\n  - \"192.168.1.100:8080:80\"  # Service B"),
        ],
        "related": [],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#ports",
        ],
    },
    "CA401": {
        "why": (
            "When PUID/PGID differ across services that share files (via volumes), "
            "one service may not be able to read or write files created by another. "
            "This causes permission errors, especially with *arr services and download "
            "clients sharing a /data mount."
        ),
        "scenarios": [
            "Sonarr (PUID=1000) can't import files downloaded by SABnzbd (PUID=0)",
            "Radarr creates files that Plex (different PUID) can't read for library scanning",
            "Hardlinks fail because different UIDs own the source and destination",
        ],
        "fix_examples": [
            ("Set consistent PUID/PGID across all services", "environment:\n  - PUID=1000\n  - PGID=1000"),
            ("Find your user's UID/GID", "# Run: id $USER\n# uid=1000(user) gid=1000(user)"),
        ],
        "related": ["CA402", "CA601"],
        "learn_more": [
            "https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/",
            "https://docs.linuxserver.io/general/understanding-puid-and-pgid/",
        ],
    },
    "CA402": {
        "why": (
            "Inconsistent UMASK values across services mean files are created with "
            "different permissions. This can cause access issues when services share "
            "files through mounted volumes."
        ),
        "scenarios": [
            "One service creates files with UMASK=022 (readable) while another uses UMASK=077 (private)",
            "A download client creates files that the *arr service can't move or rename",
        ],
        "fix_examples": [
            ("Set consistent UMASK across services", "environment:\n  - UMASK=002  # Group-writable (recommended for shared access)"),
        ],
        "related": ["CA401"],
        "learn_more": [
            "https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/",
        ],
    },
    "CA403": {
        "why": (
            "Without an explicit TZ environment variable, containers default to UTC. "
            "This makes log timestamps confusing and can cause scheduled tasks "
            "(backups, searches) to run at unexpected times."
        ),
        "scenarios": [
            "Sonarr's episode search runs at 3am UTC instead of your local 3am",
            "Log timestamps don't match your system clock, making debugging harder",
            "Scheduled backups in *arr services trigger at wrong times",
        ],
        "fix_examples": [
            ("Add timezone to each service", "environment:\n  - TZ=Australia/Sydney"),
            ("Use .env for consistency", "# .env\nTZ=America/New_York\n\n# compose.yaml\nenvironment:\n  - TZ=${TZ}"),
        ],
        "related": ["CA401"],
        "learn_more": [
            "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
        ],
    },
    "CA601": {
        "why": (
            "For hardlinks to work between download clients and *arr services, both "
            "must see the same filesystem paths. If Sonarr mounts /data/tv and "
            "SABnzbd mounts /data/downloads separately, hardlinks can't cross mount "
            "boundaries — Docker will fall back to slow copy+delete instead."
        ),
        "scenarios": [
            "Sonarr 'imports' a 50GB file by copying instead of instant hardlink",
            "Disk usage doubles because files exist in both download and library locations",
            "Import takes minutes instead of milliseconds",
        ],
        "fix_examples": [
            ("Use a unified /data mount", "volumes:\n  - /host/data:/data\n# Then configure paths inside the container:\n#   Downloads: /data/torrents\n#   TV: /data/media/tv\n#   Movies: /data/media/movies"),
            ("TRaSH Guide recommended structure", "# Host:\n# /data/torrents/  (download client output)\n# /data/media/tv/   (Sonarr library)\n# /data/media/movies/ (Radarr library)\n#\n# All services mount: /host/data:/data"),
        ],
        "related": ["CA401", "CA402"],
        "learn_more": [
            "https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/",
            "https://trash-guides.info/Hardlinks/Hardlinks-and-Instant-Moves/",
        ],
    },
}


def render_explanation(rule_id: str, console: "Console") -> bool:
    """Render detailed explanation for a rule. Returns False if rule not found."""
    from composearr.rules import get_rule

    rule = get_rule(rule_id)
    if rule is None:
        return False

    docs = RULE_DOCS.get(rule_id, {})

    # Color tokens
    C_TEAL = "#2dd4bf"
    C_MUTED = "#71717a"
    C_TEXT = "#fafafa"
    C_ERR = "#ef4444"
    C_WARN = "#f59e0b"
    C_INFO = "#3b82f6"

    sev_colors = {
        Severity.ERROR: C_ERR,
        Severity.WARNING: C_WARN,
        Severity.INFO: C_INFO,
    }
    sev_color = sev_colors.get(rule.severity, C_MUTED)

    console.print()
    console.print(f"  [bold {C_TEAL}]{rule.id}[/] [{C_MUTED}]\u2014[/] [bold {C_TEXT}]{rule.name}[/]")
    console.print(f"  [{sev_color}]{rule.severity.value}[/]  [{C_MUTED}]{rule.category}[/]")
    console.print()
    console.print(f"  [{C_TEXT}]{rule.description}[/]")
    console.print()

    # Why it matters
    if "why" in docs:
        console.print(f"  [bold {C_TEXT}]Why it matters[/]")
        from rich.padding import Padding
        from rich.text import Text
        why_text = Text(docs["why"])
        console.print(Padding(why_text, (0, 4, 0, 4)))
        console.print()

    # Common scenarios
    if docs.get("scenarios"):
        console.print(f"  [bold {C_TEXT}]Common scenarios[/]")
        for scenario in docs["scenarios"]:
            console.print(f"    [{C_MUTED}]\u2022[/] [{C_TEXT}]{scenario}[/]")
        console.print()

    # Fix examples
    if docs.get("fix_examples"):
        console.print(f"  [bold {C_TEXT}]How to fix[/]")
        for title, code in docs["fix_examples"]:
            console.print(f"    [{C_TEAL}]{title}:[/]")
            for code_line in code.split("\n"):
                console.print(f"      [{C_MUTED}]{code_line}[/]")
            console.print()

    # Related rules
    if docs.get("related"):
        related_str = ", ".join(f"[bold {C_TEAL}]{r}[/]" for r in docs["related"])
        console.print(f"  [bold {C_TEXT}]Related rules:[/] {related_str}")
        console.print()

    # Learn more
    if docs.get("learn_more"):
        console.print(f"  [bold {C_TEXT}]Learn more[/]")
        for url in docs["learn_more"]:
            console.print(f"    [{C_MUTED}]\u2192[/] [{C_TEAL}]{url}[/]")
        console.print()

    return True
