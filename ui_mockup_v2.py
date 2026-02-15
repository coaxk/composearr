"""
ComposeArr UI Mockup v2 — Beszel-Inspired Design
═════════════════════════════════════════════════

Restrained elegance: muted colors, thin borders, generous whitespace.
No flashy effects. Every pixel conveys information.

Usage:
    python ui_mockup_v2.py              # Full walkthrough
    python ui_mockup_v2.py audit        # Audit output
    python ui_mockup_v2.py dashboard    # Dashboard overview
    python ui_mockup_v2.py ports        # Port allocation
    python ui_mockup_v2.py secrets      # Secrets scan
    python ui_mockup_v2.py diff         # Diff preview
    python ui_mockup_v2.py rules        # Rules list
    python ui_mockup_v2.py init         # Init flow
"""

import sys
import io
import os
import time

if os.name == 'nt':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.align import Align
from rich.style import Style
from rich import box

# ─── Beszel-inspired color tokens ───────────────────────────────
# Muted, desaturated palette. Borders over shadows. Near-black bg.
C_BG       = "#0f0f12"
C_BORDER   = "#27272a"
C_TEXT     = "#fafafa"
C_MUTED    = "#71717a"
C_DIM      = "#3f3f46"
C_OK       = "#22c55e"
C_WARN     = "#f59e0b"
C_ERR      = "#ef4444"
C_INFO     = "#3b82f6"
C_ACCENT   = "#8884d8"  # soft purple
C_CYAN     = "#67e8f9"
C_TEAL     = "#2dd4bf"

console = Console(force_terminal=True, color_system="truecolor")

def muted(text):
    return f"[{C_MUTED}]{text}[/]"

def dim(text):
    return f"[{C_DIM}]{text}[/]"

def ok(text):
    return f"[{C_OK}]{text}[/]"

def warn(text):
    return f"[{C_WARN}]{text}[/]"

def err(text):
    return f"[{C_ERR}]{text}[/]"

def info(text):
    return f"[{C_INFO}]{text}[/]"

def accent(text):
    return f"[{C_ACCENT}]{text}[/]"

def header_bar():
    """Top bar — mimics Beszel's top nav."""
    left = Text.from_markup(f"  [bold {C_TEAL}]◆[/] [bold]composearr[/]  {muted('v0.1.0')}")
    console.print(Panel(
        left,
        border_style=Style(color=C_BORDER),
        box=box.HORIZONTALS,
        padding=(0, 0),
    ))
    console.print()


# ─────────────────────────────────────────────────────────────────
# DASHBOARD — Beszel-style score cards + overview
# ─────────────────────────────────────────────────────────────────

def show_dashboard():
    header_bar()

    # Score cards row
    score_card = Panel(
        Align.center(Text.from_markup(
            f"\n[bold {C_TEXT}]Health Score[/]\n"
            f"[bold {C_ACCENT} on {C_BG}] 74[/][{C_MUTED}]/100[/]\n"
            f"\n{muted('needs attention')}\n"
        )),
        border_style=Style(color=C_BORDER),
        box=box.ROUNDED,
        width=24,
        padding=(0, 1),
    )

    errors_card = Panel(
        Align.center(Text.from_markup(
            f"\n[bold {C_ERR}]4[/] {muted('errors')}\n"
            f"[bold {C_WARN}]8[/] {muted('warnings')}\n"
            f"[bold {C_INFO}]3[/] {muted('info')}\n"
            f"\n{ok('6 fixable')}\n"
        )),
        border_style=Style(color=C_BORDER),
        box=box.ROUNDED,
        width=24,
        padding=(0, 1),
    )

    services_card = Panel(
        Align.center(Text.from_markup(
            f"\n[bold {C_TEXT}]42[/] {muted('services')}\n"
            f"[bold {C_TEXT}]35[/] {muted('files')}\n"
            f"\n"
            f"[{C_OK}]\u25cf[/] {muted('28 clean')}  [{C_ERR}]\u25cf[/] {muted('9 issues')}  [{C_MUTED}]\u25cf[/] {muted('5 skipped')}\n"
            f"\n"
        )),
        border_style=Style(color=C_BORDER),
        box=box.ROUNDED,
        width=24,
        padding=(0, 1),
    )

    console.print(Columns([score_card, errors_card, services_card], padding=1))
    console.print()

    # Service status grid — Beszel-style compact cards
    console.print(f"  [{C_MUTED}]Services[/]")
    console.print()

    svc_table = Table(
        box=None,
        show_header=True,
        header_style=f"bold {C_MUTED}",
        padding=(0, 2),
        pad_edge=True,
        show_edge=False,
    )
    svc_table.add_column("", width=2)
    svc_table.add_column("SERVICE", style=f"bold {C_TEXT}", min_width=16)
    svc_table.add_column("IMAGE", style=C_MUTED, max_width=36)
    svc_table.add_column("ISSUES", justify="right")
    svc_table.add_column("PORT", justify="right", style=C_DIM)

    services = [
        ("\u25cf", C_ERR,  "gluetun",       "qmcgaw/gluetun:v3",                  err("2"), "8888"),
        ("\u25cf", C_WARN, "plex",          "lscr.io/linuxserver/plex:latest",     warn("1"), "32400"),
        ("\u25cf", C_WARN, "qbittorrent",   "ghcr.io/hotio/qbittorrent:latest",   warn("1"), "8095"),
        ("\u25cf", C_WARN, "sabnzbd",       "ghcr.io/home-operations/sabnzbd:latest", warn("2"), "30055"),
        ("\u25cf", C_OK,   "sonarr",        "lscr.io/linuxserver/sonarr:latest",   warn("1"), "8989"),
        ("\u25cf", C_OK,   "radarr",        "lscr.io/linuxserver/radarr:latest",   warn("1"), "7878"),
        ("\u25cf", C_OK,   "prowlarr",      "lscr.io/linuxserver/prowlarr:latest", muted("0"), "9696"),
        ("\u25cf", C_OK,   "bazarr",        "lscr.io/linuxserver/bazarr:latest",   muted("0"), "8787"),
        ("\u25cf", C_OK,   "overseerr",     "lscr.io/linuxserver/overseerr:latest", muted("0"), "5055"),
        ("\u25cf", C_OK,   "tautulli",      "lscr.io/linuxserver/tautulli:latest", muted("0"), "8181"),
        ("\u25cf", C_WARN, "socketproxy",   "tecnativa/docker-socket-proxy:latest", warn("1"), "2375"),
        ("\u25cf", C_OK,   "komodo-core",   "ghcr.io/moghtech/komodo-core:latest", muted("0"), "8000"),
    ]

    for dot, color, name, image, issues, port in services:
        svc_table.add_row(f"[{color}]{dot}[/]", name, image, issues, port)

    console.print(svc_table)
    console.print()
    console.print(f"  {muted(f'Scanned in 0.38s  \u2022  Profile: arrstack  \u2022  Config: .composearr.yml')}")
    console.print()


# ─────────────────────────────────────────────────────────────────
# AUDIT — Ruff-inspired but with Beszel's muted palette
# ─────────────────────────────────────────────────────────────────

def show_audit():
    header_bar()

    # File 1
    console.print(f"  [{C_TEXT}]gluetun/compose.yaml[/]")
    console.print()
    console.print(f"    {dim('16')}  environment:")
    console.print(f"    {dim('17')}    - PUID=0")
    console.print(f"    {dim('18')}    - WIREGUARD_PRIVATE_KEY=bijL6fcCeVv25iz...")
    console.print(f"    {dim('  ')}      [{C_ERR}]{'~' * 44}[/]")
    console.print(f"    {dim('  ')}      [{C_ERR}]\u25cf[/] {err('CA101')}  Secret value hardcoded in environment")
    console.print(f"    {dim('  ')}      {ok('\u2192')} Move to .env and reference as [{C_TEAL}]${{WIREGUARD_PRIVATE_KEY}}[/]")
    console.print()

    # File 2
    console.print(f"  [{C_TEXT}]plex/compose.yaml[/]")
    console.print()
    console.print(f"    {dim(' 3')}  image: lscr.io/linuxserver/plex:latest")
    console.print(f"    {dim('  ')}         [{C_WARN}]{'~' * 33}[/]")
    console.print(f"    {dim('  ')}         [{C_WARN}]\u25cf[/] {warn('CA001')}  Image uses :latest tag")
    console.print(f"    {dim('  ')}         {ok('\u2192')} Pin to [{C_TEAL}]lscr.io/linuxserver/plex:1.41.3[/]")
    console.print()

    # File 3
    console.print(f"  [{C_TEXT}]qbittorrent/compose.yaml[/]")
    console.print()
    console.print(f"    {dim('28')}  healthcheck:")
    console.print(f"    {dim('29')}    test: exit 0")
    console.print(f"    {dim('  ')}          [{C_WARN}]~~~~~~[/]")
    console.print(f"    {dim('  ')}          [{C_WARN}]\u25cf[/] {warn('CA202')}  Healthcheck always passes")
    console.print(f"    {dim('  ')}          {ok('\u2192')} [{C_TEAL}]curl -sf http://localhost:8080/api/v2/app/version || exit 1[/]")
    console.print()

    # File 4
    console.print(f"  [{C_TEXT}]sabnzbd/compose.yaml[/]")
    console.print()
    console.print(f"    {dim('  ')}  {muted('(no restart policy defined)')}")
    console.print(f"    {dim('  ')}  [{C_WARN}]\u25cf[/] {warn('CA203')}  Missing restart policy")
    console.print(f"    {dim('  ')}  {ok('\u2192')} Add [{C_TEAL}]restart: unless-stopped[/]")
    console.print()

    # Cross-file
    console.print(Panel(
        Text.from_markup(
            f"  [{C_ERR}]\u25cf[/] {err('CA401')}  PUID/PGID values differ across media stack\n"
            f"     {dim('\u251c\u2500')} PUID=[bold]1000[/]  sonarr, radarr, bazarr, prowlarr, plex\n"
            f"     {dim('\u251c\u2500')} PUID=[bold]568[/]   qbittorrent, sabnzbd\n"
            f"     {dim('\u2514\u2500')} PUID=[bold]0[/]     gluetun, huntarr, decypharr\n"
            f"     {muted('All media stack services should use the same PUID')}\n"
            f"     [{C_TEAL}]https://trash-guides.info/Hardlinks/How-to-setup-for/Docker/[/]\n"
            f"\n"
            f"  [{C_WARN}]\u25cf[/] {warn('CA402')}  UMASK inconsistent across *arr services\n"
            f"     {dim('\u251c\u2500')} UMASK=[bold]022[/]  sonarr, radarr, bazarr\n"
            f"     {dim('\u2514\u2500')} UMASK=[bold]002[/]  qbittorrent\n"
            f"     {muted('TRaSH recommends 002 for group write / hardlinks')}"
        ),
        title=f"[{C_MUTED}]cross-file[/]",
        title_align="left",
        border_style=Style(color=C_BORDER),
        box=box.ROUNDED,
        padding=(1, 2),
    ))
    console.print()

    # Summary bar
    show_summary_bar()


def show_summary_bar():
    console.print(Panel(
        Text.from_markup(
            f"  [{C_ERR}]\u25cf 4 errors[/]    "
            f"[{C_WARN}]\u25cf 8 warnings[/]    "
            f"[{C_INFO}]\u25cf 3 info[/]    "
            f"{muted('\u2502')}    "
            f"[bold {C_TEXT}]35[/] {muted('files')}  "
            f"[bold {C_TEXT}]42[/] {muted('services')}  "
            f"{muted('\u2502')}    "
            f"{ok('6 auto-fixable')}  "
            f"{muted('\u2192')} [{C_TEAL}]composearr audit --fix[/]"
        ),
        border_style=Style(color=C_BORDER),
        box=box.HORIZONTALS,
        padding=(0, 0),
    ))
    console.print()


# ─────────────────────────────────────────────────────────────────
# PORTS — Clean table with Beszel-style status dots
# ─────────────────────────────────────────────────────────────────

def show_ports():
    header_bar()
    console.print(f"  [{C_TEXT}]Port Allocation[/]  {muted('across 35 compose files')}")
    console.print()

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color=C_BORDER),
        header_style=f"{C_MUTED}",
        padding=(0, 2),
        show_edge=False,
        row_styles=[f"{C_TEXT}", f"dim {C_TEXT}"],
    )
    table.add_column("PORT", justify="right", style=f"bold {C_TEAL}", no_wrap=True)
    table.add_column("SERVICE", style=f"bold {C_TEXT}", min_width=16)
    table.add_column("FILE", style=C_MUTED)
    table.add_column("BIND", style=C_DIM, justify="center")
    table.add_column("", width=3)

    ports = [
        ("2375",  "socketproxy",    "socketproxy/compose.yaml",    "0.0.0.0", f"[{C_WARN}]\u25cf[/]"),
        ("3000",  "subsyncarrplus", "subsyncarrplus/compose.yaml", "0.0.0.0", ""),
        ("3001",  "meshmonitor",    "meshmonitor/compose.yaml",    "0.0.0.0", ""),
        ("5341",  "seq",            "seq/compose.yaml",            "0.0.0.0", ""),
        ("7878",  "radarr",         "radarr/compose.yaml",         "0.0.0.0", ""),
        ("8000",  "komodo-core",    "komodo/compose.yaml",         "0.0.0.0", ""),
        ("8080",  "glances",        "glances/compose.yaml",        "0.0.0.0", ""),
        ("8085",  "termix",         "termix/compose.yaml",         "0.0.0.0", ""),
        ("8095",  "qbittorrent",    "qbittorent/compose.yaml",     "0.0.0.0", ""),
        ("8787",  "bazarr",         "bazarr/compose.yaml",         "0.0.0.0", ""),
        ("8888",  "gluetun",        "gluetun/compose.yaml",        "0.0.0.0", ""),
        ("8889",  "signal-api",     "signal-api/compose.yaml",     "0.0.0.0", ""),
        ("8989",  "sonarr",         "sonarr/compose.yaml",         "0.0.0.0", ""),
        ("9696",  "prowlarr",       "prowlarr/compose.yaml",       "0.0.0.0", ""),
        ("30055", "sabnzbd",        "sabnzbd/compose.yaml",        "0.0.0.0", ""),
        ("32400", "plex",           "plex/compose.yaml",           "0.0.0.0", ""),
    ]

    for port, svc, file, bind, flag in ports:
        table.add_row(port, svc, file, bind, flag)

    console.print(table)
    console.print()
    console.print(f"  [{C_WARN}]\u25cf[/] {warn('2375')} {muted('Docker API exposed on all interfaces \u2014 bind to')} [{C_TEAL}]127.0.0.1[/]")
    console.print(f"  [{C_OK}]\u25cf[/] {ok('No port conflicts detected')}")
    console.print()
    console.print(f"  {muted('16 ports  \u2022  0 conflicts  \u2022  1 warning')}")
    console.print()


# ─────────────────────────────────────────────────────────────────
# SECRETS — Severity-colored findings
# ─────────────────────────────────────────────────────────────────

def show_secrets():
    header_bar()
    console.print(f"  [{C_TEXT}]Secrets & Credentials[/]  {muted('found in stack')}")
    console.print()

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style=Style(color=C_BORDER),
        header_style=f"{C_MUTED}",
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("", width=2)
    table.add_column("VARIABLE", style=f"bold {C_TEXT}", min_width=22, no_wrap=True)
    table.add_column("LOCATION", style=C_MUTED, min_width=24)
    table.add_column("TYPE", style=C_DIM)
    table.add_column("STATUS")

    secrets = [
        (f"[{C_ERR}]\u25cf[/]", "WIREGUARD_PRIVATE_KEY",   "gluetun/compose.yaml:18",     "WireGuard Key",   err("inline")),
        (f"[{C_ERR}]\u25cf[/]", "MYJD_PASSWORD",           "jdownloader2/compose.yaml:14", "Password",        err("inline")),
        (f"[{C_ERR}]\u25cf[/]", "TERMIX_DB_ENCRYPTION_KEY","termix/compose.yaml:15",       "Encryption Key",  err("inline")),
        (f"[{C_ERR}]\u25cf[/]", "JWT_SECRET",              "termix/compose.yaml:16",       "JWT Secret",      err("inline")),
        (f"[{C_WARN}]\u25cf[/]","WIREGUARD_PRIVATE_KEY",   ".env:37",                      "WireGuard Key",   warn("duplicated")),
        (f"[{C_WARN}]\u25cf[/]","KOMODO_JWT_SECRET",       ".env:12",                      "JWT Secret",      warn("weak value")),
        (f"[{C_DIM}]\u25cf[/]", "PLEX_TOKEN",              ".env:28",                      "API Token",       muted("in .env")),
        (f"[{C_DIM}]\u25cf[/]", "SONARR_API_KEY",          ".env:19",                      "API Key",         muted("in .env")),
        (f"[{C_DIM}]\u25cf[/]", "RADARR_API_KEY",          ".env:20",                      "API Key",         muted("in .env")),
        (f"[{C_DIM}]\u25cf[/]", "REALDEBRID_API_KEY",      ".env:35",                      "API Key",         muted("in .env")),
    ]

    for row in secrets:
        table.add_row(*row)

    console.print(table)
    console.print()
    console.print(f"  [{C_ERR}]\u25cf[/]  {err('4 critical')} {muted('\u2014 secrets hardcoded in compose files')}")
    console.print(f"  [{C_WARN}]\u25cf[/]  {warn('2 warnings')} {muted('\u2014 weak or duplicated values')}")
    console.print(f"  [{C_DIM}]\u25cf[/]  {muted('4 ok \u2014 properly stored in .env')}")
    console.print()
    console.print(f"  {ok('\u2192')} [{C_TEAL}]composearr audit --fix[/] {muted('to move inline secrets to .env')}")
    console.print()


# ─────────────────────────────────────────────────────────────────
# DIFF — Syntax-highlighted preview
# ─────────────────────────────────────────────────────────────────

def show_diff():
    header_bar()
    console.print(f"  [{C_TEXT}]Preview Changes[/]  {muted('dry run \u2014 no files modified')}")
    console.print()

    diffs = [
        ("sabnzbd/compose.yaml", "CA203", "require-restart-policy", """\
--- sabnzbd/compose.yaml
+++ sabnzbd/compose.yaml (fixed)
@@ -4,6 +4,7 @@
     image: ghcr.io/home-operations/sabnzbd:latest
     container_name: sabnzbd
+    restart: unless-stopped
     environment:
       PUID: "568"
       PGID: "568\""""),

        ("gluetun/compose.yaml", "CA101", "no-inline-secrets", """\
--- gluetun/compose.yaml
+++ gluetun/compose.yaml (fixed)
@@ -16,7 +16,7 @@
     environment:
       - PUID=0
-      - WIREGUARD_PRIVATE_KEY=bijL6fcCeVv25izRy3JseahatW9rsd0eCpo5aLricRI=
+      - WIREGUARD_PRIVATE_KEY=${WIREGUARD_PRIVATE_KEY}
       - VPN_SERVICE_PROVIDER=custom"""),

        ("prowlarr/compose.yaml", "CA205", "require-log-rotation", """\
--- prowlarr/compose.yaml
+++ prowlarr/compose.yaml (fixed)
@@ -18,3 +18,8 @@
     networks:
       - safe-bridge
+    logging:
+      driver: json-file
+      options:
+        max-size: "10m"
+        max-file: "3\""""),
    ]

    for filename, rule, name, diff_text in diffs:
        console.print(Panel(
            Syntax(diff_text, "diff", theme="monokai", line_numbers=False),
            title=f"[{C_MUTED}]{filename}[/]  {dim(f'{rule} {name}')}",
            title_align="left",
            border_style=Style(color=C_BORDER),
            box=box.ROUNDED,
            padding=(0, 1),
        ))
        console.print()

    console.print(f"  {ok('3 files')} {muted('would be modified')}  {dim('\u2022')}  {warn('3 issues')} {muted('remain (manual fix)')}")
    console.print()
    console.print(f"  {ok('\u2192')} [{C_TEAL}]composearr audit --fix[/] {muted('to apply')}")
    console.print()


# ─────────────────────────────────────────────────────────────────
# RULES — Clean tree with severity dots
# ─────────────────────────────────────────────────────────────────

def show_rules():
    header_bar()
    console.print(f"  [{C_TEXT}]Available Rules[/]  {muted('20 rules \u2022 6 fixable \u2022 4 cross-file')}")
    console.print()

    def rule_line(rid, sev, name, desc, tags=""):
        sev_colors = {"error": C_ERR, "warning": C_WARN, "info": C_INFO}
        c = sev_colors.get(sev, C_MUTED)
        tag_str = f"  [{C_DIM}]{tags}[/]" if tags else ""
        return f"[{c}]\u25cf[/] [{C_TEXT}]{rid}[/]  [{c}]{sev:<7}[/]  [bold]{name}[/]  {muted(desc)}{tag_str}"

    sections = [
        ("Images", C_ACCENT, [
            ("CA001", "warning", "no-latest-tag", "uses :latest or has no tag", "fixable"),
            ("CA002", "info",    "no-digest-pin", "no @sha256: digest pin", ""),
            ("CA003", "info",    "untrusted-registry", "image from unknown registry", ""),
        ]),
        ("Security", C_ERR, [
            ("CA101", "error",   "no-inline-secrets", "secret hardcoded in env", "fixable"),
            ("CA102", "error",   "no-privileged", "container in privileged mode", ""),
            ("CA103", "warning", "no-docker-sock", "docker socket mounted", ""),
            ("CA104", "error",   "no-cap-add-all", "cap_add: ALL grants all caps", ""),
            ("CA105", "warning", "unbound-port", "port on 0.0.0.0", "fixable"),
        ]),
        ("Reliability", C_WARN, [
            ("CA201", "warning", "require-healthcheck", "no healthcheck defined", ""),
            ("CA202", "warning", "no-fake-healthcheck", "healthcheck is exit 0", ""),
            ("CA203", "warning", "require-restart", "no restart policy", "fixable"),
            ("CA204", "warning", "require-resources", "missing memory/CPU limits", ""),
            ("CA205", "info",    "require-log-rotation", "no log rotation configured", "fixable"),
        ]),
        ("Networking", C_INFO, [
            ("CA301", "error",   "port-conflict", "same port, multiple services", "cross-file"),
            ("CA302", "warning", "no-host-network", "uses network_mode: host", ""),
            ("CA303", "info",    "no-default-network", "no explicit network", ""),
        ]),
        ("Consistency", C_OK, [
            ("CA401", "error",   "puid-pgid-mismatch", "PUID/PGID differ across services", "cross-file"),
            ("CA402", "warning", "umask-inconsistent", "UMASK values differ", "cross-file"),
            ("CA403", "warning", "missing-timezone", "TZ not set", "fixable"),
        ]),
        ("Arr Stack", C_TEAL, [
            ("CA601", "warning", "hardlink-path-mismatch", "containers lack shared /data root", "cross-file"),
        ]),
    ]

    for section_name, section_color, rules in sections:
        console.print(f"  [{section_color}]\u2501\u2501[/] [{section_color}]{section_name}[/]")
        console.print()
        for rid, sev, name, desc, tags in rules:
            console.print(f"     {rule_line(rid, sev, name, desc, tags)}")
        console.print()

    console.print(f"  {muted('Configure in .composearr.yml or with --rule / --ignore flags')}")
    console.print()


# ─────────────────────────────────────────────────────────────────
# INIT — Interactive setup with Beszel-style panels
# ─────────────────────────────────────────────────────────────────

def show_init():
    header_bar()

    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]{{task.description}}[/]"),
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning directory...", total=35)
        for _ in range(35):
            time.sleep(0.02)
            progress.update(task, advance=1)

    console.print(f"  [{C_OK}]\u2713[/] Found [bold]35[/] compose files, [bold]42[/] services")
    console.print()

    # Profile selection
    console.print(f"  [{C_TEXT}]?[/] Select a profile")
    console.print()
    profiles = [
        ("arrstack", "Media server rules \u2014 Sonarr, Radarr, TRaSH compliance", True),
        ("homelab", "General self-hosted rules", False),
        ("production", "Strict production-readiness", False),
        ("security", "Security-focused only", False),
        ("minimal", "Just the essentials", False),
    ]
    for name, desc, selected in profiles:
        if selected:
            console.print(f"    [{C_TEAL}]\u25b8[/] [bold {C_TEXT}]{name}[/]  {muted(desc)}")
        else:
            console.print(f"      {muted(name)}  {dim(desc)}")
    console.print()

    # Strictness
    console.print(f"  [{C_TEXT}]?[/] Strictness level")
    console.print()
    levels = [
        ("recommended", "Errors for critical, warnings for best practices", True),
        ("strict", "Most rules as errors (CI mode)", False),
        ("relaxed", "Mostly warnings", False),
    ]
    for name, desc, selected in levels:
        if selected:
            console.print(f"    [{C_TEAL}]\u25b8[/] [bold {C_TEXT}]{name}[/]  {muted(desc)}")
        else:
            console.print(f"      {muted(name)}  {dim(desc)}")
    console.print()

    time.sleep(0.3)
    console.print(f"  [{C_OK}]\u2713[/] Created [bold].composearr.yml[/]")
    console.print()

    config = """\
profile: arrstack
severity: warning

rules:
  CA001: warning     # no-latest-tag
  CA101: error       # no-inline-secrets
  CA201: warning     # require-healthcheck
  CA301: error       # port-conflict
  CA401: error       # puid-pgid-mismatch

trusted_registries:
  - lscr.io
  - ghcr.io
  - docker.io"""

    console.print(Panel(
        Syntax(config, "yaml", theme="monokai", line_numbers=False),
        title=f"[{C_MUTED}].composearr.yml[/]",
        title_align="left",
        border_style=Style(color=C_BORDER),
        box=box.ROUNDED,
        padding=(1, 2),
        width=52,
    ))
    console.print()
    console.print(f"  {muted('Next steps:')}")
    console.print(f"    [{C_TEAL}]composearr audit[/]         {muted('run audit')}")
    console.print(f"    [{C_TEAL}]composearr audit --fix[/]   {muted('auto-fix issues')}")
    console.print(f"    [{C_TEAL}]composearr audit --diff[/]  {muted('preview fixes')}")
    console.print(f"    [{C_TEAL}]composearr ports[/]         {muted('view port map')}")
    console.print()


# ─────────────────────────────────────────────────────────────────
# SCANNING — Progress animation
# ─────────────────────────────────────────────────────────────────

def show_scanning():
    header_bar()

    files = [
        "bazarr", "beszel", "decypharr", "glances", "gluetun",
        "huntarr", "jdownloader2", "komodo", "meshmonitor", "overseerr",
        "plex", "prowlarr", "qbittorrent", "radarr", "sabnzbd",
        "seq", "signal-api", "sonarr", "socketproxy", "subgen",
        "subsyncarrplus", "tautulli", "termix", "vector", "whisparr",
    ]

    with Progress(
        SpinnerColumn(style=C_TEAL),
        TextColumn(f"[{C_MUTED}]{{task.description}}[/]"),
        BarColumn(bar_width=30, style=C_DIM, complete_style=C_TEAL, finished_style=C_OK),
        TextColumn(f"[{C_DIM}]{{task.completed}}/{{task.total}}[/]"),
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning...", total=len(files))
        for f in files:
            progress.update(task, description=f"Scanning [{C_TEAL}]{f}[/]/compose.yaml")
            time.sleep(0.06)
            progress.update(task, advance=1)

    console.print(f"  [{C_OK}]\u2713[/] Scanned [bold]25[/] compose files ([bold]34[/] services) in [bold]0.38s[/]")
    console.print(f"  [{C_OK}]\u2713[/] Cross-file analysis complete")
    console.print()


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def show_all():
    console.print()
    console.print(Panel(
        Align.center(Text.from_markup(
            f"[bold {C_TEAL}]\u25c6[/] [bold {C_TEXT}]ComposeArr[/]  {muted('UI Mockup v2')}\n"
            f"{muted('Beszel-inspired \u2022 Restrained elegance')}"
        )),
        border_style=Style(color=C_BORDER),
        box=box.ROUNDED,
        padding=(1, 4),
    ))

    sections = [
        ("DASHBOARD", show_dashboard),
        ("SCANNING", show_scanning),
        ("AUDIT OUTPUT", show_audit),
        ("DIFF PREVIEW", show_diff),
        ("PORT TABLE", show_ports),
        ("SECRETS SCAN", show_secrets),
        ("RULES", show_rules),
        ("INIT FLOW", show_init),
    ]

    for title, fn in sections:
        console.print()
        console.print(f"  {dim(f'\u2500\u2500 {title} \u2500' * 3)}")
        console.print()
        fn()
        console.print(f"  {muted('─' * 60)}")

    console.print(Panel(
        Text.from_markup(
            f"  {ok('Done.')} {muted('All mockups rendered.')}\n\n"
            f"  {muted('Tech stack:')} [{C_TEAL}]Rich[/] {muted('for CLI')} {dim('\u2022')} "
            f"[{C_TEAL}]shadcn/ui + Tailwind[/] {muted('for web UI')}\n"
            f"  {muted('Colors auto-degrade on basic terminals. Respects NO_COLOR.')}"
        ),
        border_style=Style(color=C_OK),
        box=box.ROUNDED,
        padding=(1, 1),
    ))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    dispatch = {
        "all": show_all,
        "audit": show_audit,
        "dashboard": show_dashboard,
        "ports": show_ports,
        "secrets": show_secrets,
        "diff": show_diff,
        "rules": show_rules,
        "init": show_init,
        "scan": show_scanning,
    }
    fn = dispatch.get(cmd, show_all)
    fn()
