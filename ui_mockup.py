"""
ComposeArr UI Mockup — Run this to see what the tool will look like.

Usage:
    python ui_mockup.py              # Show all mockups
    python ui_mockup.py audit        # Just the audit output
    python ui_mockup.py ports        # Just the ports table
    python ui_mockup.py init         # Just the init flow
    python ui_mockup.py summary      # Just the summary
    python ui_mockup.py diff         # Just the diff preview
    python ui_mockup.py secrets      # Just the secrets scan
"""

import sys
import time
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout
from rich.align import Align
from rich import box

import io, os
# Force UTF-8 output on Windows
if os.name == 'nt':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
console = Console(force_terminal=True, color_system="truecolor")

# ─────────────────────────────────────────────────────────────────
# MOCKUP 1: Main Audit Output (ruff-inspired with code context)
# ─────────────────────────────────────────────────────────────────

def show_audit():
    console.print()
    console.print("[bold cyan]composearr[/] v0.1.0\n")

    # File 1: gluetun
    console.print(Rule("[bold white]gluetun/compose.yaml[/]", align="left", style="dim"))
    console.print()
    console.print("  [dim]16 │[/]     environment:")
    console.print("  [dim]17 │[/]       - PUID=0")
    console.print("  [dim]18 │[/]       - WIREGUARD_PRIVATE_KEY=bijL6fcCeVv25izRy3Jsea...")
    console.print("  [dim]   │[/]         [red]~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/]")
    console.print("  [dim]   │[/]         [bold red]✖ CA101[/] [red](error)[/]: Secret value hardcoded in environment block")
    console.print("  [dim]   │[/]         [green]Fix:[/] Move to .env and reference as [cyan]${{WIREGUARD_PRIVATE_KEY}}[/]")
    console.print()
    console.print("  [dim]20 │[/]     image: qmcgaw/gluetun:v3  [dim]✔ (pinned)[/]")
    console.print()

    # File 2: plex
    console.print(Rule("[bold white]plex/compose.yaml[/]", align="left", style="dim"))
    console.print()
    console.print("  [dim] 3 │[/]     image: lscr.io/linuxserver/plex:latest")
    console.print("  [dim]   │[/]            [yellow]~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/]")
    console.print("  [dim]   │[/]            [bold yellow]⚠ CA001[/] [yellow](warning)[/]: Image uses :latest tag")
    console.print("  [dim]   │[/]            [green]Suggested:[/] lscr.io/linuxserver/plex:1.41.3")
    console.print()

    # File 3: qbittorrent
    console.print(Rule("[bold white]qbittorrent/compose.yaml[/]", align="left", style="dim"))
    console.print()
    console.print("  [dim]28 │[/]     healthcheck:")
    console.print("  [dim]29 │[/]       test: exit 0")
    console.print("  [dim]   │[/]             [yellow]~~~~~~[/]")
    console.print("  [dim]   │[/]             [bold yellow]⚠ CA202[/] [yellow](warning)[/]: Healthcheck always passes — provides no health info")
    console.print("  [dim]   │[/]             [green]Use:[/] [cyan]curl -sf http://localhost:8080/api/v2/app/version || exit 1[/]")
    console.print()

    # File 4: sabnzbd
    console.print(Rule("[bold white]sabnzbd/compose.yaml[/]", align="left", style="dim"))
    console.print()
    console.print("  [dim] 5 │[/]     image: ghcr.io/home-operations/sabnzbd:latest")
    console.print("  [dim]   │[/]            [yellow]~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/]")
    console.print("  [dim]   │[/]            [bold yellow]⚠ CA001[/] [yellow](warning)[/]: Image uses :latest tag")
    console.print()
    console.print("  [dim]   │[/]     [dim italic]no restart policy defined[/]")
    console.print("  [dim]   │[/]            [bold yellow]⚠ CA203[/] [yellow](warning)[/]: Missing restart policy")
    console.print("  [dim]   │[/]            [green]Fix:[/] Add [cyan]restart: unless-stopped[/]")
    console.print()

    # Cross-file section
    console.print(Rule("[bold white]Cross-file checks[/]", align="left", style="dim"))
    console.print()
    console.print("  [bold red]✖ CA401[/] [red](error)[/]: PUID/PGID mismatch across stack")
    console.print("    [dim]├─[/] PUID=[bold]1000[/] in sonarr, radarr, bazarr, prowlarr, plex")
    console.print("    [dim]├─[/] PUID=[bold]568[/]  in qbittorrent, sabnzbd")
    console.print("    [dim]└─[/] PUID=[bold]0[/]    in gluetun, huntarr, decypharr")
    console.print("    [green]All media stack services should use the same PUID for hardlinks[/]")
    console.print("    [blue underline]https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/[/]")
    console.print()
    console.print("  [bold yellow]⚠ CA402[/] [yellow](warning)[/]: UMASK inconsistent across *arr services")
    console.print("    [dim]├─[/] UMASK=[bold]022[/] in sonarr, radarr, bazarr")
    console.print("    [dim]└─[/] UMASK=[bold]002[/] in qbittorrent")
    console.print("    [green]TRaSH recommends UMASK=002 for all services (group write for hardlinks)[/]")
    console.print()

    # Summary
    show_summary()


def show_summary():
    console.print(Rule("[bold white]Summary[/]", style="dim"))
    console.print()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Files scanned:", "[bold]35[/] compose files ([bold]42[/] services)")
    table.add_row("Issues found:", "[bold red]4 errors[/], [bold yellow]8 warnings[/], [bold blue]3 info[/]")
    console.print(table)

    console.print()
    console.print("  [bold red]✖[/]  4 errors    — [red]must fix[/]")
    console.print("  [bold yellow]⚠[/]  8 warnings — [yellow]recommended[/]")
    console.print("  [bold blue]ℹ[/]  3 info     — [blue]optional[/]")
    console.print()
    console.print("  [bold green]►[/] 6 issues auto-fixable with [bold cyan]composearr audit --fix[/]")
    console.print()


# ─────────────────────────────────────────────────────────────────
# MOCKUP 2: Port Allocation Table
# ─────────────────────────────────────────────────────────────────

def show_ports():
    console.print()
    console.print("[bold cyan]composearr[/] ports\n")

    table = Table(
        title="Port Allocation Map",
        box=box.ROUNDED,
        title_style="bold white",
        border_style="dim",
        header_style="bold",
        row_styles=["", "dim"],
    )
    table.add_column("PORT", style="bold cyan", justify="right")
    table.add_column("PROTO", style="dim")
    table.add_column("SERVICE", style="bold green")
    table.add_column("FILE", style="dim")
    table.add_column("BINDING", style="white")
    table.add_column("", style="yellow")  # warnings

    ports_data = [
        ("2375", "tcp", "socketproxy", "socketproxy/compose.yaml", "0.0.0.0", "⚠ Docker API"),
        ("3000", "tcp", "subsyncarrplus", "subsyncarrplus/compose.yaml", "0.0.0.0", ""),
        ("3001", "tcp", "meshmonitor", "meshmonitor/compose.yaml", "0.0.0.0", ""),
        ("5341", "tcp", "seq", "seq/compose.yaml", "0.0.0.0", ""),
        ("7878", "tcp", "radarr", "radarr/compose.yaml", "0.0.0.0", ""),
        ("8000", "tcp", "komodo-core", "komodo/compose.yaml", "0.0.0.0", ""),
        ("8080", "tcp", "glances", "glances/compose.yaml", "0.0.0.0", ""),
        ("8085", "tcp", "termix", "termix/compose.yaml", "0.0.0.0", ""),
        ("8095", "tcp", "qbittorrent", "qbittorent/compose.yaml", "0.0.0.0", ""),
        ("8787", "tcp", "bazarr", "bazarr/compose.yaml", "0.0.0.0", ""),
        ("8888", "tcp", "gluetun", "gluetun/compose.yaml", "0.0.0.0", ""),
        ("8889", "tcp", "signal-api", "signal-api/compose.yaml", "0.0.0.0", ""),
        ("8989", "tcp", "sonarr", "sonarr/compose.yaml", "0.0.0.0", ""),
        ("9696", "tcp", "prowlarr", "prowlarr/compose.yaml", "0.0.0.0", ""),
        ("30055", "tcp", "sabnzbd", "sabnzbd/compose.yaml", "0.0.0.0", ""),
        ("32400", "tcp", "plex", "plex/compose.yaml", "0.0.0.0", ""),
    ]

    for row in ports_data:
        table.add_row(*row)

    console.print(table)
    console.print()
    console.print("  [yellow]⚠ 2375[/] (socketproxy): Docker API exposed on all interfaces — bind to [cyan]127.0.0.1[/]")
    console.print("  [bold green]✔[/] No port conflicts detected")
    console.print()
    console.print(f"  [dim]{len(ports_data)} host ports in use across 35 compose files[/]")
    console.print()


# ─────────────────────────────────────────────────────────────────
# MOCKUP 3: Init Flow
# ─────────────────────────────────────────────────────────────────

def show_init():
    console.print()
    console.print("[bold cyan]composearr[/] init\n")

    # Simulated scanning animation
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning directory...", total=35)
        for i in range(35):
            time.sleep(0.03)
            progress.update(task, advance=1)

    console.print("  [green]✔[/] Found [bold]35[/] compose files, [bold]42[/] services\n")

    # Profile selection mockup
    console.print("  [bold]?[/] Select a profile:")
    console.print("    [bold cyan]❯ arrstack[/]    — Media server rules (Sonarr, Radarr, TRaSH compliance)")
    console.print("      [dim]homelab[/]     — General self-hosted rules")
    console.print("      [dim]production[/]  — Strict production-readiness")
    console.print("      [dim]security[/]    — Security-focused only")
    console.print("      [dim]minimal[/]     — Just the essentials")
    console.print()

    # Strictness selection mockup
    console.print("  [bold]?[/] Strictness:")
    console.print("    [bold cyan]❯ recommended[/] — Errors for critical, warnings for best practices")
    console.print("      [dim]strict[/]      — Most rules as errors (CI mode)")
    console.print("      [dim]relaxed[/]     — Mostly warnings")
    console.print()

    time.sleep(0.3)
    console.print("  [green]✔[/] Created [bold].composearr.yml[/]\n")

    # Config preview
    config_yaml = """\
# .composearr.yml — generated by composearr init
profile: arrstack
severity: warning

rules:
  CA001: warning     # no-latest-tag
  CA101: error       # no-inline-secrets
  CA201: warning     # require-healthcheck
  CA203: warning     # require-restart-policy
  CA301: error       # port-conflict
  CA401: error       # puid-pgid-mismatch

trusted_registries:
  - lscr.io
  - ghcr.io
  - docker.io"""

    console.print(Panel(
        Syntax(config_yaml, "yaml", theme="monokai", line_numbers=False),
        title="[bold].composearr.yml[/]",
        border_style="dim",
        width=60,
    ))

    console.print()
    console.print("  Quick start:")
    console.print("    [bold cyan]composearr audit[/]              # Run audit")
    console.print("    [bold cyan]composearr audit --fix[/]        # Auto-fix issues")
    console.print("    [bold cyan]composearr audit --diff[/]       # Preview fixes")
    console.print("    [bold cyan]composearr ports[/]              # View port map")
    console.print()


# ─────────────────────────────────────────────────────────────────
# MOCKUP 4: Diff Preview (--diff mode)
# ─────────────────────────────────────────────────────────────────

def show_diff():
    console.print()
    console.print("[bold cyan]composearr[/] audit --diff\n")
    console.print("[dim]Showing proposed changes (dry run — no files modified)\n[/]")

    # Diff 1: Adding restart policy
    diff1 = """\
--- sabnzbd/compose.yaml
+++ sabnzbd/compose.yaml (fixed)
@@ -4,6 +4,7 @@
     image: ghcr.io/home-operations/sabnzbd:latest
     container_name: sabnzbd
+    restart: unless-stopped
     environment:
       PUID: "568"
       PGID: "568\""""

    console.print(Rule("[bold white]sabnzbd/compose.yaml[/] — CA203 require-restart-policy", align="left", style="dim"))
    console.print(Syntax(diff1, "diff", theme="monokai", line_numbers=False))
    console.print()

    # Diff 2: Moving secret to env_file reference
    diff2 = """\
--- gluetun/compose.yaml
+++ gluetun/compose.yaml (fixed)
@@ -16,7 +16,7 @@
     environment:
       - PUID=0
-      - WIREGUARD_PRIVATE_KEY=bijL6fcCeVv25izRy3JseahatW9rsd0eCpo5aLricRI=
+      - WIREGUARD_PRIVATE_KEY=${WIREGUARD_PRIVATE_KEY}
       - VPN_SERVICE_PROVIDER=custom"""

    console.print(Rule("[bold white]gluetun/compose.yaml[/] — CA101 no-inline-secrets", align="left", style="dim"))
    console.print(Syntax(diff2, "diff", theme="monokai", line_numbers=False))
    console.print()

    # Diff 3: Adding log rotation
    diff3 = """\
--- prowlarr/compose.yaml
+++ prowlarr/compose.yaml (fixed)
@@ -18,3 +18,8 @@
     networks:
       - safe-bridge
+    logging:
+      driver: json-file
+      options:
+        max-size: "10m"
+        max-file: "3\""""

    console.print(Rule("[bold white]prowlarr/compose.yaml[/] — CA205 require-log-rotation", align="left", style="dim"))
    console.print(Syntax(diff3, "diff", theme="monokai", line_numbers=False))
    console.print()

    # Summary
    console.print(Rule(style="dim"))
    console.print()
    console.print("  [bold green]3 files[/] would be modified ([bold]3 fixes[/] applied)")
    console.print("  [bold]3 issues[/] remain that require manual intervention")
    console.print()
    console.print("  Run [bold cyan]composearr audit --fix[/] to apply these changes")
    console.print()


# ─────────────────────────────────────────────────────────────────
# MOCKUP 5: Secrets Scan
# ─────────────────────────────────────────────────────────────────

def show_secrets():
    console.print()
    console.print("[bold cyan]composearr[/] secrets\n")

    table = Table(
        title="Secrets & Credentials Found",
        box=box.ROUNDED,
        title_style="bold white",
        border_style="dim",
        header_style="bold",
    )
    table.add_column("", width=2)
    table.add_column("VARIABLE", style="bold")
    table.add_column("LOCATION", style="dim")
    table.add_column("TYPE", style="cyan")
    table.add_column("RISK")

    table.add_row("[red]✖[/]", "WIREGUARD_PRIVATE_KEY", "gluetun/compose.yaml:18", "WireGuard Key", "[bold red]CRITICAL[/] — inline")
    table.add_row("[red]✖[/]", "WIREGUARD_PRIVATE_KEY", ".env:37", "WireGuard Key", "[yellow]duplicated[/]")
    table.add_row("[red]✖[/]", "MYJD_PASSWORD", "jdownloader2/compose.yaml:14", "Password", "[bold red]CRITICAL[/] — inline")
    table.add_row("[red]✖[/]", "TERMIX_DB_ENCRYPTION_KEY", "termix/compose.yaml:15", "Encryption Key", "[bold red]CRITICAL[/] — inline")
    table.add_row("[red]✖[/]", "JWT_SECRET", "termix/compose.yaml:16", "JWT Secret", "[bold red]CRITICAL[/] — inline")
    table.add_row("[yellow]⚠[/]", "KOMODO_JWT_SECRET", ".env:12", "JWT Secret", "[yellow]weak value[/]")
    table.add_row("[yellow]⚠[/]", "PLEX_TOKEN", ".env:28", "API Token", "[yellow]high entropy[/]")
    table.add_row("[yellow]⚠[/]", "SONARR_API_KEY", ".env:19", "API Key", "[dim]in .env (OK)[/]")
    table.add_row("[yellow]⚠[/]", "RADARR_API_KEY", ".env:20", "API Key", "[dim]in .env (OK)[/]")
    table.add_row("[dim]ℹ[/]", "REALDEBRID_API_KEY", ".env:35", "API Key", "[dim]in .env (OK)[/]")

    console.print(table)
    console.print()
    console.print("  [bold red]4 CRITICAL[/] — Secrets hardcoded inline in compose files")
    console.print("  [bold yellow]2 WARNING[/]  — Weak or reused secret values")
    console.print("  [bold dim]4 OK[/]       — Secrets properly stored in .env file")
    console.print()
    console.print("  [bold green]►[/] Run [bold cyan]composearr audit --fix[/] to move inline secrets to .env")
    console.print()


# ─────────────────────────────────────────────────────────────────
# MOCKUP 6: Rules List
# ─────────────────────────────────────────────────────────────────

def show_rules():
    console.print()
    console.print("[bold cyan]composearr[/] rules\n")

    tree = Tree("[bold]Available Rules[/]", guide_style="dim")

    images = tree.add("[bold cyan]Images[/] (CA0xx)")
    images.add("[bold]CA001[/] [yellow]warning[/]  no-latest-tag         Image uses :latest or has no tag  [green][fixable][/]")
    images.add("[bold]CA002[/] [blue]info[/]     no-digest-pin         No @sha256: digest pin")
    images.add("[bold]CA003[/] [blue]info[/]     untrusted-registry    Image from unknown registry")

    security = tree.add("[bold red]Security[/] (CA1xx)")
    security.add("[bold]CA101[/] [red]error[/]    no-inline-secrets     Secret hardcoded in environment  [green][fixable][/]")
    security.add("[bold]CA102[/] [red]error[/]    no-privileged         Container in privileged mode")
    security.add("[bold]CA103[/] [yellow]warning[/]  no-docker-sock        Docker socket mounted")
    security.add("[bold]CA104[/] [red]error[/]    no-cap-add-all        cap_add: ALL grants all caps")
    security.add("[bold]CA105[/] [yellow]warning[/]  unbound-port          Port on 0.0.0.0 (all interfaces)  [green][fixable][/]")

    reliability = tree.add("[bold yellow]Reliability[/] (CA2xx)")
    reliability.add("[bold]CA201[/] [yellow]warning[/]  require-healthcheck   No healthcheck defined")
    reliability.add("[bold]CA202[/] [yellow]warning[/]  no-fake-healthcheck   Healthcheck is exit 0")
    reliability.add("[bold]CA203[/] [yellow]warning[/]  require-restart       No restart policy  [green][fixable][/]")
    reliability.add("[bold]CA204[/] [yellow]warning[/]  require-resources     Missing memory/CPU limits")
    reliability.add("[bold]CA205[/] [blue]info[/]     require-log-rotation  No log rotation configured  [green][fixable][/]")

    networking = tree.add("[bold magenta]Networking[/] (CA3xx)")
    networking.add("[bold]CA301[/] [red]error[/]    port-conflict         Same port used by multiple services  [bold white][cross-file][/]")
    networking.add("[bold]CA302[/] [yellow]warning[/]  no-host-network       Uses network_mode: host")
    networking.add("[bold]CA303[/] [blue]info[/]     no-default-network    No explicit network defined")

    consistency = tree.add("[bold green]Consistency[/] (CA4xx)")
    consistency.add("[bold]CA401[/] [red]error[/]    puid-pgid-mismatch    PUID/PGID differ across services  [bold white][cross-file][/]")
    consistency.add("[bold]CA402[/] [yellow]warning[/]  umask-inconsistent    UMASK values differ  [bold white][cross-file][/]")
    consistency.add("[bold]CA403[/] [yellow]warning[/]  missing-timezone      TZ not set  [green][fixable][/]")

    arrstack = tree.add("[bold #ff79c6]Arr Stack[/] (CA6xx)")
    arrstack.add("[bold]CA601[/] [yellow]warning[/]  hardlink-path-mismatch  Containers lack shared /data root  [bold white][cross-file][/]")

    console.print(tree)
    console.print()
    console.print("  [bold]20 rules[/] available ([green]6 fixable[/], [bold white]4 cross-file[/])")
    console.print("  Configure in [bold].composearr.yml[/] or with [bold]--rule[/] / [bold]--ignore[/] flags")
    console.print()


# ─────────────────────────────────────────────────────────────────
# MOCKUP 7: Progress Animation (scanning phase)
# ─────────────────────────────────────────────────────────────────

def show_scanning():
    console.print()
    console.print("[bold cyan]composearr[/] audit C:\\DockerContainers\n")

    files = [
        "bazarr", "beszel", "decypharr", "glances", "gluetun",
        "huntarr", "jdownloader2", "komodo", "meshmonitor", "overseerr",
        "plex", "prowlarr", "qbittorrent", "radarr", "sabnzbd",
        "seq", "signal-api", "sonarr", "socketproxy", "subgen",
        "subsyncarrplus", "tautulli", "termix", "vector", "whisparr",
    ]

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}[/]"),
        BarColumn(bar_width=30, style="dim", complete_style="cyan"),
        TextColumn("[dim]{task.completed}/{task.total}[/]"),
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning compose files...", total=len(files))
        for f in files:
            progress.update(task, description=f"Scanning [cyan]{f}/compose.yaml[/]...")
            time.sleep(0.08)
            progress.update(task, advance=1)

    console.print("  [green]✔[/] Scanned [bold]25 compose files[/] ([bold]34 services[/]) in [bold]0.42s[/]")
    console.print("  [green]✔[/] Cross-file analysis complete\n")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def show_all():
    console.print(Panel(
        Align.center(
            Text.from_markup(
                "[bold cyan]ComposeArr[/] — UI Mockup Preview\n"
                "[dim]What the tool will look like in your terminal[/]"
            )
        ),
        border_style="cyan",
        padding=(1, 4),
    ))

    sections = [
        ("SCANNING ANIMATION", show_scanning),
        ("AUDIT OUTPUT (main view)", show_audit),
        ("DIFF PREVIEW (--diff mode)", show_diff),
        ("PORT ALLOCATION TABLE", show_ports),
        ("SECRETS SCAN", show_secrets),
        ("RULES LIST", show_rules),
        ("INIT FLOW", show_init),
    ]

    for title, fn in sections:
        console.print()
        console.print(Panel(f"[bold]{title}[/]", border_style="cyan", width=60))
        fn()
        console.print()
        console.input("[dim]Press Enter for next mockup...[/]")

    console.print(Panel(
        "[bold green]That's the ComposeArr UI![/]\n\n"
        "All output uses [bold cyan]Rich[/] — works in Windows Terminal, iTerm2, and any modern terminal.\n"
        "Colors auto-degrade on basic terminals. [dim]Respects NO_COLOR env var.[/]",
        border_style="green",
        padding=(1, 2),
    ))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    dispatch = {
        "all": show_all,
        "audit": show_audit,
        "ports": show_ports,
        "init": show_init,
        "diff": show_diff,
        "secrets": show_secrets,
        "rules": show_rules,
        "summary": show_summary,
        "scan": show_scanning,
    }
    fn = dispatch.get(cmd, show_all)
    fn()
