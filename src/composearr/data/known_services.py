"""Known service profiles for smart analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceProfile:
    """Profile of a known Docker service."""

    name: str
    image_patterns: list[str] = field(default_factory=list)
    service_type: str = "generic"  # arr, media, download, database, proxy, monitoring, utility
    default_port: int | None = None
    healthcheck_endpoint: str | None = None
    healthcheck_type: str = "http"  # http, tcp, cmd
    healthcheck_command: str | None = None  # For cmd type or custom checks
    typical_cpu: str = "0.5"
    typical_memory: str = "256M"
    needs_puid_pgid: bool = False
    arr_service: bool = False


# ── Known Services Database ──────────────────────────────────

KNOWN_SERVICES: dict[str, ServiceProfile] = {
    # *arr services
    "sonarr": ServiceProfile(
        name="Sonarr",
        image_patterns=["linuxserver/sonarr", "hotio/sonarr", "sonarr"],
        service_type="arr",
        default_port=8989,
        healthcheck_endpoint="/api/v3/health",
        needs_puid_pgid=True,
        arr_service=True,
    ),
    "radarr": ServiceProfile(
        name="Radarr",
        image_patterns=["linuxserver/radarr", "hotio/radarr", "radarr"],
        service_type="arr",
        default_port=7878,
        healthcheck_endpoint="/api/v3/health",
        needs_puid_pgid=True,
        arr_service=True,
    ),
    "lidarr": ServiceProfile(
        name="Lidarr",
        image_patterns=["linuxserver/lidarr", "hotio/lidarr", "lidarr"],
        service_type="arr",
        default_port=8686,
        healthcheck_endpoint="/api/v1/health",
        needs_puid_pgid=True,
        arr_service=True,
    ),
    "readarr": ServiceProfile(
        name="Readarr",
        image_patterns=["linuxserver/readarr", "hotio/readarr", "readarr"],
        service_type="arr",
        default_port=8787,
        healthcheck_endpoint="/api/v1/health",
        needs_puid_pgid=True,
        arr_service=True,
    ),
    "prowlarr": ServiceProfile(
        name="Prowlarr",
        image_patterns=["linuxserver/prowlarr", "hotio/prowlarr", "prowlarr"],
        service_type="arr",
        default_port=9696,
        healthcheck_endpoint="/api/v1/health",
        needs_puid_pgid=True,
        arr_service=True,
    ),
    "whisparr": ServiceProfile(
        name="Whisparr",
        image_patterns=["hotio/whisparr", "whisparr"],
        service_type="arr",
        default_port=6969,
        healthcheck_endpoint="/api/v3/health",
        needs_puid_pgid=True,
        arr_service=True,
    ),
    "bazarr": ServiceProfile(
        name="Bazarr",
        image_patterns=["linuxserver/bazarr", "hotio/bazarr", "bazarr"],
        service_type="arr",
        default_port=6767,
        healthcheck_endpoint="/api/system/health",
        needs_puid_pgid=True,
        arr_service=True,
    ),
    # Media servers
    "plex": ServiceProfile(
        name="Plex",
        image_patterns=["linuxserver/plex", "plexinc/pms-docker", "plex"],
        service_type="media",
        default_port=32400,
        healthcheck_endpoint="/identity",
        needs_puid_pgid=True,
    ),
    "jellyfin": ServiceProfile(
        name="Jellyfin",
        image_patterns=["linuxserver/jellyfin", "jellyfin/jellyfin", "jellyfin"],
        service_type="media",
        default_port=8096,
        healthcheck_endpoint="/health",
        needs_puid_pgid=True,
    ),
    "emby": ServiceProfile(
        name="Emby",
        image_patterns=["linuxserver/emby", "emby/embyserver", "emby"],
        service_type="media",
        default_port=8096,
        healthcheck_endpoint="/System/Ping",
        needs_puid_pgid=True,
    ),
    "tautulli": ServiceProfile(
        name="Tautulli",
        image_patterns=["linuxserver/tautulli", "tautulli/tautulli", "tautulli"],
        service_type="media",
        default_port=8181,
        healthcheck_endpoint="/status",
        needs_puid_pgid=True,
    ),
    # Request management
    "overseerr": ServiceProfile(
        name="Overseerr",
        image_patterns=["linuxserver/overseerr", "sctx/overseerr", "overseerr"],
        service_type="media",
        default_port=5055,
        healthcheck_endpoint="/api/v1/status",
    ),
    "jellyseerr": ServiceProfile(
        name="Jellyseerr",
        image_patterns=["fallenbagel/jellyseerr", "jellyseerr"],
        service_type="media",
        default_port=5055,
        healthcheck_endpoint="/api/v1/status",
    ),
    # Download clients
    "qbittorrent": ServiceProfile(
        name="qBittorrent",
        image_patterns=["linuxserver/qbittorrent", "hotio/qbittorrent", "qbittorrent"],
        service_type="download",
        default_port=8080,
        healthcheck_endpoint="/api/v2/app/version",
        needs_puid_pgid=True,
    ),
    "transmission": ServiceProfile(
        name="Transmission",
        image_patterns=["linuxserver/transmission", "transmission"],
        service_type="download",
        default_port=9091,
        healthcheck_endpoint="/transmission/web/",
        needs_puid_pgid=True,
    ),
    "deluge": ServiceProfile(
        name="Deluge",
        image_patterns=["linuxserver/deluge", "deluge"],
        service_type="download",
        default_port=8112,
        healthcheck_type="tcp",
        needs_puid_pgid=True,
    ),
    "sabnzbd": ServiceProfile(
        name="SABnzbd",
        image_patterns=["linuxserver/sabnzbd", "hotio/sabnzbd", "sabnzbd"],
        service_type="download",
        default_port=8080,
        healthcheck_endpoint="/api?mode=version",
        needs_puid_pgid=True,
    ),
    "nzbget": ServiceProfile(
        name="NZBGet",
        image_patterns=["linuxserver/nzbget", "nzbget"],
        service_type="download",
        default_port=6789,
        healthcheck_endpoint="/",
        needs_puid_pgid=True,
    ),
    # VPN / Network
    "gluetun": ServiceProfile(
        name="Gluetun",
        image_patterns=["qmcgaw/gluetun", "gluetun"],
        service_type="utility",
        default_port=8888,
        healthcheck_type="cmd",
        healthcheck_command="/gluetun-entrypoint healthcheck",
    ),
    # Reverse proxies
    "traefik": ServiceProfile(
        name="Traefik",
        image_patterns=["traefik"],
        service_type="proxy",
        default_port=8080,
        healthcheck_endpoint="/ping",
    ),
    "nginx": ServiceProfile(
        name="Nginx",
        image_patterns=["nginx", "linuxserver/nginx", "linuxserver/swag"],
        service_type="proxy",
        default_port=80,
        healthcheck_type="cmd",
        healthcheck_command="curl -sf http://localhost/ || exit 1",
    ),
    "caddy": ServiceProfile(
        name="Caddy",
        image_patterns=["caddy"],
        service_type="proxy",
        default_port=80,
        healthcheck_type="cmd",
        healthcheck_command="wget -qO- http://localhost:2019/config/ || exit 1",
    ),
    # Databases
    "postgres": ServiceProfile(
        name="PostgreSQL",
        image_patterns=["postgres", "bitnami/postgresql"],
        service_type="database",
        default_port=5432,
        healthcheck_type="cmd",
        healthcheck_command="pg_isready -U ${POSTGRES_USER:-postgres}",
        typical_memory="512M",
    ),
    "mariadb": ServiceProfile(
        name="MariaDB",
        image_patterns=["mariadb", "linuxserver/mariadb", "bitnami/mariadb"],
        service_type="database",
        default_port=3306,
        healthcheck_type="cmd",
        healthcheck_command="healthcheck.sh --connect --innodb_initialized",
        typical_memory="512M",
    ),
    "mysql": ServiceProfile(
        name="MySQL",
        image_patterns=["mysql", "bitnami/mysql"],
        service_type="database",
        default_port=3306,
        healthcheck_type="cmd",
        healthcheck_command="mysqladmin ping -h localhost",
        typical_memory="512M",
    ),
    "redis": ServiceProfile(
        name="Redis",
        image_patterns=["redis", "bitnami/redis"],
        service_type="database",
        default_port=6379,
        healthcheck_type="cmd",
        healthcheck_command="redis-cli ping | grep PONG",
        typical_memory="128M",
    ),
    "mongodb": ServiceProfile(
        name="MongoDB",
        image_patterns=["mongo", "bitnami/mongodb"],
        service_type="database",
        default_port=27017,
        healthcheck_type="cmd",
        healthcheck_command="mongosh --eval 'db.runCommand(\"ping\").ok' --quiet",
        typical_memory="512M",
    ),
    # Monitoring
    "grafana": ServiceProfile(
        name="Grafana",
        image_patterns=["grafana/grafana"],
        service_type="monitoring",
        default_port=3000,
        healthcheck_endpoint="/api/health",
    ),
    "prometheus": ServiceProfile(
        name="Prometheus",
        image_patterns=["prom/prometheus"],
        service_type="monitoring",
        default_port=9090,
        healthcheck_endpoint="/-/healthy",
    ),
    # Utility / Management
    "portainer": ServiceProfile(
        name="Portainer",
        image_patterns=["portainer/portainer-ce", "portainer/portainer"],
        service_type="utility",
        default_port=9443,
        healthcheck_endpoint="/api/system/status",
    ),
    "watchtower": ServiceProfile(
        name="Watchtower",
        image_patterns=["containrrr/watchtower"],
        service_type="utility",
        healthcheck_type="cmd",
        healthcheck_command="/watchtower --health-check",
    ),
    "homepage": ServiceProfile(
        name="Homepage",
        image_patterns=["ghcr.io/gethomepage/homepage"],
        service_type="utility",
        default_port=3000,
        healthcheck_endpoint="/api/healthcheck",
    ),
    "unmanic": ServiceProfile(
        name="Unmanic",
        image_patterns=["josh5/unmanic"],
        service_type="media",
        default_port=8888,
        healthcheck_endpoint="/unmanic/api/v2/ping",
        needs_puid_pgid=True,
    ),
    "flaresolverr": ServiceProfile(
        name="FlareSolverr",
        image_patterns=["flaresolverr/flaresolverr", "ghcr.io/flaresolverr/flaresolverr"],
        service_type="utility",
        default_port=8191,
        healthcheck_endpoint="/health",
    ),
    "recyclarr": ServiceProfile(
        name="Recyclarr",
        image_patterns=["recyclarr/recyclarr", "ghcr.io/recyclarr/recyclarr"],
        service_type="arr",
        healthcheck_type="cmd",
        healthcheck_command="recyclarr --version",
    ),
    # ── Additional *arr services ────────────────────────────────
    "mylar3": ServiceProfile(
        name="Mylar3",
        image_patterns=["linuxserver/mylar3", "hotio/mylar3", "mylar3"],
        service_type="arr",
        default_port=8090,
        healthcheck_endpoint="/",
        needs_puid_pgid=True,
        arr_service=True,
    ),
    "huntarr": ServiceProfile(
        name="Huntarr",
        image_patterns=["huntarr/huntarr", "ghcr.io/plexguide/huntarr"],
        service_type="arr",
        default_port=9705,
        healthcheck_endpoint="/",
    ),
    # ── Additional media services ───────────────────────────────
    "navidrome": ServiceProfile(
        name="Navidrome",
        image_patterns=["deluan/navidrome"],
        service_type="media",
        default_port=4533,
        healthcheck_endpoint="/api/ping",
    ),
    "audiobookshelf": ServiceProfile(
        name="Audiobookshelf",
        image_patterns=["ghcr.io/advplyr/audiobookshelf", "advplyr/audiobookshelf"],
        service_type="media",
        default_port=13378,
        healthcheck_endpoint="/healthcheck",
    ),
    "stash": ServiceProfile(
        name="Stash",
        image_patterns=["stashapp/stash"],
        service_type="media",
        default_port=9999,
        healthcheck_endpoint="/",
        needs_puid_pgid=True,
    ),
    "kavita": ServiceProfile(
        name="Kavita",
        image_patterns=["jvmilazz0/kavita", "linuxserver/kavita"],
        service_type="media",
        default_port=5000,
        healthcheck_endpoint="/api/health",
    ),
    # ── Additional download clients ─────────────────────────────
    "aria2": ServiceProfile(
        name="Aria2",
        image_patterns=["p3terx/aria2-pro", "hurlenko/aria2-ariang"],
        service_type="download",
        default_port=6800,
        healthcheck_type="tcp",
    ),
    "rtorrent": ServiceProfile(
        name="rTorrent",
        image_patterns=["crazymax/rtorrent-rutorrent", "linuxserver/rutorrent"],
        service_type="download",
        default_port=8080,
        healthcheck_type="tcp",
        needs_puid_pgid=True,
    ),
    "flood": ServiceProfile(
        name="Flood",
        image_patterns=["jesec/flood"],
        service_type="download",
        default_port=3000,
        healthcheck_endpoint="/",
    ),
    # ── Additional reverse proxies / web servers ────────────────
    "swag": ServiceProfile(
        name="SWAG",
        image_patterns=["linuxserver/swag"],
        service_type="proxy",
        default_port=443,
        healthcheck_type="cmd",
        healthcheck_command="curl -sf https://localhost/ -k || exit 1",
        needs_puid_pgid=True,
    ),
    "nginx-proxy-manager": ServiceProfile(
        name="Nginx Proxy Manager",
        image_patterns=["jc21/nginx-proxy-manager"],
        service_type="proxy",
        default_port=81,
        healthcheck_endpoint="/api/",
    ),
    "authelia": ServiceProfile(
        name="Authelia",
        image_patterns=["authelia/authelia"],
        service_type="proxy",
        default_port=9091,
        healthcheck_endpoint="/api/health",
    ),
    # ── Additional databases ────────────────────────────────────
    "influxdb": ServiceProfile(
        name="InfluxDB",
        image_patterns=["influxdb"],
        service_type="database",
        default_port=8086,
        healthcheck_endpoint="/health",
        typical_memory="512M",
    ),
    "memcached": ServiceProfile(
        name="Memcached",
        image_patterns=["memcached", "bitnami/memcached"],
        service_type="database",
        default_port=11211,
        healthcheck_type="tcp",
        typical_memory="128M",
    ),
    # ── Additional monitoring ───────────────────────────────────
    "loki": ServiceProfile(
        name="Loki",
        image_patterns=["grafana/loki"],
        service_type="monitoring",
        default_port=3100,
        healthcheck_endpoint="/ready",
    ),
    "promtail": ServiceProfile(
        name="Promtail",
        image_patterns=["grafana/promtail"],
        service_type="monitoring",
        default_port=9080,
        healthcheck_endpoint="/ready",
    ),
    "uptime-kuma": ServiceProfile(
        name="Uptime Kuma",
        image_patterns=["louislam/uptime-kuma"],
        service_type="monitoring",
        default_port=3001,
        healthcheck_endpoint="/api/status-page/heartbeat",
    ),
    "netdata": ServiceProfile(
        name="Netdata",
        image_patterns=["netdata/netdata"],
        service_type="monitoring",
        default_port=19999,
        healthcheck_endpoint="/api/v1/info",
    ),
    # ── Additional utility services ─────────────────────────────
    "dozzle": ServiceProfile(
        name="Dozzle",
        image_patterns=["amir20/dozzle"],
        service_type="utility",
        default_port=8080,
        healthcheck_endpoint="/healthcheck",
    ),
    "duplicati": ServiceProfile(
        name="Duplicati",
        image_patterns=["linuxserver/duplicati", "duplicati/duplicati"],
        service_type="utility",
        default_port=8200,
        healthcheck_type="tcp",
        needs_puid_pgid=True,
    ),
    "vaultwarden": ServiceProfile(
        name="Vaultwarden",
        image_patterns=["vaultwarden/server"],
        service_type="utility",
        default_port=80,
        healthcheck_endpoint="/alive",
    ),
    "wireguard": ServiceProfile(
        name="WireGuard",
        image_patterns=["linuxserver/wireguard"],
        service_type="utility",
        needs_puid_pgid=True,
        healthcheck_type="cmd",
        healthcheck_command="wg show | grep -q interface",
    ),
    "pihole": ServiceProfile(
        name="Pi-hole",
        image_patterns=["pihole/pihole"],
        service_type="utility",
        default_port=80,
        healthcheck_endpoint="/admin/api.php?status",
    ),
    "homeassistant": ServiceProfile(
        name="Home Assistant",
        image_patterns=["homeassistant/home-assistant", "ghcr.io/home-assistant/home-assistant"],
        service_type="utility",
        default_port=8123,
        healthcheck_endpoint="/api/",
    ),
    "cloudflared": ServiceProfile(
        name="Cloudflared",
        image_patterns=["cloudflare/cloudflared"],
        service_type="utility",
        healthcheck_type="cmd",
        healthcheck_command="cloudflared tunnel --metrics localhost:60123 2>/dev/null; curl -sf http://localhost:60123/ready || exit 1",
    ),
    "adminer": ServiceProfile(
        name="Adminer",
        image_patterns=["adminer"],
        service_type="utility",
        default_port=8080,
        healthcheck_type="tcp",
    ),
    "filebrowser": ServiceProfile(
        name="File Browser",
        image_patterns=["filebrowser/filebrowser"],
        service_type="utility",
        default_port=80,
        healthcheck_endpoint="/health",
    ),
    "code-server": ServiceProfile(
        name="code-server",
        image_patterns=["linuxserver/code-server", "codercom/code-server"],
        service_type="utility",
        default_port=8443,
        healthcheck_endpoint="/healthz",
        needs_puid_pgid=True,
    ),
}


def detect_service(image: str) -> ServiceProfile | None:
    """Match an image string to a known service profile.

    Handles registry prefixes (ghcr.io, lscr.io, docker.io, etc.) and tags.
    """
    if not image:
        return None

    # Strip tag/digest
    clean = re.split(r"[:@]", image)[0]

    # Strip common registry prefixes
    for prefix in ("docker.io/", "ghcr.io/", "lscr.io/", "cr.hotio.dev/", "registry.hub.docker.com/", "library/"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break

    clean_lower = clean.lower()

    for _key, profile in KNOWN_SERVICES.items():
        for pattern in profile.image_patterns:
            if clean_lower == pattern.lower() or clean_lower.endswith(f"/{pattern.lower()}"):
                return profile

    return None
