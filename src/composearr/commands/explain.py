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
    "CA302": {
        "why": (
            "If a service declares depends_on another service but they are on "
            "incompatible networks, the dependency starts but cannot be reached. "
            "The service will fail to connect at runtime despite compose starting "
            "the dependency first."
        ),
        "scenarios": [
            "App depends on db, but app uses network_mode: host while db is on a custom network",
            "Frontend depends on API, but they are on different bridge networks with no overlap",
            "Service uses network_mode: none but depends_on a database",
        ],
        "fix_examples": [
            ("Put both services on the same network", "services:\n  app:\n    depends_on: [db]\n    networks:\n      - backend\n  db:\n    networks:\n      - backend"),
            ("Use network_mode: service: to share", "services:\n  sidecar:\n    network_mode: \"service:app\""),
        ],
        "related": ["CA301", "CA303"],
        "learn_more": [
            "https://docs.docker.com/compose/how-tos/networking/",
        ],
    },
    "CA303": {
        "why": (
            "A service with network_mode: none has no network access at all. "
            "If it also exposes ports, those ports are unreachable from outside "
            "the container — a silent misconfiguration that wastes resources."
        ),
        "scenarios": [
            "A batch processing container set to none still has ports from a template",
            "Service was isolated for security but ports were left in the config",
        ],
        "fix_examples": [
            ("Remove ports from isolated service", "services:\n  batch:\n    network_mode: none\n    # Remove: ports: [\"8080:8080\"]"),
            ("Change network mode if ports are needed", "services:\n  app:\n    # network_mode: none  # Remove this\n    ports:\n      - \"8080:8080\""),
        ],
        "related": ["CA302"],
        "learn_more": [
            "https://docs.docker.com/compose/how-tos/networking/",
        ],
    },
    "CA404": {
        "why": (
            "When the same environment variable is defined multiple times in a list, "
            "Docker silently uses the last value. This can cause confusing behavior "
            "where the 'wrong' value is active despite appearing correct in the file."
        ),
        "scenarios": [
            "DB_HOST defined twice after a copy-paste — the wrong database is connected",
            "TZ set in both environment: list and env_file, with different values",
            "A merge conflict left duplicate entries that went unnoticed",
        ],
        "fix_examples": [
            ("Remove the duplicate", "environment:\n  - DB_HOST=postgres  # Keep only one"),
            ("Use dict format to prevent duplicates", "environment:\n  DB_HOST: postgres\n  DB_PORT: \"5432\""),
        ],
        "related": ["CA403"],
        "learn_more": [
            "https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/",
        ],
    },
    "CA501": {
        "why": (
            "Without memory limits, a single misbehaving container can consume all "
            "available RAM, causing the Linux OOM killer to terminate random processes "
            "— including other containers or even the Docker daemon itself."
        ),
        "scenarios": [
            "A memory leak in Plex gradually consumes all RAM until the server crashes",
            "A download client unpacking a large archive spikes memory and OOM kills your database",
            "Your server becomes unresponsive because one container ate all the memory",
        ],
        "fix_examples": [
            ("Add memory limit via deploy", "deploy:\n  resources:\n    limits:\n      memory: 512M"),
            ("Full resource limits block", "deploy:\n  resources:\n    limits:\n      memory: 1G\n      cpus: '1.0'\n    reservations:\n      memory: 256M"),
        ],
        "related": ["CA502", "CA503"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/deploy/#resources",
            "https://docs.docker.com/config/containers/resource_constraints/",
        ],
    },
    "CA502": {
        "why": (
            "Without CPU limits, a single container can monopolize all CPU cores, "
            "starving other services. This is especially problematic for media "
            "servers doing transcoding or download clients extracting archives."
        ),
        "scenarios": [
            "Plex transcoding a 4K stream pegs all cores — Sonarr and Radarr become unresponsive",
            "A runaway process in one container causes 100% CPU on all cores",
            "Multiple services compete for CPU during peak hours",
        ],
        "fix_examples": [
            ("Add CPU limit via deploy", "deploy:\n  resources:\n    limits:\n      cpus: '0.5'  # Half a core"),
            ("Media server with more headroom", "deploy:\n  resources:\n    limits:\n      cpus: '2.0'  # 2 cores for transcoding\n      memory: 2G"),
        ],
        "related": ["CA501", "CA503"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/deploy/#resources",
            "https://docs.docker.com/config/containers/resource_constraints/",
        ],
    },
    "CA503": {
        "why": (
            "Resource limits that are significantly different from typical values "
            "for a known application may indicate a misconfiguration. Too low can "
            "cause OOM kills; too high wastes resources that other containers need."
        ),
        "scenarios": [
            "Nginx set to 4GB memory — it typically needs 128MB",
            "A database limited to 64MB — it will crash under any real load",
            "Plex limited to 0.25 CPUs — transcoding will be unusable",
        ],
        "fix_examples": [
            ("Use typical values as a starting point", "# Sonarr/Radarr: 512M memory, 0.5 CPU\n# Plex/Jellyfin: 2G memory, 2.0 CPU\n# Nginx/Caddy: 128M memory, 0.25 CPU\n# Databases: 512M-1G memory, 1.0 CPU"),
        ],
        "related": ["CA501", "CA502"],
        "learn_more": [
            "https://docs.docker.com/config/containers/resource_constraints/",
        ],
    },
    "CA504": {
        "why": (
            "Docker's default logging driver (json-file) has NO log rotation. Every "
            "line your container logs is appended to a JSON file that grows forever. "
            "On a busy server, this can fill your disk in days or weeks."
        ),
        "scenarios": [
            "A chatty application fills /var/lib/docker/containers with gigabytes of logs",
            "Disk fills up at 3am, all containers crash because they can't write",
            "You run 'docker system df' and discover logs consuming more space than images",
        ],
        "fix_examples": [
            ("Add logging with rotation", "logging:\n  driver: json-file\n  options:\n    max-size: \"10m\"\n    max-file: \"3\""),
            ("Set globally in Docker daemon config", "# /etc/docker/daemon.json\n{\n  \"log-driver\": \"json-file\",\n  \"log-opts\": {\n    \"max-size\": \"10m\",\n    \"max-file\": \"3\"\n  }\n}"),
        ],
        "related": ["CA505"],
        "learn_more": [
            "https://docs.docker.com/config/containers/logging/configure/",
            "https://docs.docker.com/config/containers/logging/json-file/",
        ],
    },
    "CA505": {
        "why": (
            "A logging driver is configured but rotation limits are missing. This "
            "means logs will still grow unbounded. Both max-size and max-file must "
            "be set for rotation to actually work."
        ),
        "scenarios": [
            "Logging driver is set to json-file but max-size is missing — same as no config",
            "max-size is set but max-file isn't — only one log file exists but it can grow forever",
        ],
        "fix_examples": [
            ("Add both rotation options", "logging:\n  driver: json-file\n  options:\n    max-size: \"10m\"  # Max size per file\n    max-file: \"3\"     # Keep 3 rotated files"),
        ],
        "related": ["CA504"],
        "learn_more": [
            "https://docs.docker.com/config/containers/logging/json-file/",
        ],
    },
    "CA701": {
        "why": (
            "Bind mounts (/host/path:/container/path) tie your compose file to a specific "
            "host directory structure. Named volumes are managed by Docker, making your "
            "stack more portable, easier to back up, and compatible with Docker's volume "
            "lifecycle (create, inspect, prune)."
        ),
        "scenarios": [
            "Moving a stack to a new server requires recreating the same directory structure",
            "Host path permissions differ between Linux, macOS, and Windows",
            "Docker Desktop on macOS/Windows has slow bind mount performance vs named volumes",
        ],
        "fix_examples": [
            ("Convert bind mount to named volume", "# Before:\nvolumes:\n  - ./data:/app/data\n\n# After:\nvolumes:\n  - app_data:/app/data\n\nvolumes:\n  app_data:"),
            ("Keep bind mount for config files", "# Bind mounts are fine for:\nvolumes:\n  - ./config.yml:/app/config.yml:ro  # Config files you edit\n  - /etc/localtime:/etc/localtime:ro  # System files"),
        ],
        "related": ["CA702", "CA601"],
        "learn_more": [
            "https://docs.docker.com/storage/volumes/",
        ],
    },
    "CA702": {
        "why": (
            "If a service references a named volume that isn't defined in the top-level "
            "volumes section, Docker Compose will create it as an anonymous volume. "
            "Anonymous volumes are harder to manage, won't survive 'docker compose down -v', "
            "and their behavior varies between Compose V1 and V2."
        ),
        "scenarios": [
            "Service uses 'mydata:/app/data' but 'mydata' isn't in the volumes section",
            "Typo in volume name leads to orphaned data across compose restarts",
            "docker compose down -v doesn't clean up the unreferenced volume",
        ],
        "fix_examples": [
            ("Define the volume", "services:\n  app:\n    volumes:\n      - app_data:/app/data\n\nvolumes:\n  app_data:  # Explicit definition"),
            ("With driver options", "volumes:\n  app_data:\n    driver: local\n    driver_opts:\n      type: none\n      o: bind\n      device: /mnt/storage/app"),
        ],
        "related": ["CA701"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/07-volumes/",
        ],
    },
    "CA304": {
        "why": (
            "DNS configuration inside containers has subtle interactions with network modes. "
            "In host mode, custom DNS settings are silently ignored. Pointing DNS to 127.0.0.1 "
            "inside a container resolves to the container itself — not the host — so local DNS "
            "resolvers (Pi-hole, AdGuard) won't work unless explicitly configured."
        ),
        "scenarios": [
            "Container with network_mode: host has dns: 1.1.1.1 — setting is silently ignored",
            "Service uses dns: 127.0.0.1 expecting the host's Pi-hole, but gets no DNS resolution",
            "VPN container tunnels DNS but downstream services still use container-local localhost",
        ],
        "fix_examples": [
            ("Use public DNS", "dns:\n  - 8.8.8.8\n  - 1.1.1.1"),
            ("Use Docker host gateway for Pi-hole", "dns:\n  - 172.17.0.1  # Docker host gateway\n  # Or use extra_hosts to map host.docker.internal"),
            ("Remove DNS from host mode service", "network_mode: host\n# Remove: dns: [...]  (host mode uses host DNS)"),
        ],
        "related": ["CA302", "CA303"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#dns",
            "https://docs.docker.com/network/#dns-services",
        ],
    },
    "CA801": {
        "why": (
            "Linux capabilities are fine-grained permissions that replace the old "
            "all-or-nothing root model. By default, Docker containers get a broad set "
            "of capabilities. Dropping all and adding back only what's needed follows "
            "the principle of least privilege and limits damage from container escapes."
        ),
        "scenarios": [
            "A compromised container with NET_RAW can sniff network traffic from other containers",
            "SYS_ADMIN capability allows mounting host filesystems from inside the container",
            "An attacker uses CAP_DAC_OVERRIDE to bypass file permission checks",
        ],
        "fix_examples": [
            ("Drop all capabilities (most services)", "cap_drop:\n  - ALL"),
            ("Drop all, add back specific ones", "cap_drop:\n  - ALL\ncap_add:\n  - NET_BIND_SERVICE  # Bind to ports < 1024"),
            ("VPN container (needs NET_ADMIN)", "cap_drop:\n  - ALL\ncap_add:\n  - NET_ADMIN"),
        ],
        "related": ["CA802", "CA804"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#cap_add",
            "https://man7.org/linux/man-pages/man7/capabilities.7.html",
        ],
    },
    "CA802": {
        "why": (
            "Privileged mode gives the container ALL host capabilities, access to all "
            "devices, and the ability to modify kernel parameters. This is essentially "
            "root on the host machine. A container escape in privileged mode means full "
            "host compromise with zero additional effort."
        ),
        "scenarios": [
            "An attacker in a privileged container mounts the host filesystem and reads /etc/shadow",
            "A vulnerability in the app allows loading a malicious kernel module",
            "The container can modify iptables rules and redirect network traffic",
        ],
        "fix_examples": [
            ("Remove privileged mode", "# Remove this:\n#   privileged: true\n\n# If specific capabilities are needed:\ncap_add:\n  - SYS_ADMIN"),
            ("Docker-in-Docker alternative (rootless)", "# Consider rootless Docker or Podman instead\n# Or use Docker socket mounting (still risky but less so):\nvolumes:\n  - /var/run/docker.sock:/var/run/docker.sock"),
        ],
        "related": ["CA801", "CA804"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#privileged",
            "https://docs.docker.com/engine/security/#linux-kernel-capabilities",
        ],
    },
    "CA803": {
        "why": (
            "A read-only root filesystem prevents processes inside the container from "
            "modifying the container's filesystem. This blocks many attack techniques "
            "that rely on writing malicious files, scripts, or binaries to disk. "
            "Services that need to write use tmpfs mounts for specific directories."
        ),
        "scenarios": [
            "Malware writes a crypto miner binary to /tmp and executes it",
            "An attacker modifies application config files to redirect traffic",
            "A compromised process plants a backdoor in the container filesystem",
        ],
        "fix_examples": [
            ("Nginx with read-only root", "read_only: true\ntmpfs:\n  - /var/cache/nginx\n  - /var/run"),
            ("Redis with read-only root", "read_only: true\ntmpfs:\n  - /data"),
            ("Traefik with read-only root", "read_only: true\ntmpfs:\n  - /tmp"),
        ],
        "related": ["CA801", "CA804"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#read_only",
        ],
    },
    "CA804": {
        "why": (
            "The no-new-privileges flag prevents processes inside the container from "
            "gaining additional privileges via setuid/setgid binaries. Even if an "
            "attacker finds a setuid root binary, they can't use it to escalate. "
            "This is safe for almost all services and blocks a common escape vector."
        ),
        "scenarios": [
            "An attacker exploits a setuid binary to gain root inside the container",
            "A process uses setgid to access files it shouldn't have permission to read",
            "Privilege escalation chain: app vulnerability → setuid binary → container root → host escape",
        ],
        "fix_examples": [
            ("Add no-new-privileges", 'security_opt:\n  - "no-new-privileges:true"'),
            ("Combine with other security options", 'security_opt:\n  - "no-new-privileges:true"\n  - "seccomp:default"'),
        ],
        "related": ["CA801", "CA802"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#security_opt",
            "https://docs.docker.com/engine/security/#linux-kernel-capabilities",
        ],
    },
    "CA901": {
        "why": (
            "Docker Compose supports both resource reservations (minimum guaranteed) and "
            "limits (maximum allowed). Defining one without the other creates unpredictable "
            "behavior: reservations without limits mean a container can consume unlimited "
            "resources beyond its guarantee, while limits without reservations mean the "
            "container may be starved under memory pressure."
        ),
        "scenarios": [
            ("Database with reservation only — can OOM the host", "deploy:\n  resources:\n    reservations:\n      memory: 1G\n    # No limits! Can use all host memory"),
            ("App with limits but no reservation — starved under pressure", "deploy:\n  resources:\n    limits:\n      memory: 512M\n    # No reservation — may be killed first under pressure"),
            ("Balanced configuration — both defined", "deploy:\n  resources:\n    reservations:\n      memory: 256M\n    limits:\n      memory: 512M"),
        ],
        "fix_examples": [
            ("Add limits alongside reservations", "deploy:\n  resources:\n    reservations:\n      memory: 256M\n      cpus: '0.25'\n    limits:\n      memory: 512M\n      cpus: '0.5'"),
            ("Add reservations alongside limits", "deploy:\n  resources:\n    reservations:\n      memory: 128M\n    limits:\n      memory: 512M"),
        ],
        "related": ["CA501", "CA502"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/deploy/#resources",
        ],
    },
    "CA902": {
        "why": (
            "The restart policy 'always' will restart a container indefinitely, even "
            "after manual stops and even when the container crashes immediately on startup. "
            "A misconfigured service with restart: always creates a crash loop that consumes "
            "resources and fills logs. 'unless-stopped' is usually what you actually want — "
            "it restarts on crashes but respects manual docker stop commands."
        ),
        "scenarios": [
            ("Crash loop — restarts 1000s of times per hour", "restart: always\n# Container has a bug and exits with code 1\n# Docker restarts it immediately, forever"),
            ("Manual stop ignored", "restart: always\n# docker stop myapp\n# Docker immediately restarts it anyway!"),
            ("Safe default — respects manual stops", "restart: unless-stopped\n# docker stop myapp → stays stopped\n# Host reboot → auto-restarts"),
        ],
        "fix_examples": [
            ("Switch to unless-stopped", "restart: unless-stopped"),
            ("Use deploy restart policy with limits", "deploy:\n  restart_policy:\n    condition: on-failure\n    max_attempts: 5\n    delay: 10s\n    window: 120s"),
        ],
        "related": ["CA203"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#restart",
            "https://docs.docker.com/compose/compose-file/deploy/#restart_policy",
        ],
    },
    "CA903": {
        "why": (
            "Tmpfs mounts live entirely in RAM. Without a size limit, a runaway process "
            "writing to a tmpfs mount can consume all available memory and cause an OOM kill "
            "of the container or even the host. Always specify a size limit for tmpfs mounts "
            "to cap memory usage."
        ),
        "scenarios": [
            ("Unbounded tmpfs — potential OOM", "tmpfs:\n  - /tmp\n# A process writing to /tmp can fill all memory"),
            ("Application writes large temp files", "tmpfs:\n  - /var/cache\n# Cache grows unbounded in RAM"),
            ("Size-limited tmpfs — safe", "tmpfs:\n  - /tmp:size=100M\n# Capped at 100MB, writes fail after that"),
        ],
        "fix_examples": [
            ("Inline size limit", "tmpfs:\n  - /tmp:size=100M"),
            ("Long-form with explicit size", "volumes:\n  - type: tmpfs\n    target: /tmp\n    tmpfs:\n      size: 104857600  # 100MB"),
        ],
        "related": ["CA501"],
        "learn_more": [
            "https://docs.docker.com/compose/compose-file/05-services/#tmpfs",
            "https://docs.docker.com/storage/tmpfs/",
        ],
    },
    "CA904": {
        "why": (
            "By default, user IDs inside a container map directly to the same UIDs on the "
            "host. This means root (UID 0) inside the container is root on the host — if a "
            "container escape occurs, the attacker has full host access. User namespace "
            "remapping maps container UIDs to unprivileged host UIDs, adding an extra "
            "security boundary."
        ),
        "scenarios": [
            ("Container root = host root", "# Default: no userns_mode\n# Root inside container has root on host\n# Container escape = game over"),
            ("Service that needs host namespace", "# Docker-in-Docker, Portainer, Traefik\n# These need host user namespace — CA904 skips them"),
            ("Remapped namespace — safer", "userns_mode: host\n# Container UIDs mapped to unprivileged host UIDs"),
        ],
        "fix_examples": [
            ("Enable user namespace remapping", "userns_mode: host"),
            ("Run as non-root user instead", "user: \"1000:1000\""),
        ],
        "related": ["CA801", "CA802"],
        "learn_more": [
            "https://docs.docker.com/engine/security/userns-remap/",
            "https://docs.docker.com/compose/compose-file/05-services/#userns_mode",
        ],
    },
}

# Extended rule details — keyed by rule ID
RULE_DETAILS: dict[str, dict] = {
    "CA001": {
        "why_it_matters": (
            "Container images tagged :latest are mutable — the same tag can point to completely "
            "different images over time. In a homelab arr stack, an unexpected image change can "
            "break API compatibility between Sonarr, Radarr, and your download clients. Pinning "
            "versions ensures reproducible deployments and predictable upgrades."
        ),
        "when_to_ignore": [
            "Development or testing environments where you always want the newest build",
            "Short-lived containers that are rebuilt frequently (CI runners, one-shot tasks)",
            "Images you build and tag locally where :latest is your only tag",
        ],
        "real_world_example": (
            "A homelab user running Sonarr, Radarr, and Prowlarr all on :latest woke up to find "
            "Prowlarr had auto-updated to v2 overnight via Watchtower. The new version changed its "
            "API, breaking all indexer connections in Sonarr and Radarr. Pinning to specific version "
            "tags would have prevented the silent upgrade."
        ),
        "fix_explanation": (
            "The auto-fix replaces :latest with the most recent stable version tag from the "
            "registry for known images. For unknown images, it flags the line for manual pinning."
        ),
    },
    "CA003": {
        "why_it_matters": (
            "Pulling images from untrusted registries is a supply-chain risk. Malicious images can "
            "contain crypto miners, backdoors, or data exfiltration tools that run silently in your "
            "homelab. Sticking to Docker Hub, GHCR, or LSCR ensures images are scanned and signed."
        ),
        "when_to_ignore": [
            "Private registries you control (e.g., your own Harbor or Nexus instance)",
            "Vendor-specific registries for commercial software (e.g., registry.gitlab.com)",
            "Air-gapped environments where images are pre-vetted before import",
        ],
        "real_world_example": (
            "A user found a community Docker image for a niche torrent client on an unknown registry. "
            "The image worked fine but was secretly running a Monero miner in the background, consuming "
            "CPU and inflating the electricity bill. Switching to the official Docker Hub image resolved it."
        ),
        "fix_explanation": (
            "This rule is informational only and has no auto-fix. You must manually verify the "
            "registry and switch to a trusted source."
        ),
    },
    "CA101": {
        "why_it_matters": (
            "Hardcoded secrets in compose files are the most common way credentials leak in homelab "
            "setups. If you push your compose files to GitHub or share them in forums, passwords for "
            "databases, API keys, and tokens become public. Even private repos can be compromised."
        ),
        "when_to_ignore": [
            "Truly isolated test environments with no network access and dummy data",
            "Docker-in-Docker CI pipelines where secrets are ephemeral and never persisted",
            "Values that look like secrets but are actually non-sensitive defaults (e.g., example placeholders)",
        ],
        "real_world_example": (
            "A user shared their docker-compose.yml in a Reddit troubleshooting post without redacting "
            "their Plex token and database password. Bots scraped the post within minutes. Their Plex "
            "server was accessed by strangers and their database was wiped."
        ),
        "fix_explanation": (
            "The auto-fix extracts hardcoded secrets into environment variable references (${VAR_NAME}) "
            "and generates a .env file with the original values. The .env file should be added to .gitignore."
        ),
    },
    "CA201": {
        "why_it_matters": (
            "Without healthchecks, Docker only knows if a container process is running, not if the "
            "application inside is functional. In an arr stack, a hung Sonarr instance still shows as "
            "'running' while silently failing to grab new episodes. Healthchecks enable automatic recovery."
        ),
        "when_to_ignore": [
            "Sidecar containers that are expected to exit after completing a task",
            "Containers managed by an external orchestrator that performs its own health monitoring",
            "Init containers or migration runners that should run once and stop",
        ],
        "real_world_example": (
            "A Radarr container had a database lock issue and stopped responding to API requests, but "
            "the process stayed alive. Without a healthcheck, Docker reported it as healthy for two weeks. "
            "The user missed dozens of movie releases before noticing. A simple HTTP healthcheck would have "
            "triggered a restart within minutes."
        ),
        "fix_explanation": (
            "The auto-fix adds an appropriate healthcheck based on the detected service type. For *arr "
            "services it uses the /api/health endpoint; for web services it uses a TCP or HTTP check."
        ),
    },
    "CA202": {
        "why_it_matters": (
            "A disabled or no-op healthcheck (NONE or 'exit 0') is worse than no healthcheck at all "
            "because it actively reports the service as healthy when it might not be. Other services "
            "using depends_on with condition: service_healthy will proceed based on a lie."
        ),
        "when_to_ignore": [
            "Overriding a Dockerfile healthcheck that is known to be broken or inappropriate",
            "Temporary debugging where you need to keep a failing container running",
        ],
        "real_world_example": (
            "A user copied a compose template that had 'test: exit 0' as a healthcheck placeholder. "
            "Their Postgres container was set with depends_on: condition: service_healthy. Postgres "
            "crashed on startup due to a config error, but the fake healthcheck said it was fine. "
            "The app service started and immediately failed with connection refused errors."
        ),
        "fix_explanation": (
            "The auto-fix replaces the no-op healthcheck with a real check appropriate for the "
            "detected service type. For unknown services, it suggests a TCP connectivity check."
        ),
    },
    "CA203": {
        "why_it_matters": (
            "Homelab servers often run unattended for weeks or months. Without a restart policy, any "
            "container that crashes or any host reboot leaves your services down until you manually "
            "intervene. For media automation, this means missed downloads and broken monitoring."
        ),
        "when_to_ignore": [
            "One-shot utility containers that should run once and exit (backup scripts, migrations)",
            "Development containers you want to stay stopped after manual docker stop",
            "Containers managed by an external process manager like systemd",
        ],
        "real_world_example": (
            "A homelab user went on vacation for two weeks. A power blip rebooted the server on day 2. "
            "Without restart policies, all 15 containers stayed down. Sonarr, Radarr, Plex, and all "
            "download clients were offline for 12 days. Adding 'restart: unless-stopped' to every "
            "service prevented this from happening again."
        ),
        "fix_explanation": (
            "The auto-fix adds 'restart: unless-stopped' to services missing a restart policy. This "
            "is the recommended default for homelab services — it auto-restarts on crashes and reboots "
            "but respects manual stops."
        ),
    },
    "CA301": {
        "why_it_matters": (
            "Port conflicts are one of the most common issues in homelab Docker setups. When two "
            "services bind to the same host port, the second one fails silently or crashes on startup. "
            "This is especially tricky when services are spread across multiple compose files."
        ),
        "when_to_ignore": [
            "Services that intentionally share a port via a reverse proxy (only one binds the host port)",
            "Containers using network_mode: service: that share the same network namespace",
            "Services bound to different host IPs on the same port (e.g., 127.0.0.1:80 vs 192.168.1.5:80)",
        ],
        "real_world_example": (
            "A user added Overseerr (port 5055) alongside an existing Ombi instance (also port 5055). "
            "Overseerr failed to start with a cryptic bind error. Changing Overseerr's host port to "
            "5056 while keeping the container port at 5055 fixed the conflict immediately."
        ),
        "fix_explanation": (
            "The auto-fix detects the conflict and suggests an alternative host port by incrementing "
            "the conflicting port number. It preserves the container port mapping."
        ),
    },
    "CA302": {
        "why_it_matters": (
            "A depends_on relationship only controls startup order, not network connectivity. If the "
            "dependent service and its dependency are on incompatible networks, the service will start "
            "but fail to connect at runtime, producing confusing timeout errors."
        ),
        "when_to_ignore": [
            "Services that communicate through shared volumes rather than network connections",
            "Dependencies that only need to run (not be reachable) before the dependent service starts",
        ],
        "real_world_example": (
            "A user configured Sonarr to depend on a Postgres database, but Sonarr used network_mode: host "
            "while Postgres was on a custom bridge network. Sonarr started after Postgres but could never "
            "connect to it. Moving both to the same bridge network or using host mode for both fixed it."
        ),
        "fix_explanation": (
            "This rule is informational only. You must manually ensure dependent services share at "
            "least one common network or use compatible network modes."
        ),
    },
    "CA401": {
        "why_it_matters": (
            "PUID/PGID consistency is critical for arr stacks where multiple services read and write "
            "to shared media directories. If Sonarr runs as UID 1000 but SABnzbd runs as UID 0, files "
            "created by SABnzbd may be unreadable by Sonarr, breaking imports and hardlinks."
        ),
        "when_to_ignore": [
            "Services that never share files with other containers",
            "Containers using named volumes with no cross-service file access",
            "Services that run their own internal user mapping (e.g., databases)",
        ],
        "real_world_example": (
            "A user had Radarr (PUID=1000) and qBittorrent (PUID=0) sharing a /data mount. Every "
            "movie import failed with 'permission denied' because qBittorrent created files as root. "
            "Setting both services to PUID=1000 and PGID=1000 fixed all import issues instantly."
        ),
        "fix_explanation": (
            "The auto-fix identifies the most common PUID/PGID values across services and normalizes "
            "all services to match. It defaults to 1000:1000 if no majority value exists."
        ),
    },
    "CA402": {
        "why_it_matters": (
            "UMASK controls the default permissions of newly created files. Inconsistent UMASK values "
            "mean some services create group-readable files while others create private files. This "
            "causes silent permission failures when services share directories."
        ),
        "when_to_ignore": [
            "Services that only read files and never create new ones",
            "Isolated services with their own dedicated volumes",
            "Security-sensitive services that intentionally use restrictive permissions",
        ],
        "real_world_example": (
            "A user set UMASK=077 on their download client for security but left UMASK=002 on Sonarr. "
            "Downloads completed successfully but Sonarr could not read the downloaded files to import "
            "them. Standardizing UMASK=002 across all arr services fixed the issue."
        ),
        "fix_explanation": (
            "The auto-fix normalizes UMASK to 002 (group-writable) across all services that share "
            "volumes. This is the TRaSH Guides recommended value for arr stacks."
        ),
    },
    "CA403": {
        "why_it_matters": (
            "Containers without an explicit TZ variable default to UTC. In a homelab, this means "
            "scheduled searches, backups, and log timestamps are offset from your local time. This "
            "makes debugging harder and can cause tasks to run during peak usage hours."
        ),
        "when_to_ignore": [
            "Globally stateless services that never log timestamps or run scheduled tasks",
            "Services running in environments where UTC is the standard (cloud deployments, multi-region setups)",
        ],
        "real_world_example": (
            "A user in Australia (UTC+10) noticed Sonarr's RSS sync running at 2pm instead of 4am. "
            "Without TZ set, Sonarr used UTC, so the 4am schedule actually ran at 4am UTC (2pm local). "
            "Adding TZ=Australia/Sydney to all services aligned schedules with local time."
        ),
        "fix_explanation": (
            "The auto-fix adds TZ=${TZ} to services missing a timezone, referencing a .env file variable. "
            "If a .env file exists, it checks for an existing TZ value; otherwise it prompts you to set one."
        ),
    },
    "CA404": {
        "why_it_matters": (
            "Duplicate environment variables in Docker Compose are silently resolved by using the last "
            "value. This makes it easy to accidentally override a critical setting without realizing it, "
            "especially after copy-pasting configuration blocks."
        ),
        "when_to_ignore": [
            "There is no valid reason to have duplicate environment variables — this is always a bug",
        ],
        "real_world_example": (
            "A user debugging a database connection added DB_HOST=localhost at the bottom of their "
            "environment list, forgetting the original DB_HOST=postgres higher up. The service silently "
            "used localhost, which pointed to the container itself, not the database."
        ),
        "fix_explanation": (
            "The auto-fix removes duplicate entries and keeps the last occurrence, since that is what "
            "Docker would use anyway. It logs a warning about which values were removed."
        ),
    },
    "CA501": {
        "why_it_matters": (
            "Without memory limits, a single container can consume all host RAM, triggering the Linux "
            "OOM killer. In a homelab, this often kills critical services like databases or causes the "
            "entire Docker daemon to crash, taking down every container."
        ),
        "when_to_ignore": [
            "Single-container hosts where the container is the only workload",
            "Containers that need dynamic memory (e.g., Java apps with -Xmx already configured internally)",
            "Environments using cgroup-based memory management at the system level",
        ],
        "real_world_example": (
            "A Plex server performing a library scan with thousands of movies spiked to 8GB of RAM on a "
            "16GB host. The OOM killer chose to terminate the Postgres container running Authentik, "
            "locking the user out of all SSO-protected services. A 4GB memory limit on Plex would have "
            "throttled the scan instead."
        ),
        "fix_explanation": (
            "The auto-fix adds a deploy.resources.limits.memory value based on typical usage for the "
            "detected service type. You should tune these values based on your actual usage patterns."
        ),
    },
    "CA502": {
        "why_it_matters": (
            "CPU-intensive operations like media transcoding or archive extraction can starve other "
            "services of CPU time. In a homelab running multiple arr services, an unbounded transcode "
            "in Plex can make Sonarr and Radarr unresponsive for the duration."
        ),
        "when_to_ignore": [
            "Single-purpose servers dedicated to one CPU-intensive workload",
            "Services using hardware acceleration (GPU) where CPU usage is minimal",
            "Systems with abundant CPU headroom where contention is not a concern",
        ],
        "real_world_example": (
            "A user's qBittorrent client was extracting a large RAR archive, pegging all 4 CPU cores "
            "at 100%. During this time, Sonarr's API became unresponsive and Overseerr showed timeouts. "
            "Setting qBittorrent's CPU limit to 2.0 cores left headroom for other services."
        ),
        "fix_explanation": (
            "The auto-fix adds a deploy.resources.limits.cpus value based on typical CPU needs for the "
            "detected service type. Media servers get more cores; lightweight services get fractions."
        ),
    },
    "CA503": {
        "why_it_matters": (
            "Resource limits that are wildly out of range for a service type waste resources or cause "
            "crashes. Giving Nginx 4GB of RAM wastes memory other containers need, while giving Postgres "
            "64MB guarantees OOM kills under any real workload."
        ),
        "when_to_ignore": [
            "Services with known atypical resource needs (e.g., a Plex server with a huge library)",
            "Custom applications where default heuristics don't apply",
            "Testing scenarios where you intentionally stress-test with unusual limits",
        ],
        "real_world_example": (
            "A user copied resource limits from a minimal Nginx config and applied them to Jellyfin: "
            "128MB memory and 0.25 CPUs. Jellyfin OOM-crashed every time someone tried to play a video. "
            "Increasing to 2GB memory and 2.0 CPUs matched actual transcoding requirements."
        ),
        "fix_explanation": (
            "This rule flags limits that are more than 4x above or below typical values for known "
            "service types. It suggests a reasonable range but does not auto-fix."
        ),
    },
    "CA504": {
        "why_it_matters": (
            "Docker's default json-file log driver has no rotation. Every log line is appended forever. "
            "In a homelab running chatty services like download clients, logs can consume tens of "
            "gigabytes, eventually filling the disk and crashing all containers."
        ),
        "when_to_ignore": [
            "Systems using a centralized log driver (syslog, journald, fluentd) configured at the daemon level",
            "Containers with logging configured in the Docker daemon.json globally",
            "Short-lived containers that are removed after each run",
        ],
        "real_world_example": (
            "A user's 500GB SSD filled up after three months. Investigation revealed that qBittorrent's "
            "container log file was 180GB due to verbose tracker announcements logged every minute. Adding "
            "log rotation with max-size: 10m and max-file: 3 capped total log usage at 30MB per service."
        ),
        "fix_explanation": (
            "The auto-fix adds a logging block with json-file driver, max-size of 10m, and max-file of 3. "
            "This caps each service's logs at approximately 30MB total."
        ),
    },
    "CA505": {
        "why_it_matters": (
            "Configuring a log driver without rotation limits gives a false sense of security. The logging "
            "section exists but logs still grow unbounded. Both max-size and max-file options must be "
            "present for rotation to actually function."
        ),
        "when_to_ignore": [
            "When using a log driver that handles rotation externally (e.g., syslog with logrotate)",
            "When max-size/max-file are set at the Docker daemon level and not needed per-container",
        ],
        "real_world_example": (
            "A user added a logging section with driver: json-file but forgot the options block. They "
            "assumed logs were being rotated. Six months later, docker system df showed 50GB of logs. "
            "Adding max-size and max-file options immediately enabled rotation on the next container restart."
        ),
        "fix_explanation": (
            "The auto-fix adds the missing max-size and/or max-file options to the existing logging "
            "configuration. Defaults are max-size: 10m and max-file: 3."
        ),
    },
    "CA601": {
        "why_it_matters": (
            "Hardlinks only work within a single filesystem. If your arr services and download clients "
            "mount different host paths, Docker creates separate filesystem boundaries and hardlinks "
            "become impossible. Imports fall back to slow copy+delete, doubling disk usage."
        ),
        "when_to_ignore": [
            "Services that don't share files (e.g., a standalone database)",
            "Setups intentionally using separate storage pools for downloads and media",
            "Environments where disk space is not a concern and copy behavior is acceptable",
        ],
        "real_world_example": (
            "A user had Sonarr mounting /mnt/tv:/tv and qBittorrent mounting /mnt/downloads:/downloads. "
            "Every episode import took 2-3 minutes and consumed double the disk space because hardlinks "
            "couldn't cross mount boundaries. Switching both to /mnt/data:/data with subdirectories "
            "made imports instant and eliminated the duplicate storage."
        ),
        "fix_explanation": (
            "The auto-fix suggests a unified /data mount structure following the TRaSH Guides layout. "
            "It identifies services that should share mounts and recommends path consolidation."
        ),
    },
    "CA602": {
        "why_it_matters": (
            "Services sharing a /data or /media mount must use consistent internal paths for hardlinks "
            "to work. If one service sees /data/downloads and another sees /downloads, the filesystem "
            "paths don't match even though the underlying storage is the same."
        ),
        "when_to_ignore": [
            "Services that don't participate in the download-import pipeline",
            "Read-only mounts where the service only consumes data",
        ],
        "real_world_example": (
            "A user correctly shared a single /data host directory but mounted it as /data in Sonarr "
            "and /media in qBittorrent. Sonarr tried to hardlink from /data/downloads but qBittorrent "
            "wrote to /media/downloads. The paths didn't match, so Docker fell back to copying."
        ),
        "fix_explanation": (
            "This rule checks for consistent mount points across services that share volumes. "
            "It does not auto-fix but highlights mismatched paths for manual correction."
        ),
    },
    "CA603": {
        "why_it_matters": (
            "Read-only volume mounts (:ro) prevent containers from writing to shared directories. If a "
            "download client's output directory is mounted read-only, it cannot save completed downloads. "
            "Conversely, mounting config directories as read-write when read-only suffices increases risk."
        ),
        "when_to_ignore": [
            "Intentionally read-only mounts for config files that should not be modified by the container",
            "Services that genuinely only need read access to shared media libraries",
        ],
        "real_world_example": (
            "A user mounted /data:/data:ro on their SABnzbd container for safety. Downloads appeared to "
            "start but failed at 100% because SABnzbd could not write the completed files. Removing the "
            ":ro flag for the downloads subdirectory fixed the issue."
        ),
        "fix_explanation": (
            "This rule flags potentially incorrect read-only mounts on directories that typically need "
            "write access. It does not auto-fix to avoid unintended permission changes."
        ),
    },
    "CA701": {
        "why_it_matters": (
            "Bind mounts couple your compose file to a specific host directory layout. Named volumes "
            "are managed by Docker, making backups easier and the stack more portable across machines. "
            "However, for arr stacks, bind mounts to a unified /data directory are often preferred."
        ),
        "when_to_ignore": [
            "Arr stack media directories where bind mounts to a unified path are the recommended approach",
            "Configuration files you need to edit directly on the host",
            "Development environments where you need live code reloading",
        ],
        "real_world_example": (
            "A user migrating their homelab to a new server had to manually recreate 20 different "
            "directory paths because every service used bind mounts to unique host paths. Named volumes "
            "for application data (configs, databases) would have made the migration a simple volume "
            "backup and restore."
        ),
        "fix_explanation": (
            "This rule is informational. It suggests converting application data bind mounts to named "
            "volumes while keeping media/data bind mounts that follow the TRaSH Guides structure."
        ),
    },
    "CA702": {
        "why_it_matters": (
            "Referencing a named volume in a service without defining it in the top-level volumes section "
            "creates an anonymous volume. Anonymous volumes have random names, are not visible in docker "
            "volume ls by a recognizable name, and may be pruned unexpectedly."
        ),
        "when_to_ignore": [
            "Volumes defined in an external compose file using extends or include",
            "Volumes created externally and referenced with external: true (must still be declared)",
        ],
        "real_world_example": (
            "A user typo'd 'sonar_config' instead of 'sonarr_config' in their service definition. Docker "
            "created an anonymous volume, so Sonarr started fresh with no configuration. The user spent "
            "hours reconfiguring before realizing the old data was in the correctly-named volume."
        ),
        "fix_explanation": (
            "The auto-fix adds missing volume definitions to the top-level volumes section with default "
            "driver settings. It preserves any existing volume configuration."
        ),
    },
    "CA801": {
        "why_it_matters": (
            "Linux capabilities grant specific kernel-level permissions to containers. The default set "
            "includes capabilities most services never need, like NET_RAW (packet sniffing). Dropping "
            "all and adding back only required capabilities limits blast radius if a container is compromised."
        ),
        "when_to_ignore": [
            "Containers that need broad capabilities (VPN clients, network tools)",
            "Debugging scenarios where you need to run diagnostic tools inside a container",
            "Legacy applications that fail with reduced capabilities and cannot be modified",
        ],
        "real_world_example": (
            "A vulnerability in a web application allowed remote code execution inside the container. "
            "Because NET_RAW was available (Docker default), the attacker could ARP spoof other containers "
            "on the bridge network and intercept database traffic. Dropping all capabilities except "
            "NET_BIND_SERVICE would have blocked this lateral movement."
        ),
        "fix_explanation": (
            "The auto-fix adds 'cap_drop: [ALL]' to services missing it. For services that need specific "
            "capabilities (VPN, DNS), it also adds the minimum required cap_add entries."
        ),
    },
    "CA802": {
        "why_it_matters": (
            "Privileged mode is equivalent to running as root on the host with no restrictions. A single "
            "container escape vulnerability gives an attacker complete control of your server, all other "
            "containers, and all data. It should almost never be used."
        ),
        "when_to_ignore": [
            "Docker-in-Docker setups that genuinely require host-level access",
            "Hardware passthrough scenarios where specific device access is insufficient",
            "System-level tools like Portainer agent that need full host visibility",
        ],
        "real_world_example": (
            "A user set privileged: true on their media server to fix a GPU passthrough issue. A later "
            "vulnerability in the media server's web interface allowed an attacker to mount the host "
            "filesystem, read SSH keys, and gain persistent access to the server. Using specific device "
            "passthrough instead of privileged mode would have contained the breach."
        ),
        "fix_explanation": (
            "The auto-fix removes privileged: true and suggests specific cap_add and device entries "
            "based on the detected service type. For GPU passthrough, it adds the appropriate device mapping."
        ),
    },
    "CA803": {
        "why_it_matters": (
            "A read-only root filesystem prevents attackers from writing malicious binaries, modifying "
            "configs, or planting backdoors inside the container. Most services only need to write to "
            "specific directories, which can be mounted as tmpfs or named volumes."
        ),
        "when_to_ignore": [
            "Applications that write to unpredictable filesystem locations",
            "Arr services (Sonarr, Radarr) that write to multiple internal directories — use with caution",
            "Containers where identifying all writable paths would be impractical",
        ],
        "real_world_example": (
            "An attacker exploited a path traversal vulnerability in a web application to write a reverse "
            "shell script to /tmp and execute it. With read_only: true and a size-limited tmpfs on /tmp, "
            "the write would have either failed or been constrained to a small tmpfs that is cleared on restart."
        ),
        "fix_explanation": (
            "The auto-fix adds read_only: true and suggests tmpfs mounts for common writable directories "
            "(/tmp, /var/run, /var/cache) based on the detected service type."
        ),
    },
    "CA804": {
        "why_it_matters": (
            "The no-new-privileges flag blocks privilege escalation via setuid/setgid binaries inside the "
            "container. This is a low-cost, high-impact security measure that breaks almost nothing while "
            "closing a common attack vector used in container escape chains."
        ),
        "when_to_ignore": [
            "Containers that use su or sudo internally to switch users at runtime",
            "Services that rely on setuid binaries for specific operations (e.g., ping, crontab)",
            "Legacy init systems inside containers that need privilege transitions",
        ],
        "real_world_example": (
            "An attacker gained code execution as a non-root user inside a container. They found a setuid "
            "root binary (/usr/bin/newgrp) and used it to escalate to root inside the container. From root "
            "in the container, they exploited a kernel vulnerability to escape to the host. The "
            "no-new-privileges flag would have blocked the first escalation step."
        ),
        "fix_explanation": (
            "The auto-fix adds 'security_opt: [\"no-new-privileges:true\"]' to services missing it. "
            "This is safe for the vast majority of containerized applications."
        ),
    },
    "CA901": {
        "why_it_matters": (
            "Resource reservations guarantee minimum resources; limits cap the maximum. Having one without "
            "the other creates imbalanced scheduling. Reservations without limits allow runaway usage; "
            "limits without reservations mean the container may be evicted under memory pressure."
        ),
        "when_to_ignore": [
            "Simple homelab setups where you only want to set limits and don't need guaranteed minimums",
            "Single-container hosts where reservation vs. limit distinction is irrelevant",
            "Swarm/Kubernetes environments where scheduling policies handle resource guarantees differently",
        ],
        "real_world_example": (
            "A user set memory reservations of 1GB on their Postgres container but no limit. During a "
            "large query, Postgres consumed 6GB of the host's 8GB RAM, OOM-killing other containers. "
            "Adding a 2GB limit alongside the 1GB reservation ensured Postgres got at least 1GB but "
            "could never consume more than 2GB."
        ),
        "fix_explanation": (
            "The auto-fix adds the missing counterpart: if only reservations exist, it adds limits at "
            "2x the reservation value. If only limits exist, it adds reservations at 50% of the limit."
        ),
    },
    "CA902": {
        "why_it_matters": (
            "The 'always' restart policy restarts containers even after manual stops and during crash "
            "loops. A misconfigured container with restart: always will restart thousands of times per "
            "hour, filling logs and consuming resources. Use 'unless-stopped' instead."
        ),
        "when_to_ignore": [
            "Services that must absolutely never stay stopped (critical infrastructure monitoring)",
            "Containers managed by an orchestrator that handles restart logic externally",
        ],
        "real_world_example": (
            "A user set restart: always on a container with a broken config. The container crashed on "
            "startup every time, restarting hundreds of times per minute. Docker logs grew by gigabytes "
            "per hour and the constant restarts consumed enough CPU to slow down other services. Changing "
            "to unless-stopped and using docker stop allowed them to debug in peace."
        ),
        "fix_explanation": (
            "The auto-fix replaces 'restart: always' with 'restart: unless-stopped'. This preserves "
            "auto-restart on crashes and reboots while respecting manual docker stop commands."
        ),
    },
    "CA903": {
        "why_it_matters": (
            "Tmpfs mounts store data in RAM. Without a size limit, a process writing to tmpfs can "
            "consume all available memory, potentially OOM-killing the container or other services on "
            "the host. Always specify a size limit for predictable memory usage."
        ),
        "when_to_ignore": [
            "Tmpfs mounts for tiny files (PID files, sockets) where the practical risk is negligible",
            "Systems with abundant RAM where tmpfs usage is monitored externally",
        ],
        "real_world_example": (
            "A container used an unbounded tmpfs at /tmp for temporary file processing. A bug caused it "
            "to write a 12GB temp file to /tmp, which went directly to RAM. The host ran out of memory "
            "and the OOM killer terminated the database container. Adding size=100M to the tmpfs mount "
            "would have caused a 'no space left on device' error instead — a much safer failure mode."
        ),
        "fix_explanation": (
            "The auto-fix adds a size limit to tmpfs mounts. The default is 100M for /tmp and /var/run, "
            "adjustable based on the service's known requirements."
        ),
    },
    "CA904": {
        "why_it_matters": (
            "By default, UID 0 (root) inside a container maps to UID 0 on the host. A container escape "
            "as root gives full host access. User namespace remapping maps container root to an "
            "unprivileged host UID, adding a critical security boundary."
        ),
        "when_to_ignore": [
            "Containers that need direct host UID mapping for file permission compatibility (arr services with PUID/PGID)",
            "Services that require actual root access (Docker socket, system management tools)",
            "Environments where user namespace remapping is configured at the Docker daemon level",
        ],
        "real_world_example": (
            "A container running as root internally escaped through a kernel vulnerability. Because "
            "container root mapped directly to host root, the attacker immediately had full host access. "
            "With user namespace remapping, container root would have mapped to an unprivileged host UID, "
            "limiting the damage to what that unprivileged user could access."
        ),
        "fix_explanation": (
            "This rule is informational. User namespace remapping is best configured at the Docker daemon "
            "level rather than per-container. The rule suggests using 'user: 1000:1000' as an alternative."
        ),
    },
}


def get_rule_details(rule_id: str) -> dict | None:
    """Return the RULE_DETAILS entry for a rule, or None if not found."""
    return RULE_DETAILS.get(rule_id)


def render_explanation(rule_id: str, console: "Console", *, detailed: bool = False, example: bool = False) -> bool:
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

    # Extended details (detailed mode)
    details = RULE_DETAILS.get(rule_id, {})
    if detailed and details:
        from rich.padding import Padding
        from rich.text import Text

        if "why_it_matters" in details:
            console.print(f"  [bold {C_TEXT}]Why it matters (detailed)[/]")
            console.print(Padding(Text(details["why_it_matters"]), (0, 4, 0, 4)))
            console.print()

        if details.get("when_to_ignore"):
            console.print(f"  [bold {C_TEXT}]When to ignore this rule[/]")
            for item in details["when_to_ignore"]:
                console.print(f"    [{C_MUTED}]\u2022[/] [{C_TEXT}]{item}[/]")
            console.print()

        if "fix_explanation" in details:
            console.print(f"  [bold {C_TEXT}]How the auto-fix works[/]")
            console.print(Padding(Text(details["fix_explanation"]), (0, 4, 0, 4)))
            console.print()

    # Real-world example (example mode)
    if example and details.get("real_world_example"):
        from rich.padding import Padding
        from rich.text import Text

        console.print(f"  [bold {C_TEXT}]Real-world example[/]")
        console.print(Padding(Text(details["real_world_example"]), (0, 4, 0, 4)))
        console.print()

    return True
