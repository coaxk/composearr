# ComposeArr — Everest Expedition Plan

## Merged & Prioritized Feature Roadmap

Consolidated from Claude's strategic assessment + Judd's feedback/prioritization.
For web Claude to merge into the overall project plan.

---

## Priority 1 — CRITICAL (The Original Seeds + Viral Feature)

### P1.1: Resource Limits Rule (CA501)
**Status:** NOT IMPLEMENTED — Top priority per Judd (this was the original seed of ComposeArr)
**What:** Detect services missing `deploy.resources.limits` (CPU + memory). Flag containers with no resource constraints. Suggest sensible defaults based on known app profiles (e.g., Sonarr ~512M, Plex ~2G). Interactive flow: scan → show what's missing → reference known defaults → let user fine-tune per app → apply.
**Rules:**
- `CA501`: Missing memory limit
- `CA502`: Missing CPU limit
- `CA503`: Resource limits seem too high/low for known app (info-level)
**Fix capability:** Auto-add `deploy.resources.limits` with user-confirmed values.

### P1.2: Logging Driver / Log Rotation Rule (CA504)
**Status:** NOT IMPLEMENTED — Top priority per Judd (also original project seed)
**What:** Detect services with no logging configuration (defaults to json-file with NO rotation = disk fill). Detect missing `logging.options.max-size` and `max-file`. Suggest `json-file` with `max-size: 10m`, `max-file: 3` as sensible default.
**Rules:**
- `CA504`: No logging driver configured
- `CA505`: Logging driver configured but no rotation limits
**Fix capability:** Auto-add logging config block.

### P1.3: Stack Health Score (A+ through F)
**Status:** NOT IMPLEMENTED — Viral feature, gamification driver
**What:** After every audit, compute and display an overall stack grade (A+ to F) with category breakdown: Security, Reliability, Consistency, Network. Display prominently in TUI, include in all output formats. Track score history over time (ties into P2.3 audit history). Users will screenshot and share scores. Consider: badge generation for README ("My stack scores A+ on ComposeArr").
**Scoring:** Weighted formula — errors count heavy, warnings moderate, info light. Perfect stack = A+. Any unresolved error = max B. Customize weights in config.

### P1.4: Duplicate Environment Variables Rule (CA404)
**Status:** NOT IMPLEMENTED — Quick win, common real-world issue
**What:** Detect same env var defined multiple times in a service (last one wins silently). Detect conflicts between `environment:` and `env_file:` entries. Flag and show which value actually takes effect.
**Fix capability:** Remove duplicates, keep the intended value.

---

## Priority 2 — HIGH (Differentiating Features)

### P2.1: Watch Mode
**Status:** NOT IMPLEMENTED
**What:** `composearr watch` — monitor compose files for changes, re-lint on save, show live results. In TUI: persistent view with auto-updating issue list and score. Consider: deliver as Docker image for non-neckbeard users who want it always running.
**Charm opportunity:** Bubble Tea's reactive model makes this trivial — file watcher triggers Update(), UI re-renders.

### P2.2: Image Freshness / Upgrade Advisor
**Status:** NOT IMPLEMENTED — Not a big hill from current codebase
**What:** Query Docker Hub / GHCR / LSCR APIs for available tags. Show table: image, current tag, latest stable, latest any, age. Info-level only — never prescribe which version to use. Respects users on :latest, :dev, :beta, pinned versions.
**Nuanced tag handling (per Judd's feedback):**
- `:latest` → warn but don't prescribe version
- No tag (implicit latest) → warn harder
- `:dev`/`:nightly`/`:beta` → info: "development channel — intentional?"
- Pinned version → green
- Config option: `allow_latest_for: [app1, app2]` to whitelist
- Upgrade advisor *shows* what's available, doesn't demand action
**Network required:** Needs HTTP calls to registry APIs. Respect `no_network` config flag.

### P2.3: Audit History & Diff Between Audits
**Status:** NOT IMPLEMENTED
**What:** Save audit results to `.composearr/history/` (JSON, timestamped). Show trends: "Last week: 14 issues → This week: 6. You fixed 8." Sparkline or mini-chart in TUI. Ties directly into Stack Score tracking over time. CI use: fail pipeline if score dropped or issues increased.
**Pairs with:** P1.3 (Stack Score) — history tracks score progression.

### P2.4: Interactive Fix Preview (Diff View)
**Status:** NOT IMPLEMENTED
**What:** Before applying any fix, show actual red/green diff of what will change in the YAML. Line-by-line, scrollable. User confirms after seeing exact changes. Builds trust in the fix/secrets workflows. Separate from runtime comparison (P2.5).
**Charm opportunity:** Split-pane diff viewer with Lip Gloss styling.

### P2.5: Live Runtime Comparison
**Status:** NOT IMPLEMENTED
**What:** Connect to Docker socket. Compare compose YAML vs actually running containers. Detect: wrong ports, different image versions, services defined but not running, running containers not in compose, env var mismatches. Standalone feature AND integrated into fix flow (pre-apply sanity check per Judd's suggestion).
**Pairs with:** P2.4 (diff preview) — runtime diff shown alongside YAML diff before fixes.

### P2.6: Named Volumes vs Bind Mounts Rule (CA701)
**Status:** NOT IMPLEMENTED
**What:** Detect bind mounts that should be named volumes (better for portability, backup, Docker management). Detect named volumes that reference non-existent volume definitions. Detect volume definitions with no driver specified.
**Rules:**
- `CA701`: Bind mount where named volume recommended
- `CA702`: Referenced volume not defined in volumes section

---

## Priority 3 — MEDIUM (Deepening the Platform)

### P3.1: Scaffold...arr (Stack Templates)
**Status:** NOT IMPLEMENTED — "we already have the scaffolding for this practically"
**What:** `composearr init sonarr` — generate best-practice compose file for known apps. Healthcheck, restart policy, proper volumes, .env file, pinned image, resource limits, logging config — everything ComposeArr would audit for, baked in from the start. Template library for top 50+ homelab apps. Community-contributed templates.
**Templates include:** compose.yaml + .env + README with app-specific notes.

### P3.2: Remote Host Scanning (SSH)
**Status:** NOT IMPLEMENTED — Must-have for multi-host homelab users
**What:** SSH into remote hosts, scan their stacks, report back. TUI: add/manage remote hosts in config, switch between local and remote. Supports users running Portainer/Komodo with remote agents, socket proxy setups. Save remote hosts in `.composearr.yml`.
**Pairs with:** P3.6 (Multi-Stack Dashboard) — remote stacks appear alongside local.

### P3.3: Compose from Running Containers (Capture)
**Status:** NOT IMPLEMENTED — "purely all about yamls" fits perfectly
**What:** `composearr capture` — inspect running containers via Docker socket, generate compose files. The reverse of `docker compose up`. Migration tool for users who started with `docker run` commands. Life-saver for disaster recovery (Judd's SABnzbd/subgen incident). Output: clean compose.yaml following all ComposeArr best practices.

### P3.4: Orphaned Resources Detection (The Orphanage)
**Status:** NOT IMPLEMENTED — "identify and guide but don't become Portainer"
**What:** Detect orphaned volumes, networks, and configs referenced in compose but not defined (or defined but not used). Report only — NO prune/delete buttons. Guide users on what to clean up and how, but stay firmly in the "advisor" lane.
**Philosophy:** Identify and educate. Never auto-delete infrastructure resources.

### P3.5: Capability Dropping Rule (CA801)
**Status:** NOT IMPLEMENTED
**What:** Detect containers running with default Linux capabilities. Suggest `cap_drop: [ALL]` + `cap_add: [only needed]`. Known app profiles: which caps each common app actually needs. Educational: explain what capabilities are and why dropping them matters. Part of broader security hardening guidance.
**Rules:**
- `CA801`: No capability restrictions defined
- `CA802`: Running with `privileged: true` (high severity)

### P3.6: Multi-Stack Dashboard
**Status:** NOT IMPLEMENTED
**What:** Dashboard view for users with multiple stack directories. Each stack: name, score, issue count, last audit date, host (local/remote). One-glance infrastructure overview.
**Pairs with:** P3.2 (Remote Hosts) — remote stacks appear in dashboard.
**Charm opportunity:** Table with colored status indicators, sparklines for score history.

### P3.7: Read-Only Filesystem Rule (CA803)
**Status:** NOT IMPLEMENTED
**What:** Detect containers that could run with `read_only: true` but don't. Suggest read-only root with explicit tmpfs mounts for `/tmp`, `/run`, etc. Known app profiles for which paths need write access. Security hardening that most homelabbers don't know exists.

### P3.8: Network Mode Conflict Improvements
**Status:** PARTIALLY IMPLEMENTED — "we identify but drop the baby"
**What:** Extend existing network detection to actually resolve conflicts. Guide users through fixes. Detect incompatible network modes between dependent services. DNS configuration issues rolled into this family.
**Rules:**
- Existing network rules enhanced with fix guidance
- `CA304`: DNS configuration issues (missing/conflicting DNS settings on bridge networks)

---

## Priority 4 — FUTURE (Nitrous Oxide Phase)

### P4.1: Plugin / Custom Rules API
**Status:** NOT IMPLEMENTED — "further down the line as userbase solidifies"
**What:** Simple Python API (now), Go interface (post-Charm rewrite). Receive parsed compose dict, return issues list. Community rules package: `composearr-rules-contrib`. Plugin discovery, loading, config integration.
**Timing:** After core rule count hits 25+ and user base is established.

### P4.2: Health Report Export
**Status:** NOT IMPLEMENTED
**What:** Generate markdown/HTML health report. Stack name, date, score, all issues with explanations, topology diagram. For: homelab wikis, r/selfhosted posts, CTO desk drops, GitHub issue evidence. History + score trends visualized in reports.
**Formats:** Markdown, HTML, PDF (via markdown → PDF).

### P4.3: Docker Image Distribution
**Status:** NOT IMPLEMENTED
**What:** ComposeArr as a Docker image for users who want watch mode always running without tmux. Mount stack directory as volume, expose web UI or just run TUI in attached terminal. Lower barrier to entry for non-terminal-native users.

### P4.4: Documentation Site
**Status:** NOT IMPLEMENTED
**What:** Full docs site (likely Astro or MkDocs). Rule reference, config guide, template library, plugin API docs, tutorials. In-app config guide covers the gap for now.

---

## New Rule Summary (to add to rule engine)

| Rule ID | Name | Priority | Category |
|---------|------|----------|----------|
| CA501 | missing-memory-limit | P1 | Resources |
| CA502 | missing-cpu-limit | P1 | Resources |
| CA503 | resource-limits-unusual | P1 | Resources |
| CA504 | no-logging-config | P1 | Reliability |
| CA505 | no-log-rotation | P1 | Reliability |
| CA404 | duplicate-env-vars | P1 | Consistency |
| CA701 | prefer-named-volumes | P2 | Best Practice |
| CA702 | undefined-volume-ref | P2 | Best Practice |
| CA801 | no-capability-restrictions | P3 | Security |
| CA802 | privileged-mode | P3 | Security |
| CA803 | no-read-only-root | P3 | Security |
| CA304 | dns-configuration | P3 | Network |

Current: 13 rules → Target: 25 rules (nearly doubles coverage)

---

## Implementation Sequence

**Sprint 1 (NOW):** P1.1 (Resource Limits) + P1.2 (Logging) + P1.4 (Dupe Env Vars)
— The original seeds. These should have been first. Fix that now.

**Sprint 2:** P1.3 (Stack Score) + P2.3 (Audit History)
— The viral + retention combo. Score needs history to track progress.

**Sprint 3:** P2.2 (Image Freshness) + P2.4 (Interactive Diff Preview)
— Recurring value + trust building for fix workflows.

**Sprint 4:** P2.1 (Watch Mode) + P2.6 (Named Volumes)
— The "leave it running" feature + more rules.

**Sprint 5:** P2.5 (Runtime Comparison) + P3.4 (Orphanage) + P3.5 (Capabilities) + P3.7 (Read-Only) + P3.8 (Network Improvements)
— Docker socket integration + security hardening rules.

**Sprint 6:** P3.1 (Scaffold...arr) + P3.3 (Capture)
— Template generation + reverse engineering. Both compose file generators.

**Sprint 7:** P3.2 (Remote Hosts) + P3.6 (Multi-Stack Dashboard)
— Multi-host support. These pair naturally.

**Sprint 8+:** P4.x (Plugins, Reports, Docker Image, Docs Site)
— The nitrous oxide phase.

---

## Tag Handling Strategy (Refined)

NOT a simple "don't use latest" — nuanced approach:
- `:latest` explicit → warning (but don't prescribe version)
- No tag (implicit latest) → stronger warning (user may not realize)
- `:dev`/`:nightly`/`:beta` → info: "development channel — intentional?"
- Pinned version → all good
- Config: `allow_latest_for: [app1, app2]` whitelist
- Upgrade advisor shows available versions as FYI, never demands action
- Respects: latest-lovers, dev-testers, version-pinners, legacy-dependency users

---

*Generated by ComposeArr Everest Expedition Planning Session*
*Tenzing Norgay reporting for duty*
