# ComposeArr MVP Rules - Complete Specification

This document defines the 10 rules shipping in v0.1.0.

Each rule includes:
- ID and name
- Severity level
- Scope (service/file/project)
- Detection logic
- Fix suggestion
- Documentation links
- Example violations

---

## CA001 - no-latest-tag

**Category:** Images  
**Severity:** warning  
**Scope:** service  
**Fixable:** yes (v0.2)

### Description
Image uses `:latest` tag or has no tag specified. This is a moving target and can cause unexpected updates.

### Rationale
The `:latest` tag always points to the newest image. When you `docker compose pull`, you might get a breaking change without warning. Version pinning ensures reproducibility.

### Detection
```python
# Triggers on:
image: "lscr.io/linuxserver/plex:latest"
image: "lscr.io/linuxserver/plex"  # No tag = implicit :latest

# Does NOT trigger on:
image: "lscr.io/linuxserver/plex:1.41.3"
image: "lscr.io/linuxserver/plex:version-1.41.3"
```

### Fix Suggestion
**Smart tag lookup:**
1. Parse image name (registry/org/image)
2. Fetch available tags from Docker Hub/GHCR API
3. Identify versioning pattern:
   - Semantic versions (1.2.3)
   - Date-based (2024.01.15)
   - Named releases (stable, release)
4. Suggest appropriate tag

**Example output:**
```
⚠️  CA001 (warning): Image uses :latest tag
    image: lscr.io/linuxserver/plex:latest

    Available tags for this image:
      • 1.41.3 (latest stable)
      • 1.41.2
      • version-1.41.3 (recommended)
    
    Suggested fix:
    image: lscr.io/linuxserver/plex:1.41.3
    
    Or use digest pinning:
    image: lscr.io/linuxserver/plex@sha256:abc123...
```

### Learn More
- https://docs.docker.com/develop/dev-best-practices/#how-to-keep-your-images-small
- https://docs.linuxserver.io/images/docker-plex/#application-setup

### Edge Cases
- Custom registries might not support tag API
- Some images intentionally use :latest (testing environments)
- Allow suppression: `# composearr-ignore: CA001`

---

## CA101 - no-inline-secrets

**Category:** Security  
**Severity:** error  
**Scope:** service  
**Fixable:** yes (v0.2)

### Description
Secret value is hardcoded in the environment block. Secrets should be in .env files, not committed to git.

### Rationale
Hardcoded secrets in compose files get committed to version control, exposing API keys, passwords, and tokens. This is a critical security issue.

### Detection
**Pattern matching + entropy analysis:**

```python
SENSITIVE_PATTERNS = [
    r'.*API[_-]?KEY.*',
    r'.*PASSWORD.*',
    r'.*SECRET.*',
    r'.*TOKEN.*',
    r'.*PRIVATE[_-]?KEY.*',
    r'.*AUTH.*',
    r'.*CREDENTIAL.*',
]

# Also check for high-entropy strings (likely to be secrets)
# Example: "bijL6fcCeVv25izRy3JseahatW9rsd0eCpo5aLricRI=" has high entropy
```

**Triggers on:**
```yaml
environment:
  WIREGUARD_PRIVATE_KEY: bijL6fcCeVv25izRy3JseahatW9rsd0eCpo5aLricRI=
  API_KEY: sk_test_abc123def456
  POSTGRES_PASSWORD: mySecurePassword123
```

**Does NOT trigger on:**
```yaml
environment:
  WIREGUARD_PRIVATE_KEY: ${WIREGUARD_PRIVATE_KEY}  # Reference, not value
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}  # Default is OK if clearly placeholder
  DEBUG: "true"  # Not a secret
  PORT: "8080"  # Not a secret
```

### Fix Suggestion
```
✖ CA101 (error): Secret value hardcoded in environment block
  18 │       - WIREGUARD_PRIVATE_KEY=bijL6fcCeVv25izRy3Jsea...
     │         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  Fix:
  1. Add to .env file:
     WIREGUARD_PRIVATE_KEY=bijL6fcCeVv25izRy3JseahatW9rsd0eCpo5aLricRI=
  
  2. Change compose.yaml to:
     - WIREGUARD_PRIVATE_KEY=${WIREGUARD_PRIVATE_KEY}
  
  3. Ensure .env is in .gitignore
```

### Learn More
- https://docs.docker.com/compose/use-secrets/
- https://12factor.net/config
- https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

### Edge Cases
- Some values look like secrets but aren't (base64 encoded configs)
- Allow override: `# composearr-ignore: CA101` for test fixtures
- Empty/placeholder values should not trigger

---

## CA201 - require-healthcheck

**Category:** Reliability  
**Severity:** warning  
**Scope:** service  
**Fixable:** no (requires user input)

### Description
Service has no healthcheck defined. Docker cannot detect if the container is healthy or hung.

### Rationale
Without healthchecks, Docker only knows if the process is running, not if it's functioning. A web server with a crashed thread pool will show as "running" but be completely broken.

### Detection
```python
# Triggers when:
service.get('healthcheck') is None

# Does NOT trigger for:
- Databases (postgres, mysql, redis) - they have internal health
- One-shot containers (restart: "no")
- Init containers
```

### Fix Suggestion
**Smart healthcheck suggestions based on service type:**

```
⚠️  CA201 (warning): Service missing healthcheck

  Detected service type: Web application (port 8080 exposed)
  
  Suggested healthchecks:
  
  Option 1: HTTP check (recommended)
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
  
  Option 2: Process check
    healthcheck:
      test: ["CMD-SHELL", "pgrep -f sonarr || exit 1"]
      interval: 60s
      timeout: 10s
      retries: 5
      start_period: 40s
  
  Option 3: Skip healthcheck
    # composearr-ignore: CA201
    # Reason: Service doesn't need health monitoring
```

**CRITICAL: Healthcheck Ejector Seats**

When a healthcheck fails in production:
```
🚨 Healthcheck failing? Quick fixes:

1. 🔧 Change healthcheck type
   Current: curl check on /health
   Try: Process check (pgrep -f servicename)
   Try: Always pass (exit 0) - TEMPORARY ONLY

2. ⏱️  Adjust timings
   Current intervals might be too aggressive
   Try: Longer interval (60s → 120s)
   Try: More retries (3 → 5)
   Try: Longer start_period (30s → 60s)

3. 🔍 Debug mode
   Run: docker exec SERVICE /bin/sh -c "curl -f http://localhost:8080/health"
   See exact error output

4. 🚫 Disable temporarily
   Comment out healthcheck block
   Service will show as "Up" without health status
   Re-enable once issue is diagnosed

Need help? https://composearr.dev/docs/healthcheck-troubleshooting
```

### Learn More
- https://docs.docker.com/engine/reference/builder/#healthcheck
- https://docs.linuxserver.io/faq/#my-host-is-incompatible-with-images-based-on-ubuntu-focal
- https://docs.docker.com/compose/compose-file/05-services/#healthcheck

### Edge Cases
- Some services (watchtower, diun) don't need healthchecks
- Databases have internal health - don't nag
- Short-lived containers (restart: "no") don't need health

---

## CA202 - no-fake-healthcheck

**Category:** Reliability  
**Severity:** warning  
**Scope:** service  
**Fixable:** no

### Description
Healthcheck always passes (exit 0, true, etc). This provides no actual health information.

### Rationale
A healthcheck that always succeeds defeats the purpose. It gives false confidence that the service is healthy when it might be completely broken.

### Detection
```python
# Triggers on:
healthcheck:
  test: ["CMD-SHELL", "exit 0"]
  test: ["CMD-SHELL", "true"]
  test: ["CMD", "true"]
  test: "exit 0"

# Also triggers on obviously fake checks:
  test: ["CMD-SHELL", "echo 'healthy'"]  # Just printing text
  test: ["CMD-SHELL", "sleep 1"]  # Doing nothing
```

### Fix Suggestion
```
⚠️  CA202 (warning): Healthcheck always passes - provides no health info
  
  Current:
    test: ["CMD-SHELL", "exit 0"]
  
  This healthcheck will ALWAYS succeed, even if the service is broken.
  
  Better options:
  
  1. Check if process is running:
     test: ["CMD-SHELL", "pgrep -f qbittorrent || exit 1"]
  
  2. Check HTTP endpoint:
     test: ["CMD-SHELL", "curl -sf http://localhost:8080/api/v2/app/version || exit 1"]
  
  3. Check specific port is listening:
     test: ["CMD-SHELL", "nc -z localhost 8080 || exit 1"]
  
  4. If you genuinely don't need health monitoring:
     Remove the healthcheck block entirely
     # composearr-ignore: CA201
```

### Learn More
- https://docs.docker.com/engine/reference/builder/#healthcheck
- https://blog.sixeyed.com/docker-healthchecks-why-not-to-use-curl-or-iwr/

---

## CA203 - require-restart-policy

**Category:** Reliability  
**Severity:** warning  
**Scope:** service  
**Fixable:** yes (v0.2)

### Description
Service has no restart policy defined. Container won't auto-restart after failure or host reboot.

### Rationale
Without a restart policy, containers stay down after crashes or system reboots. For long-running services, this means manual intervention is required.

### Detection
```python
# Triggers when:
service.get('restart') is None

# Does NOT trigger for:
- restart: "no" (explicit choice)
- restart: "always"
- restart: "unless-stopped"
- restart: "on-failure"
```

### Fix Suggestion
```
⚠️  CA203 (warning): No restart policy defined
  
  Current: (no restart policy)
  
  For long-running services, use:
    restart: unless-stopped
  
  This ensures the container:
  ✅ Restarts after crashes
  ✅ Starts on system boot
  ❌ Won't restart if you manually stopped it
  
  Other options:
  - restart: always (even if manually stopped)
  - restart: "on-failure:5" (only on errors, max 5 retries)
  - restart: "no" (never restart - for one-shot tasks)
```

### Learn More
- https://docs.docker.com/config/containers/start-containers-automatically/
- https://docs.docker.com/compose/compose-file/05-services/#restart

---

## CA301 - port-conflict (CROSS-FILE)

**Category:** Networking  
**Severity:** error  
**Scope:** project  
**Fixable:** no

### Description
Multiple services are trying to bind the same host port. This will cause deployment failures.

### Rationale
Only one service can bind to a host port at a time. If two compose files try to use port 8080, the second one will fail to start.

### Detection
**Cross-file analysis required!**

```python
all_ports = {}
for compose_file in all_files:
    for service in compose_file.services:
        for port_mapping in service.ports:
            host_port = parse_host_port(port_mapping)
            if host_port in all_ports:
                # CONFLICT!
                yield LintIssue(
                    rule_id="CA301",
                    message=f"Port {host_port} used by multiple services",
                    affected_services=[
                        all_ports[host_port],
                        current_service
                    ]
                )
```

**Port parsing handles all formats:**
```yaml
ports:
  - "8080:80"              # host 8080
  - "8080:80/udp"          # host 8080 UDP
  - "127.0.0.1:8080:80"    # host 8080 on localhost only
  - "8080-8090:80-90"      # range: host 8080-8090
  - target: 80             # long form
    published: 8080
    host_ip: 0.0.0.0
```

### Fix Suggestion
```
✖ CA301 (error): Port conflict detected

  Port 8080 is used by multiple services:
  
  ├─ sonarr/compose.yaml (line 7)
  │    ports:
  │      - "8080:8989"
  │
  └─ radarr/compose.yaml (line 7)
       ports:
         - "8080:7878"
  
  Only one service can bind to port 8080 on the host.
  
  Solutions:
  1. Change one service to use a different port:
     - "8081:7878"  (for radarr)
  
  2. Bind to different interfaces:
     - "127.0.0.1:8080:8989"  (sonarr on localhost only)
     - "192.168.1.10:8080:7878"  (radarr on specific IP)
  
  3. Use a reverse proxy (recommended):
     Access both via nginx/traefik on different subdomains
```

### Learn More
- https://docs.docker.com/compose/compose-file/05-services/#ports
- https://docs.docker.com/config/containers/container-networking/#published-ports

---

## CA401 - puid-pgid-mismatch (CROSS-FILE)

**Category:** Consistency  
**Severity:** error  
**Scope:** project  
**Fixable:** no

### Description
PUID/PGID values differ across services. This breaks file permissions and hardlinks in media stacks.

### Rationale
For hardlinks to work (TRaSH Guides), all services that touch the same files must run as the same user. Different UIDs mean files get created with different ownership, breaking hardlinks and causing permission errors.

### Detection
**Cross-file analysis:**

```python
puid_groups = defaultdict(list)
for file in all_files:
    for service_name, service in file.services.items():
        puid = get_env_var(service, 'PUID')
        if puid:
            puid_groups[puid].append((file.path, service_name))

if len(puid_groups) > 1:
    # MISMATCH!
    yield LintIssue(...)
```

### Fix Suggestion
```
✖ CA401 (error): PUID/PGID mismatch across stack

  Different PUID values detected:
  
  ├─ PUID=1000 (8 services)
  │  ├─ sonarr/compose.yaml
  │  ├─ radarr/compose.yaml
  │  ├─ bazarr/compose.yaml
  │  ├─ prowlarr/compose.yaml
  │  ├─ plex/compose.yaml
  │  └─ ... 3 more
  │
  ├─ PUID=568 (2 services)
  │  ├─ qbittorrent/compose.yaml
  │  └─ sabnzbd/compose.yaml
  │
  └─ PUID=0 (3 services)
     ├─ gluetun/compose.yaml
     ├─ huntarr/compose.yaml
     └─ decypharr/compose.yaml
  
  Problem:
  Services with different PUIDs cannot share files or create hardlinks.
  Your media stack will have permission errors and wasted disk space.
  
  Solution:
  All media stack services should use PUID=1000 (your host user):
  - sonarr, radarr, bazarr, prowlarr → already correct ✓
  - qbittorrent, sabnzbd → change to PUID=1000
  - gluetun, huntarr, decypharr → may need root (0) for network/fuse
  
  Learn more about hardlinks and permissions:
  https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/
```

### Learn More
- https://docs.linuxserver.io/general/understanding-puid-and-pgid/
- https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/

---

## CA402 - umask-inconsistent (CROSS-FILE)

**Category:** Consistency  
**Severity:** warning  
**Scope:** project  
**Fixable:** no

### Description
UMASK values differ across *arr services. This can cause permission issues with newly created files.

### Rationale
UMASK controls default file permissions. Inconsistent UMASK means some files are created with 644 (readable by group) and others with 640 (not readable). This breaks hardlinks and causes access issues.

### Detection
```python
# Check UMASK in all *arr services
arr_services = [s for s in services if s.image.contains('sonarr|radarr|lidarr|bazarr')]
umask_values = {get_env_var(s, 'UMASK') for s in arr_services}

if len(umask_values) > 1:
    # INCONSISTENT!
```

**Recommended:** UMASK=002 (files: 664, dirs: 775 - group writable)  
**Alternative:** UMASK=022 (files: 644, dirs: 755 - group readable only)

### Fix Suggestion
```
⚠️  CA402 (warning): UMASK inconsistent across *arr services

  ├─ UMASK=022 → sonarr, radarr, bazarr
  └─ UMASK=002 → qbittorrent
  
  Recommendation: Use UMASK=002 everywhere
  
  Why 002?
  - Files: 664 (rw-rw-r--) - group can write
  - Dirs:  775 (rwxrwxr-x) - group can create files
  - Allows hardlinks between services
  - Allows SABnzbd → Sonarr atomic moves
  
  TRaSH Guides recommends UMASK=002 for media stacks.
```

### Learn More
- https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/
- https://hotio.dev/faq/#umask

---

## CA403 - missing-timezone

**Category:** Consistency  
**Severity:** warning  
**Scope:** service  
**Fixable:** yes (v0.2)

### Description
TZ environment variable not set. Service will use UTC, causing incorrect timestamps in logs.

### Detection
```python
# Triggers when:
'TZ' not in service.environment
```

### Fix Suggestion
```
⚠️  CA403 (warning): TZ environment variable not set
  
  Service will use UTC timezone.
  Logs and schedules will show incorrect times.
  
  Add to environment:
    TZ: Australia/Sydney
  
  Or use central .env:
    TZ=${TZ}
  
  Then in .env file:
    TZ=Australia/Sydney
```

### Learn More
- https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

---

## CA601 - hardlink-path-mismatch (CROSS-FILE)

**Category:** Arr Stack  
**Severity:** warning  
**Scope:** project  
**Fixable:** no

### Description
*arr services don't use unified /data mount structure. This prevents hardlinks and instant moves.

### Rationale
For hardlinks to work, all containers must see the source and destination as the SAME filesystem. If Sonarr sees `/downloads` and `/media` as separate mounts (even if they're on the same disk on the host), it will COPY instead of hardlink.

TRaSH Guides solution: All services mount `/host/data:/data` and use subdirectories.

### Detection
**Complex cross-file check:**

```python
# Find all *arr services
arr_services = find_arr_services(all_files)

# Check if they use unified mount
for service in arr_services:
    volumes = service.get('volumes', [])
    
    # Look for unified /data mount
    has_unified = any('/data' in vol for vol in volumes)
    
    # Look for split mounts
    has_split = any('/downloads' in vol or '/media' in vol for vol in volumes)
    
    if has_split and not has_unified:
        # VIOLATION!
```

### Fix Suggestion
```
⚠️  CA601 (warning): Services not using unified /data mount

  Current setup (BREAKS HARDLINKS):
    sonarr:
      volumes:
        - /mnt/nas/Media:/media
        - /mnt/nas/Torrents:/downloads
    
    radarr:
      volumes:
        - /mnt/nas/Media:/media
        - /mnt/nas/Torrents:/downloads
  
  Problem:
  Docker sees /media and /downloads as SEPARATE filesystems.
  File moves will COPY instead of hardlink (slow + double disk usage).
  
  TRaSH Guides solution (ENABLES HARDLINKS):
    ALL services use same root mount:
    
    sonarr:
      volumes:
        - /mnt/nas:/data
    
    radarr:
      volumes:
        - /mnt/nas:/data
    
    qbittorrent:
      volumes:
        - /mnt/nas:/data
  
  Then update paths in each app:
    Sonarr:  /data/Media/TV, /data/Torrents/tv-sonarr
    Radarr:  /data/Media/Movies, /data/Torrents/movies
    qBit:    /data/Torrents
  
  Result: Instant atomic moves, no disk space wasted.
  
  Learn more:
  https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/
  https://trash-guides.info/Hardlinks/Hardlinks-and-Instant-Moves/
```

### Learn More
- https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/
- https://trash-guides.info/File-and-Folder-Structure/

---

## SUMMARY

### MVP Rules (v0.1.0)

| ID | Name | Severity | Scope | Fixable |
|----|------|----------|-------|---------|
| CA001 | no-latest-tag | warning | service | v0.2 |
| CA101 | no-inline-secrets | error | service | v0.2 |
| CA201 | require-healthcheck | warning | service | no |
| CA202 | no-fake-healthcheck | warning | service | no |
| CA203 | require-restart-policy | warning | service | v0.2 |
| CA301 | port-conflict | error | project | no |
| CA401 | puid-pgid-mismatch | error | project | no |
| CA402 | umask-inconsistent | warning | project | no |
| CA403 | missing-timezone | warning | service | v0.2 |
| CA601 | hardlink-path-mismatch | warning | project | no |

### Rule Distribution
- **Service-scope:** 6 rules (run per-service)
- **Project-scope:** 4 rules (cross-file analysis)
- **Errors:** 3 rules (must fix)
- **Warnings:** 7 rules (should fix)
- **Auto-fixable (v0.2):** 4 rules

### Key Features
- ✅ Cross-file analysis (CA301, CA401, CA402, CA601)
- ✅ Security detection (CA101 with pattern + entropy)
- ✅ Smart suggestions (tag lookup, healthcheck templates)
- ✅ Homelab-aware (LSIO, Hotio, TRaSH compliance)
- ✅ Documentation links for every rule
- ✅ Healthcheck ejector seats (CA201/CA202)

---

**NEXT:** Config system design (.composearr.yml format)
