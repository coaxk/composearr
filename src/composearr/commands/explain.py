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
