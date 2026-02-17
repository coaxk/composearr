#!/usr/bin/env python3
"""Generate realistic Docker Compose test stacks with intentionally seeded issues.

Creates 6 stack directories with varying sizes and issue profiles for manual QA
of ComposeArr's scan, fix, topology, and secure-secrets features.

Stacks 1-5 seed common issues (CA001, CA101, CA201, CA203, CA301, CA403).
Stack 6 (rule-showcase) adds one file per remaining rule for complete 30-rule coverage.

Run:  python testingstacks/generate.py
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).parent

# ── Helpers ──────────────────────────────────────────────────────

def write(stack: str, name: str, content: str) -> None:
    d = ROOT / stack / name
    d.parent.mkdir(parents=True, exist_ok=True)
    d.write_text(content, encoding="utf-8")
    print(f"  wrote {stack}/{name}")


# ══════════════════════════════════════════════════════════════════
# Stack 1: minimal-stack  (3 files — mostly clean, baseline)
# ══════════════════════════════════════════════════════════════════

def gen_minimal():
    s = "minimal-stack"

    # 1 — Clean nginx reverse proxy
    write(s, "nginx/compose.yaml", """\
services:
  nginx:
    image: nginx:1.27-alpine
    container_name: nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config:/etc/nginx/conf.d
      - ./certs:/etc/nginx/certs
    environment:
      TZ: America/New_York
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost"]
      interval: 30s
      timeout: 5s
      retries: 3

networks:
  default:
    name: proxy-net
""")

    # 2 — Portainer with missing TZ (CA403) and :latest tag (CA001)
    write(s, "portainer/compose.yaml", """\
services:
  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer
    restart: unless-stopped
    ports:
      - "9000:9000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
    # NOTE: missing TZ — CA403

volumes:
  portainer_data:
""")

    # 3 — Uptime Kuma, clean
    write(s, "uptime-kuma/compose.yaml", """\
services:
  uptime-kuma:
    image: louislam/uptime-kuma:1.23.13
    container_name: uptime-kuma
    restart: unless-stopped
    ports:
      - "3001:3001"
    volumes:
      - ./data:/app/data
    environment:
      TZ: America/New_York
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3001"]
      interval: 60s
      timeout: 10s
      retries: 3
""")


# ══════════════════════════════════════════════════════════════════
# Stack 2: arr-stack  (7 files — classic *arr, secrets & TZ issues)
# ══════════════════════════════════════════════════════════════════

def gen_arr():
    s = "arr-stack"

    # 1 — Sonarr with hardcoded API key (CA101) and missing healthcheck (CA201)
    write(s, "sonarr/compose.yaml", """\
services:
  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
    container_name: sonarr
    restart: unless-stopped
    ports:
      - "8989:8989"
    volumes:
      - ./config:/config
      - /data/media:/data/media
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
      - SONARR__AUTH__APIKEY=a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4

networks:
  default:
    name: arr-net
""")

    # 2 — Radarr with hardcoded secret and :latest tag
    write(s, "radarr/compose.yaml", """\
services:
  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: radarr
    restart: unless-stopped
    ports:
      - "7878:7878"
    volumes:
      - ./config:/config
      - /data/media:/data/media
    environment:
      PUID: 1000
      PGID: 1000
      TZ: America/New_York
      RADARR__AUTH__APIKEY: f9e8d7c6b5a4f9e8d7c6b5a4f9e8d7c6

networks:
  default:
    name: arr-net
""")

    # 3 — Prowlarr — missing restart (CA203), hardcoded secret
    write(s, "prowlarr/compose.yaml", """\
services:
  prowlarr:
    image: lscr.io/linuxserver/prowlarr:develop
    container_name: prowlarr
    ports:
      - "9696:9696"
    volumes:
      - ./config:/config
    environment:
      PUID: 1000
      PGID: 1000
      TZ: America/New_York
      PROWLARR__AUTH__APIKEY: 12345678901234567890123456789012

networks:
  default:
    name: arr-net
""")

    # 4 — Bazarr — missing TZ (CA403)
    write(s, "bazarr/compose.yaml", """\
services:
  bazarr:
    image: lscr.io/linuxserver/bazarr:latest
    container_name: bazarr
    restart: unless-stopped
    ports:
      - "6767:6767"
    volumes:
      - ./config:/config
      - /data/media:/data/media
    environment:
      PUID: 1000
      PGID: 1000
      # Missing TZ!

networks:
  default:
    name: arr-net
""")

    # 5 — Overseerr — hardcoded API_KEY, no healthcheck
    write(s, "overseerr/compose.yaml", """\
services:
  overseerr:
    image: sctx/overseerr
    container_name: overseerr
    restart: unless-stopped
    ports:
      - "5055:5055"
    volumes:
      - ./config:/app/config
    environment:
      TZ: America/New_York
      API_KEY: supersecretapikey12345

networks:
  default:
    name: arr-net
""")

    # 6 — qBittorrent — hardcoded webui password
    write(s, "qbittorrent/compose.yaml", """\
services:
  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    restart: unless-stopped
    ports:
      - "8080:8080"
      - "6881:6881"
      - "6881:6881/udp"
    volumes:
      - ./config:/config
      - /data/torrents:/data/torrents
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
      - WEBUI_PORT=8080

networks:
  default:
    name: arr-net
""")

    # 7 — Flaresolverr — no restart, no TZ, no healthcheck
    write(s, "flaresolverr/compose.yaml", """\
services:
  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    ports:
      - "8191:8191"
    environment:
      LOG_LEVEL: info

networks:
  default:
    name: arr-net
""")


# ══════════════════════════════════════════════════════════════════
# Stack 3: media-server  (12 files — ports, tags, networks)
# ══════════════════════════════════════════════════════════════════

def gen_media():
    s = "media-server"

    # 1 — Plex (host network mode)
    write(s, "plex/compose.yaml", """\
services:
  plex:
    image: lscr.io/linuxserver/plex:latest
    container_name: plex
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./config:/config
      - /data/media/movies:/movies
      - /data/media/tv:/tv
    environment:
      PUID: 1000
      PGID: 1000
      TZ: America/New_York
      PLEX_CLAIM: claim-xxxxxxxxxxxxxxxxxx
      VERSION: docker
""")

    # 2 — Jellyfin with GPU passthrough
    write(s, "jellyfin/compose.yaml", """\
services:
  jellyfin:
    image: jellyfin/jellyfin:latest
    container_name: jellyfin
    restart: unless-stopped
    ports:
      - "8096:8096"
    volumes:
      - ./config:/config
      - ./cache:/cache
      - /data/media:/media
    environment:
      TZ: America/New_York
    devices:
      - /dev/dri:/dev/dri
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

networks:
  default:
    name: media-net
""")

    # 3 — Tautulli — port conflict with something else
    write(s, "tautulli/compose.yaml", """\
services:
  tautulli:
    image: lscr.io/linuxserver/tautulli
    container_name: tautulli
    restart: unless-stopped
    ports:
      - "8181:8181"
    volumes:
      - ./config:/config
    environment:
      PUID: 1000
      PGID: 1000
      TZ: America/New_York

networks:
  default:
    name: media-net
""")

    # 4 — SABnzbd — missing TZ, missing restart
    write(s, "sabnzbd/compose.yaml", """\
services:
  sabnzbd:
    image: lscr.io/linuxserver/sabnzbd:latest
    container_name: sabnzbd
    ports:
      - "8080:8080"
    volumes:
      - ./config:/config
      - /data/usenet:/data/usenet
    environment:
      PUID: 1000
      PGID: 1000
""")

    # 5 — Transmission — hardcoded password, port conflict with sabnzbd 8080
    write(s, "transmission/compose.yaml", """\
services:
  transmission:
    image: lscr.io/linuxserver/transmission:latest
    container_name: transmission
    restart: unless-stopped
    ports:
      - "9091:9091"
      - "51413:51413"
      - "51413:51413/udp"
    volumes:
      - ./config:/config
      - /data/torrents:/data/torrents
    environment:
      PUID: 1000
      PGID: 1000
      TZ: America/New_York
      USER: admin
      PASS: MySecretPassword123!

networks:
  default:
    name: media-net
""")

    # 6 — Requestrr — missing restart, TZ
    write(s, "requestrr/compose.yaml", """\
services:
  requestrr:
    image: thomst08/requestrr:latest
    container_name: requestrr
    ports:
      - "4545:4545"
    volumes:
      - ./config:/root/config
    environment:
      - PUID=1000
      - PGID=1000
""")

    # 7 — Notifiarr — hardcoded API key
    write(s, "notifiarr/compose.yaml", """\
services:
  notifiarr:
    image: golift/notifiarr:latest
    container_name: notifiarr
    restart: unless-stopped
    ports:
      - "5454:5454"
    volumes:
      - ./config:/config
    environment:
      TZ: America/New_York
      DN_API_KEY: abcdef1234567890abcdef1234567890
      DN_SONARR_0_URL: http://sonarr:8989
      DN_SONARR_0_API_KEY: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
      DN_RADARR_0_URL: http://radarr:7878
      DN_RADARR_0_API_KEY: f9e8d7c6b5a4f9e8d7c6b5a4f9e8d7c6

networks:
  default:
    name: media-net
""")

    # 8 — Organizr — no tag (just image name)
    write(s, "organizr/compose.yaml", """\
services:
  organizr:
    image: organizr/organizr
    container_name: organizr
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./config:/config
    environment:
      TZ: America/New_York
      PUID: 1000
      PGID: 1000
""")

    # 9 — Lidarr
    write(s, "lidarr/compose.yaml", """\
services:
  lidarr:
    image: lscr.io/linuxserver/lidarr:latest
    container_name: lidarr
    restart: unless-stopped
    ports:
      - "8686:8686"
    volumes:
      - ./config:/config
      - /data/media/music:/music
      - /data/torrents:/downloads
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
""")

    # 10 — Readarr — missing restart, missing TZ
    write(s, "readarr/compose.yaml", """\
services:
  readarr:
    image: lscr.io/linuxserver/readarr:develop
    container_name: readarr
    ports:
      - "8787:8787"
    volumes:
      - ./config:/config
      - /data/media/books:/books
    environment:
      PUID: 1000
      PGID: 1000
""")

    # 11 — Recyclarr (runs once, no ports)
    write(s, "recyclarr/compose.yaml", """\
services:
  recyclarr:
    image: ghcr.io/recyclarr/recyclarr
    container_name: recyclarr
    restart: unless-stopped
    volumes:
      - ./config:/config
    environment:
      TZ: America/New_York
      CRON_SCHEDULE: "0 */6 * * *"
      RECYCLARR_CREATE_CONFIG: "true"
""")

    # 12 — Homepage dashboard — depends_on multiple services
    write(s, "homepage/compose.yaml", """\
services:
  homepage:
    image: ghcr.io/gethomepage/homepage:latest
    container_name: homepage
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - ./config:/app/config
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      TZ: America/New_York
      HOMEPAGE_VAR_PLEX_TOKEN: myplextokensupersecret123456
      HOMEPAGE_VAR_SONARR_KEY: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
""")


# ══════════════════════════════════════════════════════════════════
# Stack 4: full-homelab  (22 files — everything)
# ══════════════════════════════════════════════════════════════════

def gen_homelab():
    s = "full-homelab"

    # ── Networking & DNS ──

    write(s, "traefik/compose.yaml", """\
services:
  traefik:
    image: traefik:v3.1
    container_name: traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - ./config/traefik.yml:/traefik.yml:ro
      - ./config/acme.json:/acme.json
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      TZ: America/Chicago
      CF_API_EMAIL: admin@example.com
      CF_DNS_API_TOKEN: abc123def456ghi789jkl012mno345pqr
    networks:
      - proxy

networks:
  proxy:
    name: proxy
""")

    write(s, "pihole/compose.yaml", """\
services:
  pihole:
    image: pihole/pihole:latest
    container_name: pihole
    restart: unless-stopped
    ports:
      - "53:53/tcp"
      - "53:53/udp"
      - "8053:80"
    volumes:
      - ./etc-pihole:/etc/pihole
      - ./etc-dnsmasq.d:/etc/dnsmasq.d
    environment:
      TZ: America/Chicago
      WEBPASSWORD: MyPiholePassword123
      DNSSEC: "true"
    cap_add:
      - NET_ADMIN
""")

    write(s, "wireguard/compose.yaml", """\
services:
  wireguard:
    image: lscr.io/linuxserver/wireguard:latest
    container_name: wireguard
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    ports:
      - "51820:51820/udp"
    volumes:
      - ./config:/config
      - /lib/modules:/lib/modules
    environment:
      PUID: 1000
      PGID: 1000
      TZ: America/Chicago
      SERVERURL: vpn.example.com
      SERVERPORT: 51820
      PEERS: 5
      PEERDNS: auto
      INTERNAL_SUBNET: 10.13.13.0
      ALLOWEDIPS: 0.0.0.0/0
    sysctls:
      - net.ipv4.conf.all.src_valid_mark=1
""")

    # ── Monitoring ──

    write(s, "grafana/compose.yaml", """\
services:
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      TZ: America/Chicago
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: GrafanaSecretP@ss2024!
      GF_INSTALL_PLUGINS: grafana-clock-panel,grafana-simple-json-datasource
    depends_on:
      - prometheus
    networks:
      - monitoring

volumes:
  grafana_data:

networks:
  monitoring:
    name: monitoring
""")

    write(s, "prometheus/compose.yaml", """\
services:
  prometheus:
    image: prom/prometheus:v2.53.0
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./config:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=30d"
    environment:
      TZ: America/Chicago
    networks:
      - monitoring

volumes:
  prometheus_data:

networks:
  monitoring:
    name: monitoring
""")

    write(s, "node-exporter/compose.yaml", """\
services:
  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    network_mode: host
    restart: unless-stopped
    pid: host
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - "--path.procfs=/host/proc"
      - "--path.rootfs=/rootfs"
      - "--path.sysfs=/host/sys"
""")

    write(s, "cadvisor/compose.yaml", """\
services:
  cadvisor:
    image: gcr.io/cadvisor/cadvisor
    container_name: cadvisor
    restart: unless-stopped
    ports:
      - "8081:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:rw
      - /sys:/sys:ro
      - /var/lib/docker:/var/lib/docker:ro
    networks:
      - monitoring

networks:
  monitoring:
    name: monitoring
""")

    write(s, "loki/compose.yaml", """\
services:
  loki:
    image: grafana/loki:2.9.0
    container_name: loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - ./config:/etc/loki
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - monitoring

volumes:
  loki_data:

networks:
  monitoring:
    name: monitoring
""")

    write(s, "promtail/compose.yaml", """\
services:
  promtail:
    image: grafana/promtail:2.9.0
    container_name: promtail
    restart: unless-stopped
    volumes:
      - ./config:/etc/promtail
      - /var/log:/var/log:ro
    command: -config.file=/etc/promtail/config.yml
    depends_on:
      - loki
    networks:
      - monitoring

networks:
  monitoring:
    name: monitoring
""")

    # ── Databases ──

    write(s, "postgres/compose.yaml", """\
services:
  postgres:
    image: postgres:16
    container_name: postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: homelab
      POSTGRES_PASSWORD: SuperSecretDBPassword123!
      POSTGRES_DB: homelab
      TZ: America/Chicago
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U homelab"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - db

volumes:
  postgres_data:

networks:
  db:
    name: database
""")

    write(s, "redis/compose.yaml", """\
services:
  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --requirepass RedisSecretPass456!
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    networks:
      - db

volumes:
  redis_data:

networks:
  db:
    name: database
""")

    write(s, "mariadb/compose.yaml", """\
services:
  mariadb:
    image: mariadb:latest
    container_name: mariadb
    restart: unless-stopped
    ports:
      - "3306:3306"
    volumes:
      - mariadb_data:/var/lib/mysql
    environment:
      MYSQL_ROOT_PASSWORD: MariaDBRootP@ss789!
      MYSQL_DATABASE: homelab
      MYSQL_USER: homelab
      MYSQL_PASSWORD: MariaDBUserP@ss456!

volumes:
  mariadb_data:
""")

    # ── Home Automation ──

    write(s, "homeassistant/compose.yaml", """\
services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    container_name: homeassistant
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./config:/config
      - /etc/localtime:/etc/localtime:ro
    privileged: true
""")

    write(s, "mosquitto/compose.yaml", """\
services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    restart: unless-stopped
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./config:/mosquitto/config
      - mosquitto_data:/mosquitto/data
      - mosquitto_log:/mosquitto/log
    environment:
      TZ: America/Chicago

volumes:
  mosquitto_data:
  mosquitto_log:
""")

    write(s, "zigbee2mqtt/compose.yaml", """\
services:
  zigbee2mqtt:
    image: koenkk/zigbee2mqtt
    container_name: zigbee2mqtt
    restart: unless-stopped
    ports:
      - "8082:8080"
    volumes:
      - ./data:/app/data
    environment:
      TZ: America/Chicago
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    depends_on:
      - mosquitto
""")

    # ── Utilities ──

    write(s, "vaultwarden/compose.yaml", """\
services:
  vaultwarden:
    image: vaultwarden/server:latest
    container_name: vaultwarden
    restart: unless-stopped
    ports:
      - "8222:80"
    volumes:
      - vw_data:/data
    environment:
      ADMIN_TOKEN: $argon2id$v=19$m=65540,t=3,p=4$somerandomsaltvalue$hashedvalue
      DOMAIN: https://vault.example.com
      SIGNUPS_ALLOWED: "false"
      SMTP_HOST: smtp.gmail.com
      SMTP_FROM: vault@example.com
      SMTP_PORT: 587
      SMTP_SECURITY: starttls
      SMTP_USERNAME: vault@example.com
      SMTP_PASSWORD: MyGmailAppPassword123!
    networks:
      - proxy

volumes:
  vw_data:

networks:
  proxy:
    name: proxy
""")

    write(s, "watchtower/compose.yaml", """\
services:
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      TZ: America/Chicago
      WATCHTOWER_CLEANUP: "true"
      WATCHTOWER_POLL_INTERVAL: 86400
      WATCHTOWER_NOTIFICATION_URL: discord://tokenpart1/tokenpart2@channelid
""")

    write(s, "filebrowser/compose.yaml", """\
services:
  filebrowser:
    image: filebrowser/filebrowser:latest
    container_name: filebrowser
    restart: unless-stopped
    ports:
      - "8084:80"
    volumes:
      - /data:/srv
      - ./filebrowser.db:/database.db
      - ./settings.json:/.filebrowser.json
""")

    write(s, "duplicati/compose.yaml", """\
services:
  duplicati:
    image: lscr.io/linuxserver/duplicati:latest
    container_name: duplicati
    restart: unless-stopped
    ports:
      - "8200:8200"
    volumes:
      - ./config:/config
      - /data/backups:/backups
      - /data:/source
    environment:
      - PUID=1000
      - PGID=1000
""")

    write(s, "authelia/compose.yaml", """\
services:
  authelia:
    image: authelia/authelia:latest
    container_name: authelia
    restart: unless-stopped
    ports:
      - "9091:9091"
    volumes:
      - ./config:/config
    environment:
      TZ: America/Chicago
      AUTHELIA_JWT_SECRET: a-very-long-secret-jwt-key-for-authelia-1234567890
      AUTHELIA_SESSION_SECRET: another-secret-session-key-0987654321
      AUTHELIA_STORAGE_ENCRYPTION_KEY: yet-another-encryption-key-abcdef
    depends_on:
      - redis
      - postgres
    networks:
      - proxy
      - db

networks:
  proxy:
    name: proxy
  db:
    name: database
""")

    write(s, "speedtest/compose.yaml", """\
services:
  speedtest:
    image: lscr.io/linuxserver/librespeed
    container_name: speedtest
    ports:
      - "8085:80"
    environment:
      - PASSWORD=SpeedTestAdmin123
""")

    write(s, "dozzle/compose.yaml", """\
services:
  dozzle:
    image: amir20/dozzle:latest
    container_name: dozzle
    restart: unless-stopped
    ports:
      - "9999:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      DOZZLE_LEVEL: info
""")


# ══════════════════════════════════════════════════════════════════
# Stack 5: stress-test  (40 files — performance testing)
# ══════════════════════════════════════════════════════════════════

# Real project images for realistic content
STRESS_SERVICES = [
    ("adguard", "adguard/adguardhome:latest", [("3000:3000", "80:80")]),
    ("audiobookshelf", "ghcr.io/advplyr/audiobookshelf:latest", [("13378:80",)]),
    ("autobrr", "ghcr.io/autobrr/autobrr:latest", [("7474:7474",)]),
    ("blocky", "spx01/blocky:latest", [("4000:4000", "53:53/udp")]),
    ("bookstack", "lscr.io/linuxserver/bookstack", [("6875:80",)]),
    ("calibre-web", "lscr.io/linuxserver/calibre-web:latest", [("8083:8083",)]),
    ("changedetection", "ghcr.io/dgtlmoon/changedetection.io", [("5000:5000",)]),
    ("cloudflared", "cloudflare/cloudflared:latest", []),
    ("code-server", "lscr.io/linuxserver/code-server:latest", [("8443:8443",)]),
    ("crowdsec", "crowdsecurity/crowdsec:latest", [("8088:8080",)]),
    ("cyberchef", "ghcr.io/gchq/cyberchef:latest", [("8000:8000",)]),
    ("dashdot", "mauricenino/dashdot:latest", [("3001:3001",)]),
    ("dashy", "lissy93/dashy:latest", [("4000:8080",)]),
    ("diun", "crazymax/diun:latest", []),
    ("dokuwiki", "lscr.io/linuxserver/dokuwiki", [("8086:80",)]),
    ("excalidraw", "excalidraw/excalidraw:latest", [("3002:80",)]),
    ("freshrss", "lscr.io/linuxserver/freshrss:latest", [("8087:80",)]),
    ("gitea", "gitea/gitea:latest", [("3003:3000", "2222:22")]),
    ("ghost", "ghost:5", [("2368:2368",)]),
    ("gotify", "gotify/server:latest", [("8089:80",)]),
    ("guacamole", "guacamole/guacamole", [("8090:8080",)]),
    ("haproxy", "haproxy:2.9-alpine", [("80:80", "443:443", "1936:1936")]),
    ("heimdall", "lscr.io/linuxserver/heimdall:latest", [("8091:80",)]),
    ("immich", "ghcr.io/immich-app/immich-server:release", [("2283:2283",)]),
    ("influxdb", "influxdb:2.7", [("8086:8086",)]),
    ("it-tools", "corentinth/it-tools:latest", [("8092:80",)]),
    ("jellyseerr", "fallenbagel/jellyseerr:latest", [("5056:5055",)]),
    ("linkding", "sissbruecker/linkding:latest", [("9095:9090",)]),
    ("mealie", "ghcr.io/mealie-recipes/mealie:latest", [("9000:9000",)]),
    ("minio", "minio/minio:latest", [("9002:9000", "9003:9001")]),
    ("n8n", "n8nio/n8n:latest", [("5678:5678",)]),
    ("netdata", "netdata/netdata:latest", [("19999:19999",)]),
    ("nextcloud", "nextcloud:latest", [("8093:80",)]),
    ("nzbget", "lscr.io/linuxserver/nzbget:latest", [("6789:6789",)]),
    ("olivetin", "jamesread/olivetin:latest", [("1337:1337",)]),
    ("paperless", "ghcr.io/paperless-ngx/paperless-ngx:latest", [("8094:8000",)]),
    ("scrutiny", "ghcr.io/analogj/scrutiny:master-web", [("8095:8080",)]),
    ("stirling-pdf", "frooodle/s-pdf:latest", [("8096:8080",)]),
    ("syncthing", "lscr.io/linuxserver/syncthing:latest", [("8384:8384", "22000:22000")]),
    ("tandoor", "ghcr.io/tandoorrecipes/recipes:latest", [("8097:8080",)]),
]

def gen_stress():
    s = "stress-test"

    for i, (name, image, ports) in enumerate(STRESS_SERVICES):
        # Vary the issues intentionally
        has_restart = i % 3 != 0       # 1 in 3 missing restart
        has_tz = i % 4 != 0            # 1 in 4 missing TZ
        has_secret = i % 5 == 0        # 1 in 5 has hardcoded secret
        use_list_env = i % 2 == 0      # Alternate between dict and list env

        port_lines = ""
        if ports:
            port_lines = "    ports:\n"
            for p in ports:
                if isinstance(p, tuple):
                    for pp in p:
                        port_lines += f'      - "{pp}"\n'
                else:
                    port_lines += f'      - "{p}"\n'

        env_entries = {}
        if has_tz:
            env_entries["TZ"] = "America/Denver"
        env_entries["PUID"] = "1000"
        env_entries["PGID"] = "1000"
        if has_secret:
            env_entries["SECRET_KEY"] = f"supersecret{name}key1234567890"
            env_entries["DB_PASSWORD"] = f"dbpass_{name}_xYz!987"

        if use_list_env:
            env_block = "    environment:\n"
            for k, v in env_entries.items():
                env_block += f"      - {k}={v}\n"
        else:
            env_block = "    environment:\n"
            for k, v in env_entries.items():
                env_block += f"      {k}: {v}\n"

        restart_line = "    restart: unless-stopped\n" if has_restart else ""

        content = f"""\
services:
  {name}:
    image: {image}
    container_name: {name}
{restart_line}{port_lines}{env_block}    volumes:
      - ./config:/config
"""
        write(s, f"{name}/compose.yaml", content)


# ══════════════════════════════════════════════════════════════════
# Stack 6: rule-showcase  (24 files — one per missing rule, complete coverage)
# ══════════════════════════════════════════════════════════════════

def gen_rule_showcase():
    """Generate rule showcase stack — triggers ALL 24 missing rules.

    Combined with the 6 rules already seeded in other stacks
    (CA001, CA101, CA201, CA203, CA301, CA403), this gives
    complete coverage of all 30 ComposeArr rules.
    """
    s = "rule-showcase"

    # ── CA003 — untrusted-registry ──
    write(s, "ca003-untrusted-registry/compose.yaml", """\
services:
  sketchy-app:
    image: randomuser/totally-safe-image:1.0
    container_name: sketchy-app
    restart: unless-stopped
    environment:
      TZ: America/New_York
""")

    # ── CA202 — no-fake-healthcheck ──
    write(s, "ca202-fake-healthcheck/compose.yaml", """\
services:
  fake-healthy:
    image: nginx:1.27-alpine
    container_name: fake-healthy
    restart: unless-stopped
    environment:
      TZ: America/New_York
    healthcheck:
      test: ["CMD-SHELL", "exit 0"]
      interval: 30s
      timeout: 5s
      retries: 3
""")

    # ── CA302 — unreachable-dependency (cross-file, needs two services) ──
    write(s, "ca302-unreachable-dep/compose.yaml", """\
services:
  web:
    image: nginx:1.27-alpine
    container_name: web-isolated
    restart: unless-stopped
    environment:
      TZ: America/New_York
    networks:
      - frontend
    depends_on:
      - api

  api:
    image: nginx:1.27-alpine
    container_name: api-isolated
    restart: unless-stopped
    environment:
      TZ: America/New_York
    networks:
      - backend

networks:
  frontend:
  backend:
""")

    # ── CA303 — isolated-service-ports ──
    write(s, "ca303-isolated-ports/compose.yaml", """\
services:
  isolated-app:
    image: nginx:1.27-alpine
    container_name: isolated-app
    restart: unless-stopped
    network_mode: "none"
    ports:
      - "9999:80"
    environment:
      TZ: America/New_York
""")

    # ── CA304 — dns-configuration ──
    write(s, "ca304-dns-config/compose.yaml", """\
services:
  bad-dns:
    image: nginx:1.27-alpine
    container_name: bad-dns
    restart: unless-stopped
    environment:
      TZ: America/New_York
    dns:
      - 0.0.0.0
""")

    # ── CA401 — puid-pgid-mismatch (needs two services with different PUID) ──
    write(s, "ca401-puid-mismatch/compose.yaml", """\
services:
  sonarr:
    image: lscr.io/linuxserver/sonarr:4.0.14
    container_name: sonarr-mismatch
    restart: unless-stopped
    environment:
      TZ: America/New_York
      PUID: 1000
      PGID: 1000

  radarr:
    image: lscr.io/linuxserver/radarr:5.20
    container_name: radarr-mismatch
    restart: unless-stopped
    environment:
      TZ: America/New_York
      PUID: 1001
      PGID: 1001
""")

    # ── CA402 — umask-inconsistent (needs arr services with different UMASK) ──
    write(s, "ca402-umask-drift/compose.yaml", """\
services:
  sonarr:
    image: lscr.io/linuxserver/sonarr:4.0.14
    container_name: sonarr-umask
    restart: unless-stopped
    environment:
      TZ: America/New_York
      PUID: 1000
      PGID: 1000
      UMASK: "002"

  radarr:
    image: lscr.io/linuxserver/radarr:5.20
    container_name: radarr-umask
    restart: unless-stopped
    environment:
      TZ: America/New_York
      PUID: 1000
      PGID: 1000
      UMASK: "022"
""")

    # ── CA404 — duplicate-env-vars ──
    write(s, "ca404-duplicate-env/compose.yaml", """\
services:
  app:
    image: nginx:1.27-alpine
    container_name: dup-env-app
    restart: unless-stopped
    environment:
      TZ: America/New_York
      LOG_LEVEL: info
      LOG_LEVEL: debug
""")

    # ── CA501 — missing-memory-limit ──
    write(s, "ca501-no-memory-limit/compose.yaml", """\
services:
  memory-hog:
    image: nginx:1.27-alpine
    container_name: memory-hog
    restart: unless-stopped
    environment:
      TZ: America/New_York
""")

    # ── CA502 — missing-cpu-limit ──
    write(s, "ca502-no-cpu-limit/compose.yaml", """\
services:
  cpu-hog:
    image: nginx:1.27-alpine
    container_name: cpu-hog
    restart: unless-stopped
    environment:
      TZ: America/New_York
    deploy:
      resources:
        limits:
          memory: 512M
""")

    # ── CA503 — resource-limits-unusual ──
    write(s, "ca503-unusual-limits/compose.yaml", """\
services:
  unrealistic:
    image: nginx:1.27-alpine
    container_name: unrealistic
    restart: unless-stopped
    environment:
      TZ: America/New_York
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "0.01"
""")

    # ── CA504 — no-logging-config ──
    write(s, "ca504-no-logging/compose.yaml", """\
services:
  no-logging:
    image: nginx:1.27-alpine
    container_name: no-logging
    restart: unless-stopped
    environment:
      TZ: America/New_York
""")

    # ── CA505 — no-log-rotation ──
    write(s, "ca505-no-log-rotation/compose.yaml", """\
services:
  json-logger:
    image: nginx:1.27-alpine
    container_name: json-logger
    restart: unless-stopped
    environment:
      TZ: America/New_York
    logging:
      driver: json-file
""")

    # ── CA601 — hardlink-path-mismatch (arr services without unified /data) ──
    write(s, "ca601-hardlink-mismatch/compose.yaml", """\
services:
  sonarr:
    image: lscr.io/linuxserver/sonarr:4.0.14
    container_name: sonarr-hardlink
    restart: unless-stopped
    environment:
      TZ: America/New_York
      PUID: 1000
      PGID: 1000
    volumes:
      - ./config:/config
      - /media/tv:/tv
      - /downloads:/downloads

  radarr:
    image: lscr.io/linuxserver/radarr:5.20
    container_name: radarr-hardlink
    restart: unless-stopped
    environment:
      TZ: America/New_York
      PUID: 1000
      PGID: 1000
    volumes:
      - ./config:/config
      - /media/movies:/movies
      - /downloads:/downloads
""")

    # ── CA701 — prefer-named-volumes (bind mount for database) ──
    write(s, "ca701-bind-mount/compose.yaml", """\
services:
  database:
    image: postgres:16-alpine
    container_name: bind-db
    restart: unless-stopped
    environment:
      TZ: America/New_York
      POSTGRES_PASSWORD: example
    volumes:
      - ./postgres-data:/var/lib/postgresql/data
""")

    # ── CA702 — undefined-volume-ref ──
    write(s, "ca702-undefined-volume/compose.yaml", """\
services:
  app:
    image: nginx:1.27-alpine
    container_name: undef-vol-app
    restart: unless-stopped
    environment:
      TZ: America/New_York
    volumes:
      - missing_volume:/data
""")

    # ── CA801 — no-capability-restrictions ──
    write(s, "ca801-no-cap-drop/compose.yaml", """\
services:
  unrestricted:
    image: nginx:1.27-alpine
    container_name: unrestricted
    restart: unless-stopped
    environment:
      TZ: America/New_York
""")

    # ── CA802 — privileged-mode ──
    write(s, "ca802-privileged/compose.yaml", """\
services:
  privileged-container:
    image: alpine:3.19
    container_name: privileged
    privileged: true
    restart: unless-stopped
    command: sleep infinity
    environment:
      TZ: America/New_York
""")

    # ── CA803 — no-read-only-root ──
    write(s, "ca803-no-readonly/compose.yaml", """\
services:
  writable:
    image: nginx:1.27-alpine
    container_name: writable
    restart: unless-stopped
    environment:
      TZ: America/New_York
""")

    # ── CA804 — no-new-privileges ──
    write(s, "ca804-no-new-privileges/compose.yaml", """\
services:
  escalatable:
    image: nginx:1.27-alpine
    container_name: escalatable
    restart: unless-stopped
    environment:
      TZ: America/New_York
""")

    # ── CA901 — resource-requests-mismatch ──
    write(s, "ca901-requests-mismatch/compose.yaml", """\
services:
  mismatched:
    image: nginx:1.27-alpine
    container_name: mismatched
    restart: unless-stopped
    environment:
      TZ: America/New_York
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: "0.5"
        reservations:
          memory: 512M
          cpus: "1.0"
""")

    # ── CA902 — restart-policy-unlimited ──
    write(s, "ca902-restart-always/compose.yaml", """\
services:
  restart-loop:
    image: nginx:1.27-alpine
    container_name: restart-loop
    restart: always
    environment:
      TZ: America/New_York
""")

    # ── CA903 — tmpfs-no-size-limit ──
    write(s, "ca903-tmpfs-no-limit/compose.yaml", """\
services:
  tmpfs-app:
    image: nginx:1.27-alpine
    container_name: tmpfs-app
    restart: unless-stopped
    environment:
      TZ: America/New_York
    tmpfs:
      - /tmp
""")

    # ── CA904 — no-user-namespace ──
    write(s, "ca904-no-userns/compose.yaml", """\
services:
  no-userns:
    image: nginx:1.27-alpine
    container_name: no-userns
    restart: unless-stopped
    environment:
      TZ: America/New_York
""")


# ══════════════════════════════════════════════════════════════════

def main():
    print(f"\nGenerating test stacks in: {ROOT}\n")

    print("── minimal-stack (3 files) ──")
    gen_minimal()

    print("\n── arr-stack (7 files) ──")
    gen_arr()

    print("\n── media-server (12 files) ──")
    gen_media()

    print("\n── full-homelab (22 files) ──")
    gen_homelab()

    print("\n── stress-test (40 files) ──")
    gen_stress()

    print("\n" + "─" * 60)
    print("  rule-showcase (24 files) — ALL 30 rules triggered!")
    print("─" * 60)
    gen_rule_showcase()

    # Count totals
    total = 0
    stacks = 0
    for stack_dir in sorted(ROOT.iterdir()):
        if stack_dir.is_dir() and not stack_dir.name.startswith(("_", ".")):
            count = len(list(stack_dir.rglob("compose.yaml")))
            if count:
                total += count
                stacks += 1
                print(f"\n  {stack_dir.name}: {count} compose files")
    print(f"\n  TOTAL: {total} compose files across {stacks} stacks")
    print("  Complete 30-rule coverage\n")

    # Summary of seeded issues
    print("Seeded issues (stacks 1-5):")
    print("  CA001 — :latest / untagged images scattered throughout")
    print("  CA101 — Hardcoded secrets (API keys, passwords, tokens)")
    print("  CA201 — Missing healthchecks (most services)")
    print("  CA203 — Missing restart policy (several per stack)")
    print("  CA403 — Missing TZ environment variable")
    print("  CA3xx — Port conflicts (8080 duplicated, etc)")
    print("  Mixed — dict-style and list-style environment blocks")
    print("  Mixed — host, bridge, named, and shared network modes")
    print("  Mixed — depends_on chains for topology testing")
    print()
    print("Rule showcase (stack 6 — 24 additional rules):")
    print("  CA003, CA202, CA302, CA303, CA304, CA401, CA402, CA404")
    print("  CA501, CA502, CA503, CA504, CA505, CA601, CA701, CA702")
    print("  CA801, CA802, CA803, CA804, CA901, CA902, CA903, CA904")
    print()


if __name__ == "__main__":
    main()
