# Stack Manager Compatibility Research
## ComposeArr Secure-Secrets Feature Safety Analysis

**Date:** 2026-02-17
**Critical Question:** Can ComposeArr safely centralize env files for users of different stack managers?

---

## Executive Summary

**Finding:** Centralizing `env_file` paths is **unsafe as a default behavior** for the majority of stack managers. Most popular tools run Docker Compose inside a container, meaning absolute host paths in `env_file:` directives **will not resolve**.

**Key insight:** There are three deployment models, and each has different implications:

| Model | Tools | env_file with host paths? |
|-------|-------|--------------------------|
| **Container-based compose** | Portainer, Dockge, Yacht | BREAKS - paths resolve inside container |
| **Host-native compose** | CasaOS, TrueNAS Scale, Runtipi (CLI) | Works, but each has caveats |
| **No compose / own format** | Cosmos Cloud, Umbrel, Unraid (native) | N/A - env_file not supported |

**Recommendation:** **Option 3: Interactive** approach with detection. ComposeArr should:
1. Detect the stack manager in use (or ask the user)
2. Warn before any env_file path changes
3. Provide tool-specific guidance
4. Default to **no centralization** unless the user explicitly opts in

**Go/No-Go:** The secure-secrets feature can ship, but `env_file` centralization must be **opt-in with warnings**, never automatic.

---

## Tool-by-Tool Analysis

---

### 1. Komodo

**Deployment Method:** Container-based (CONFIRMED by Judd's production debugging)

**How it works:**
- Runs `docker compose` inside `komodo-periphery` container
- Mounts `/var/run/docker.sock` to control Docker
- Uses git clone workflow (repos cloned to mounted volume)
- Cannot access arbitrary host paths without explicit mounts

**Container Details:**
```yaml
komodo-periphery:
  image: ghcr.io/moghtech/komodo-periphery:latest
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - /host/path/to/periphery:/etc/komodo
    - /host/path/to/stacks:/mnt/stacks
    # User must add:
    - /host/path/to/.env:/etc/komodo/.env:ro
```

**Path Access:**
- Host paths like `/mnt/c/DockerContainers/.env`: **FAILS** (not mounted)
- Container paths like `/etc/komodo/.env`: **WORKS** (if mounted by user)
- Relative paths: **WORKS** (relative to repo clone location)

**ComposeArr Implications:**
- CRITICAL: Cannot centralize to arbitrary host paths
- MUST detect Komodo usage
- MUST use Komodo-specific mount path or warn user
- Cannot auto-fix without user setup first

**Detection Methods:**
- Running containers with image `ghcr.io/moghtech/komodo-periphery`
- `komodo-db` and `komodo-periphery` containers running
- Komodo config directory structure present

**Sources:** Judd's production debugging, INSTRUCTIONS.md, confirmed working solution

---

### 2. Portainer

**Deployment Method:** Container-based (uses embedded Go library, not CLI)

**How it works:**
- Runs as `portainer/portainer-ce` container
- Uses `libstack.Deployer` (Go library wrapping Docker Compose) — does NOT shell out to `docker compose`
- Compose files stored inside container at `/data/compose/{stackID}/docker-compose.yml`
- Parses `env_file` directives itself before issuing Docker API calls

**Container Details:**
```yaml
portainer:
  image: portainer/portainer-ce:lts
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - portainer_data:/data
```

**Path Access:**
- Host paths in `env_file:`: **FAILS** — resolved inside Portainer container, not on host
- Volume bind mounts: **WORKS** — passed through to Docker daemon, resolved on host
- This asymmetry is the key gotcha (GitHub issue #4600)

**env_file behavior:**
- `env_file: /home/user/.env` → FAILS (path doesn't exist in container)
- `env_file: ./stack.env` → WORKS (relative to `/data/compose/{stackID}/`)
- Workaround: bind-mount env file directory into Portainer container

**Recommended Pattern:**
- Portainer UI environment variables (substitution for `${VAR}` in YAML)
- `env_file: stack.env` for container env vars (Standalone only, not Swarm)

**ComposeArr Implications:**
- HIGH RISK: Centralizing env_file with absolute paths breaks Portainer
- Should detect and warn
- Alternative: suggest `${VAR}` substitution syntax

**Detection Methods:**
- Running container with image `portainer/portainer-ce` or `portainer/portainer-ee`
- Docker volume `portainer_data`
- API at port 9443 (HTTPS) or 9000 (HTTP legacy): `GET /api/status`

**Sources:** Portainer docs, GitHub issue #4600, community blog posts

---

### 3. Dockge

**Deployment Method:** Container-based (shells out to `docker compose` CLI inside container)

**How it works:**
- Runs as `louislam/dockge` container
- Node.js backend spawns `docker compose` as child process
- Compose files stored at `/opt/stacks/{stack-name}/compose.yaml`
- CRITICAL: Both sides of volume mount must match (`/opt/stacks:/opt/stacks`)

**Container Details:**
```yaml
dockge:
  image: louislam/dockge:1
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - ./data:/app/data
    - /opt/stacks:/opt/stacks    # MUST match both sides
  environment:
    - DOCKGE_STACKS_DIR=/opt/stacks
```

**Path Access:**
- Paths outside `/opt/stacks`: **FAILS** (not mounted)
- Paths within `/opt/stacks`: **WORKS**
- Relative paths from compose file: **WORKS** (within stacks dir)

**env_file behavior:**
- Dockge does NOT intercept `env_file` — passes straight to `docker compose`
- `docker compose` resolves paths inside the container
- Absolute paths outside mounted dirs: **FAILS**
- Relative `.env` co-located with compose file: **WORKS**

**Recommended Pattern:**
- Per-stack `.env` file alongside `compose.yaml` in `/opt/stacks/{stack}/`
- `global.env` at stacks root for shared variables
- Symlinks as workaround for shared env files

**ComposeArr Implications:**
- HIGH RISK for absolute path centralization
- Dockge expects `.env` co-located with `compose.yaml`
- Breaking Dockge UI workflow if env files are moved

**Detection Methods:**
- Running container with image `louislam/dockge`
- `/opt/stacks/*/compose.yaml` directory pattern
- `DOCKGE_STACKS_DIR` environment variable
- Dockge exclusively uses `compose.yaml` (not `docker-compose.yml`)

**Sources:** Dockge GitHub discussions #57, #133, #146; issue #775

---

### 4. CasaOS

**Deployment Method:** Host-native (systemd services, NOT containerized)

**How it works:**
- Installed directly on host via shell script
- `casaos-app-management` service embeds Docker Compose v2 Go library
- Does NOT shell out to `docker compose` CLI
- Compose files stored at `/var/lib/casaos/apps/{app-name}/docker-compose.yml`

**Path Access:**
- Full host filesystem access (runs as root systemd service)
- BUT: UI import copies compose to `/tmp/casaos-compose-app-*/` temporarily
- `.env` files NOT copied alongside during import → import breaks

**env_file behavior:**
- `env_file:` is a **known broken feature** in CasaOS (GitHub issue #1903)
- Works at runtime with absolute paths, but breaks during UI import
- The UI only surfaces inline `environment:` variables
- Workaround: manually place `.env` at absolute path after initial import

**Recommended Pattern:**
- Inline `environment:` blocks with CasaOS system variables (`$PUID`, `$PGID`, `$TZ`)
- `x-casaos` extension for UI metadata
- `env_file:` is NOT part of the official app format

**ComposeArr Implications:**
- MEDIUM RISK: Absolute paths work at runtime but break UI import
- `env_file:` is not officially supported
- Should warn CasaOS users about UI incompatibility

**Detection Methods:**
- `/etc/casaos/casaos.conf` exists
- `/var/lib/casaos/apps/` directory exists
- `x-casaos` key present in compose files
- `casaos` systemd services running

**Sources:** CasaOS GitHub issues #1903, #1248; AppStore CONTRIBUTING.md

---

### 5. Yacht

**Deployment Method:** Container-based (Python `sh` module invokes `docker-compose`)

**How it works:**
- Runs as `selfhostedpro/yacht` container
- Compose files mapped to `/config/compose/` inside container
- Shells out to `docker-compose` CLI from within container

**Path Access:**
- Only `/config` volume and Docker socket mounted by default
- Arbitrary host paths: **NOT accessible**
- `env_file:` resolved inside Yacht container filesystem

**ComposeArr Implications:**
- HIGH RISK: Absolute host paths in env_file WILL BREAK
- Relative paths only work if `.env` is co-located in project directory

**Detection Methods:**
- Container with image `selfhostedpro/yacht` or `yacht-sh/yacht`
- `yacht.*` labels on managed containers

**Sources:** Yacht GitHub repos, documentation

---

### 6. Cosmos Cloud

**Deployment Method:** Container-based (Docker Go SDK, NOT docker-compose)

**How it works:**
- Written in Go + JavaScript
- Uses Docker Go SDK directly (`client.ContainerCreate`)
- Does NOT use docker-compose at all
- Has its own "Cosmos-Compose" format (JSON/YAML derivative)

**env_file support:** **NONE** — `env_file` is not part of the Cosmos-Compose specification

**ComposeArr Implications:**
- N/A: Cosmos doesn't use standard compose format
- If user has Cosmos-managed containers, ComposeArr likely won't encounter them
- Any `env_file` directives would be ignored/stripped

**Detection Methods:**
- Container `cosmos-server` with image `azukaar/cosmos-server`
- `cosmos-*` Docker networks
- `cosmos.*` labels on managed containers

**Sources:** Cosmos-Server GitHub, cosmos-servapps-official repo, Cosmos docs

---

### 7. Runtipi

**Deployment Method:** Hybrid — CLI on host (Rust), backend in container (NestJS)

**How it works:**
- `runtipi-cli` runs on host and spawns `docker compose` directly
- Compose files generated/copied to Runtipi root directory
- App templates define env vars that get merged into `.env` files

**Path Access:**
- Full host access (CLI runs on host)
- `env_file:` resolved on host filesystem — absolute paths work

**env_file behavior:**
- Supported and used natively (`env_file: - .env`)
- BUT: Runtipi regenerates compose and `.env` files during app start/update
- Custom env_file paths may be overwritten

**ComposeArr Implications:**
- LOW-MEDIUM RISK: Technically works but fragile due to regeneration
- Custom paths survive in `user-config/` overrides only

**Detection Methods:**
- Containers with `runtipi-*` prefix
- Network `runtipi_tipi_main_network`
- Directory structure: `app-data/`, `apps/`, `state/`, `user-config/`
- `runtipi-cli` binary present

**Sources:** Runtipi GitHub, runtipi.io docs

---

### 8. Umbrel

**Deployment Method:** Host-native (runs `docker compose` on host, but patches compose files)

**How it works:**
- Each app has `docker-compose.yml` in `/umbrel/app-data/{app}/`
- Umbrel PATCHES compose files at install/startup: rewrites container names, pins images to SHA256, injects `app_proxy` sidecar
- Uses `exports.sh` scripts for inter-app environment sharing

**env_file support:** **Not used** — Umbrel uses its own `exports.sh` system instead

**ComposeArr Implications:**
- HIGH RISK: Compose files are rewritten at runtime
- `env_file` directives may be stripped during patching
- Umbrel's variable system is incompatible with standard env_file

**Detection Methods:**
- `/umbrel/` or `/umbrel/app-data/` directory exists
- `umbrel-app.yml` manifest files present
- `$APP_DATA_DIR` variable usage in compose files
- `umbreld` process running

**Sources:** Umbrel-apps GitHub README, Umbrel community forum

---

### 9. TrueNAS Scale (Electric Eel 24.10+)

**Deployment Method:** Host-native (Docker Compose on host, managed by TrueNAS middleware)

**How it works:**
- Electric Eel (24.10+) switched from Kubernetes to Docker Compose
- Compose runs on host, managed by `middlewared`
- App data under `/mnt/.ix-apps`
- Supports pasting raw Docker Compose YAML in GUI
- Power users use `include:` directive to reference external compose files

**env_file behavior:**
- **Fully supported** in compose YAML
- Absolute host paths work (e.g., `/mnt/pool/dataset/.env`)
- Relative paths work with the `include:` workaround

**ComposeArr Implications:**
- LOW RISK: Standard Docker Compose behavior on host
- Centralized env_file paths work if files are accessible on NAS filesystem

**Detection Methods:**
- `/mnt/.ix-apps` directory exists (Electric Eel)
- `/mnt/*/ix-applications/` (pre-24.10 Kubernetes era)
- `middlewared` process running
- `/etc/truenas_conf` or TrueNAS version identifiers

**Sources:** TrueNAS forums, TrueNAS 24.10 docs

---

### 10. Unraid

**Deployment Method:** Host-native XML templates (NOT docker-compose by default)

**How it works:**
- Native system uses `docker run` commands generated from XML template files
- Templates stored at `/boot/config/plugins/dockerMan/templates-user/`
- Docker Compose available only via optional "Docker Compose Manager" plugin
- Community Applications (CA) plugin provides app-store UI

**env_file support:**
- Native XML system: **No env_file concept** — variables defined individually in XML
- Compose plugin: Standard `env_file` support, host paths work

**ComposeArr Implications:**
- N/A for native Unraid (no compose files)
- LOW RISK for compose plugin users (standard host behavior)

**Detection Methods:**
- `/boot/config/plugins/dockerMan/` directory exists
- XML templates at `/boot/config/plugins/dockerMan/templates-user/*.xml`
- `/etc/unraid-version`
- Slackware-based OS

**Sources:** Unraid wiki, Unraid forums

---

## Common Patterns Identified

### Three Categories of Stack Managers

**Category A: Container-Isolated Compose (HIGH RISK)**
- Portainer, Dockge, Yacht, Komodo
- `docker compose` runs inside a container
- `env_file` paths resolve inside the container, NOT on host
- Absolute host paths BREAK unless explicitly mounted
- **This is the most common deployment model for homelab users**

**Category B: Host-Native Compose (LOW RISK)**
- CasaOS, TrueNAS Scale, Runtipi (CLI)
- Compose runs directly on host or via host-native service
- Absolute host paths work
- But each has its own caveats (CasaOS import bug, Runtipi regeneration)

**Category C: Non-Compose / Custom Format (N/A)**
- Cosmos Cloud, Umbrel, Unraid (native)
- Don't use standard `env_file` at all
- ComposeArr env centralization is irrelevant

### Universal Truths
1. **No universal safe path exists** — every tool has its own filesystem context
2. **Relative paths are safer** than absolute paths (usually resolve from compose file location)
3. **Co-located `.env` files** (same directory as `compose.yaml`) work in almost every tool
4. **Inline `environment:` blocks** are the most universally compatible approach

---

## Recommendations for ComposeArr

### Recommended Approach: Interactive with Detection (Option 3 + Option 2 hybrid)

```
┌─────────────────────────────────────────────────┐
│  ComposeArr Secure-Secrets Decision Flow        │
│                                                 │
│  1. Scan compose files for env_file usage       │
│  2. Attempt to detect stack manager             │
│  3. If detected → show tool-specific guidance   │
│  4. If unknown → ask user how they deploy       │
│  5. Present safe options based on context        │
│  6. User explicitly opts in before any changes   │
└─────────────────────────────────────────────────┘
```

### Implementation: Detection Logic

```python
def detect_stack_manager():
    """Detect which stack manager is in use. Returns list of detected tools."""
    detected = []

    # Category A: Container-based (HIGH RISK)
    containers = get_running_containers()  # via docker ps or Docker API

    for c in containers:
        if "portainer/portainer" in c.image:
            detected.append("portainer")
        if "louislam/dockge" in c.image:
            detected.append("dockge")
        if "selfhostedpro/yacht" in c.image or "yacht-sh/yacht" in c.image:
            detected.append("yacht")
        if "komodo-periphery" in c.image:
            detected.append("komodo")
        if "azukaar/cosmos-server" in c.image:
            detected.append("cosmos")
        if "runtipi" in c.name:
            detected.append("runtipi")

    # Category B: Host-native
    if Path("/etc/casaos/casaos.conf").exists():
        detected.append("casaos")
    if Path("/mnt/.ix-apps").exists():
        detected.append("truenas-scale")

    # Category C: Non-compose
    if Path("/umbrel/app-data").exists():
        detected.append("umbrel")
    if Path("/etc/unraid-version").exists():
        detected.append("unraid")

    # Also check compose file contents
    # x-casaos key → CasaOS
    # umbrel-app.yml sibling → Umbrel
    # /opt/stacks/ path → likely Dockge

    return detected
```

### Implementation: Risk Assessment

```python
TOOL_RISK = {
    # Category A: Container-isolated (HIGH RISK)
    "portainer": {
        "risk": "high",
        "reason": "env_file paths resolve inside Portainer container, not on host",
        "safe_pattern": "Use Portainer UI env vars or mount env dir into container",
    },
    "dockge": {
        "risk": "high",
        "reason": "env_file paths resolve inside Dockge container",
        "safe_pattern": "Keep .env co-located with compose.yaml in /opt/stacks/{stack}/",
    },
    "yacht": {
        "risk": "high",
        "reason": "env_file paths resolve inside Yacht container",
        "safe_pattern": "Keep .env in project directory under /config/compose/",
    },
    "komodo": {
        "risk": "high",
        "reason": "env_file paths resolve inside komodo-periphery container",
        "safe_pattern": "Mount .env into periphery, use /etc/komodo/.env",
    },
    # Category B: Host-native (LOW-MEDIUM RISK)
    "casaos": {
        "risk": "medium",
        "reason": "env_file works at runtime but breaks CasaOS UI import",
        "safe_pattern": "Use absolute paths; warn about UI import limitation",
    },
    "truenas-scale": {
        "risk": "low",
        "reason": "Standard Docker Compose on host, paths work normally",
        "safe_pattern": "Absolute paths on NAS filesystem work fine",
    },
    "runtipi": {
        "risk": "medium",
        "reason": "Paths work but Runtipi regenerates compose/env files on updates",
        "safe_pattern": "Use user-config overrides for persistence",
    },
    # Category C: Non-compose (N/A)
    "cosmos": {
        "risk": "n/a",
        "reason": "Does not use docker-compose or env_file at all",
        "safe_pattern": "env_file centralization not applicable",
    },
    "umbrel": {
        "risk": "high",
        "reason": "Compose files are patched at runtime; uses exports.sh instead",
        "safe_pattern": "env_file centralization not applicable",
    },
    "unraid": {
        "risk": "n/a",
        "reason": "Native Unraid uses XML templates, not compose files",
        "safe_pattern": "Only relevant for Docker Compose Manager plugin users",
    },
}
```

### Warning Messages

When ComposeArr detects a container-based stack manager:

```
WARNING: Detected {tool_name} stack manager.

{tool_name} runs Docker Compose inside a container, which means
env_file paths in your compose files are resolved inside that
container's filesystem — NOT on your host.

Centralizing env files to a host path will BREAK your deployments
unless you mount the centralized path into {tool_name}'s container.

Options:
  1. Skip env_file centralization (safest)
  2. View {tool_name}-specific setup instructions
  3. Proceed anyway (you know what you're doing)
```

---

## Safe Universal Patterns

### Pattern 1: Co-located .env (Safest — works everywhere)
```yaml
# .env file in same directory as compose.yaml
services:
  myapp:
    env_file:
      - .env
```
**Works with:** All tools that support env_file
**Limitation:** No centralization; each stack has its own .env

### Pattern 2: Inline environment (Most universal)
```yaml
services:
  myapp:
    environment:
      - TZ=${TZ}
      - PUID=${PUID}
```
**Works with:** Every tool, no exceptions
**Limitation:** Variables must be defined in .env or tool's UI

### Pattern 3: Tool-specific mounted path (Requires setup)
```yaml
# Only after user mounts the path into their stack manager
services:
  myapp:
    env_file:
      - /etc/komodo/.env  # Komodo example
```
**Works with:** Any tool after user configures the mount
**Limitation:** Requires per-tool setup documentation

---

## Testing Requirements

Before shipping secure-secrets feature:
- [x] Komodo — confirmed broken, confirmed fix (Judd's production)
- [ ] Test detection logic for Portainer
- [ ] Test detection logic for Dockge
- [ ] Test detection logic for CasaOS
- [ ] Verify warning messages are clear and actionable
- [ ] Test with direct `docker compose` (no manager) — should work normally
- [ ] Document required setup for each tool

---

## Implementation Checklist

Based on research findings:
- [ ] Add stack manager detection logic (`detect_stack_manager()`)
- [ ] Add risk assessment per detected tool
- [ ] Add warning messages before env_file centralization
- [ ] Make env centralization opt-in (not default)
- [ ] Add `--deployment-tool` CLI flag to skip auto-detection
- [ ] Add tool-specific guidance in secure-secrets flow
- [ ] Update secure-secrets to check for tool before proceeding
- [ ] Add tests for detection logic

---

## Conclusion

**Go/No-Go: CONDITIONAL GO**

The secure-secrets feature CAN ship, but with these requirements:

1. **env_file centralization must be opt-in** — never automatic
2. **Stack manager detection must run first** — warn users of risks
3. **Tool-specific guidance must be provided** — users need to know what to do
4. **Co-located `.env` should be the default recommendation** — safest universal option
5. **The "just works" path is inline `environment:` blocks** — always safe

The feature adds real value for direct `docker compose` users and users who understand their deployment model. The risk is only for users who don't realize their stack manager runs compose inside a container. Detection + warnings eliminate this risk.

**Beta can resume** once detection and warnings are implemented.
