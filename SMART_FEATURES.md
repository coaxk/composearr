# ComposeArr Smart Features

Advanced intelligence that makes ComposeArr more than just a linter.

---

## Overview

ComposeArr includes smart features that go beyond static analysis:
1. **Tag Analyzer** - Fetch available tags from registries
2. **System Profiler** - Detect host resources and suggest limits
3. **Healthcheck Helper** - Generate service-specific healthchecks
4. **Secret Detector** - Pattern matching + entropy analysis
5. **Known Services Database** - Pre-configured settings for popular images

---

## 1. Tag Analyzer

### Purpose
When CA001 detects `:latest` tag, automatically fetch available versions from the registry and suggest the most appropriate one.

### Implementation

```python
# src/composearr/analyzers/tag_analyzer.py

from dataclasses import dataclass
from typing import List, Optional
import requests
from packaging import version as pkg_version

@dataclass
class TagInfo:
    tag: str
    created: str
    size: int
    is_latest: bool = False

@dataclass
class TagSuggestion:
    registry: str
    image: str
    current_tag: str
    available_tags: List[TagInfo]
    recommended_tag: str
    reasoning: str

class TagAnalyzer:
    """Fetch and analyze image tags from Docker registries"""
    
    REGISTRY_APIS = {
        'docker.io': 'https://registry.hub.docker.com/v2',
        'ghcr.io': 'https://ghcr.io/v2',
        'lscr.io': 'https://lscr.io/v2',
        'gcr.io': 'https://gcr.io/v2',
        'quay.io': 'https://quay.io/v2',
    }
    
    def analyze_image(self, image: str) -> Optional[TagSuggestion]:
        """
        Parse image name and fetch available tags
        
        Examples:
          lscr.io/linuxserver/plex:latest
          ghcr.io/hotio/sonarr:release
          nginx:latest
          myregistry.com:5000/myapp:latest
        """
        registry, repo, tag = self._parse_image(image)
        
        if not self._is_supported_registry(registry):
            return None
        
        tags = self._fetch_tags(registry, repo)
        if not tags:
            return None
        
        recommended = self._recommend_tag(tags, repo)
        
        return TagSuggestion(
            registry=registry,
            image=f"{registry}/{repo}",
            current_tag=tag,
            available_tags=tags,
            recommended_tag=recommended.tag,
            reasoning=self._explain_recommendation(recommended, tags)
        )
    
    def _parse_image(self, image: str) -> tuple[str, str, str]:
        """
        Parse image string into (registry, repo, tag)
        
        nginx:latest → (docker.io, library/nginx, latest)
        lscr.io/linuxserver/plex:latest → (lscr.io, linuxserver/plex, latest)
        """
        # Handle explicit registry
        if '/' in image and '.' in image.split('/')[0]:
            parts = image.split('/', 1)
            registry = parts[0]
            rest = parts[1]
        else:
            registry = 'docker.io'
            rest = image
        
        # Handle tag
        if ':' in rest:
            repo, tag = rest.rsplit(':', 1)
        else:
            repo, tag = rest, 'latest'
        
        # Handle official images (nginx → library/nginx)
        if registry == 'docker.io' and '/' not in repo:
            repo = f'library/{repo}'
        
        return registry, repo, tag
    
    def _fetch_tags(self, registry: str, repo: str) -> List[TagInfo]:
        """Fetch available tags from registry API"""
        api_base = self.REGISTRY_APIS.get(registry)
        if not api_base:
            return []
        
        try:
            if registry == 'docker.io':
                return self._fetch_dockerhub_tags(repo)
            elif registry.startswith('ghcr.io'):
                return self._fetch_ghcr_tags(repo)
            elif registry == 'lscr.io':
                return self._fetch_lscr_tags(repo)
            else:
                return self._fetch_generic_v2_tags(registry, repo)
        except Exception as e:
            # Don't crash on API failures
            return []
    
    def _fetch_dockerhub_tags(self, repo: str) -> List[TagInfo]:
        """
        Fetch tags from Docker Hub
        API: https://registry.hub.docker.com/v2/repositories/{repo}/tags
        """
        url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags"
        params = {'page_size': 100, 'ordering': 'last_updated'}
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        tags = []
        
        for tag in data.get('results', []):
            tags.append(TagInfo(
                tag=tag['name'],
                created=tag['last_updated'],
                size=tag.get('full_size', 0),
                is_latest=(tag['name'] == 'latest')
            ))
        
        return tags
    
    def _fetch_ghcr_tags(self, repo: str) -> List[TagInfo]:
        """
        Fetch tags from GitHub Container Registry
        API: https://ghcr.io/v2/{repo}/tags/list
        """
        url = f"https://ghcr.io/v2/{repo}/tags/list"
        
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        tags = []
        
        for tag_name in data.get('tags', []):
            tags.append(TagInfo(
                tag=tag_name,
                created='',  # GHCR doesn't provide this in tags/list
                size=0,
                is_latest=(tag_name == 'latest')
            ))
        
        return tags
    
    def _recommend_tag(self, tags: List[TagInfo], repo: str) -> TagInfo:
        """
        Recommend the best tag based on versioning pattern
        
        Logic:
        1. For LinuxServer.io: prefer "version-X.Y.Z" over "X.Y.Z"
        2. For Hotio: prefer "release" over semantic versions
        3. For others: prefer latest semantic version
        """
        # LinuxServer.io pattern: version-1.41.3
        if 'linuxserver' in repo:
            version_tags = [t for t in tags if t.tag.startswith('version-')]
            if version_tags:
                return self._get_latest_version(version_tags, prefix='version-')
        
        # Hotio pattern: release, testing, nightly
        if 'hotio' in repo:
            for preferred in ['release', 'stable', 'latest']:
                tag = next((t for t in tags if t.tag == preferred), None)
                if tag:
                    return tag
        
        # Semantic versioning: 1.2.3, v1.2.3
        semantic_tags = self._filter_semantic_tags(tags)
        if semantic_tags:
            return self._get_latest_version(semantic_tags)
        
        # Fallback: just return first non-latest tag
        return next((t for t in tags if not t.is_latest), tags[0])
    
    def _filter_semantic_tags(self, tags: List[TagInfo]) -> List[TagInfo]:
        """Filter tags that look like semantic versions"""
        semantic = []
        for tag in tags:
            # Match: 1.2.3, v1.2.3, 2024.01.15
            if self._is_semantic_version(tag.tag):
                semantic.append(tag)
        return semantic
    
    def _is_semantic_version(self, tag: str) -> bool:
        """Check if tag looks like a semantic version"""
        cleaned = tag.lstrip('v')
        try:
            pkg_version.parse(cleaned)
            return True
        except:
            return False
    
    def _get_latest_version(self, tags: List[TagInfo], prefix: str = '') -> TagInfo:
        """Get the highest semantic version from list"""
        def version_key(tag: TagInfo):
            cleaned = tag.tag.lstrip('v').removeprefix(prefix)
            try:
                return pkg_version.parse(cleaned)
            except:
                return pkg_version.parse('0.0.0')
        
        return max(tags, key=version_key)
    
    def _explain_recommendation(self, recommended: TagInfo, all_tags: List[TagInfo]) -> str:
        """Generate human-readable explanation of why this tag was chosen"""
        if recommended.tag.startswith('version-'):
            return "LinuxServer.io version tag (recommended for stability)"
        elif recommended.tag == 'release':
            return "Hotio release channel (stable updates)"
        elif self._is_semantic_version(recommended.tag):
            return "Latest stable semantic version"
        else:
            return "Most recently updated tag"


# ─────────────────────────────────────────────────────────────
# Usage in CA001 rule
# ─────────────────────────────────────────────────────────────

class NoLatestTag(BaseRule):
    id = "CA001"
    
    def check(self, context) -> List[LintIssue]:
        issues = []
        analyzer = TagAnalyzer()
        
        for service_name, service in context.services.items():
            image = service.get('image', '')
            
            if ':latest' in image or ':' not in image:
                # Try to fetch better tags
                suggestion = analyzer.analyze_image(image)
                
                if suggestion:
                    suggested_fix = f"image: {suggestion.image}:{suggestion.recommended_tag}"
                    learn_more = self._format_tag_options(suggestion)
                else:
                    suggested_fix = "Pin to a specific version tag"
                    learn_more = None
                
                issues.append(LintIssue(
                    rule_id=self.id,
                    message="Image uses :latest tag",
                    suggested_fix=suggested_fix,
                    learn_more=learn_more
                ))
        
        return issues
    
    def _format_tag_options(self, suggestion: TagSuggestion) -> str:
        """Format available tags as markdown for rich console"""
        lines = [
            f"\nAvailable tags for {suggestion.image}:",
            f"  • {suggestion.recommended_tag} ({suggestion.reasoning})",
        ]
        
        # Show a few other options
        other_tags = [t for t in suggestion.available_tags[:5] 
                      if t.tag != suggestion.recommended_tag]
        for tag in other_tags:
            lines.append(f"  • {tag.tag}")
        
        return "\n".join(lines)
```

---

## 2. System Profiler

### Purpose
Detect host system resources and suggest appropriate resource limits based on:
- Total system RAM/CPU
- Current container usage (if running)
- Service type (database vs web app vs media processor)

### Implementation

```python
# src/composearr/analyzers/system_profiler.py

from dataclasses import dataclass
from typing import Optional
import psutil
import subprocess
import json

@dataclass
class SystemResources:
    total_ram_gb: float
    total_cpus: int
    available_ram_gb: float
    cpu_usage_percent: float

@dataclass
class ContainerStats:
    name: str
    cpu_percent: float
    memory_mb: float
    memory_limit_mb: Optional[float]
    memory_percent: float

@dataclass
class ResourceSuggestion:
    cpu_limit: str
    memory_limit: str
    reasoning: str
    based_on: str  # "system_default", "current_usage", "service_profile"

class SystemProfiler:
    """Analyze system resources and suggest container limits"""
    
    # Service profiles with typical resource usage
    SERVICE_PROFILES = {
        'database': {'cpu': '2.0', 'memory': '2G', 'priority': 'high'},
        'web': {'cpu': '1.0', 'memory': '512M', 'priority': 'medium'},
        'media': {'cpu': '4.0', 'memory': '2G', 'priority': 'high'},
        'vpn': {'cpu': '0.5', 'memory': '256M', 'priority': 'low'},
        'monitoring': {'cpu': '0.5', 'memory': '512M', 'priority': 'low'},
    }
    
    def get_system_resources(self) -> SystemResources:
        """Get current system resource availability"""
        mem = psutil.virtual_memory()
        
        return SystemResources(
            total_ram_gb=mem.total / (1024**3),
            total_cpus=psutil.cpu_count(),
            available_ram_gb=mem.available / (1024**3),
            cpu_usage_percent=psutil.cpu_percent(interval=1)
        )
    
    def get_container_stats(self, service_name: str) -> Optional[ContainerStats]:
        """Get current stats for a running container"""
        try:
            # docker stats --no-stream --format json SERVICE
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', 'json', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None
            
            data = json.loads(result.stdout)
            
            # Parse memory (e.g., "512MiB / 2GiB")
            mem_parts = data['MemUsage'].split(' / ')
            current_mem = self._parse_size(mem_parts[0])
            limit_mem = self._parse_size(mem_parts[1]) if len(mem_parts) > 1 else None
            
            return ContainerStats(
                name=service_name,
                cpu_percent=float(data['CPUPerc'].rstrip('%')),
                memory_mb=current_mem,
                memory_limit_mb=limit_mem,
                memory_percent=float(data['MemPerc'].rstrip('%'))
            )
        
        except Exception:
            return None
    
    def suggest_resources(
        self, 
        service_name: str, 
        service_image: str,
        current_stats: Optional[ContainerStats] = None
    ) -> ResourceSuggestion:
        """
        Suggest resource limits for a service
        
        Priority:
        1. Current usage (if container is running) + 20% headroom
        2. Service profile (based on image type)
        3. System defaults (conservative fallback)
        """
        system = self.get_system_resources()
        
        # Try to get current usage
        if current_stats:
            return self._suggest_from_usage(current_stats, system)
        
        # Try to detect running container
        stats = self.get_container_stats(service_name)
        if stats:
            return self._suggest_from_usage(stats, system)
        
        # Fallback to service profile
        service_type = self._detect_service_type(service_image)
        if service_type:
            return self._suggest_from_profile(service_type, system)
        
        # Final fallback: conservative defaults
        return self._suggest_defaults(system)
    
    def _suggest_from_usage(
        self, 
        stats: ContainerStats, 
        system: SystemResources
    ) -> ResourceSuggestion:
        """Suggest based on current container usage + 20% headroom"""
        
        # CPU: current usage + 20%
        suggested_cpu = stats.cpu_percent * 1.2 / 100
        suggested_cpu = max(0.5, min(suggested_cpu, system.total_cpus))
        cpu_limit = f"{suggested_cpu:.1f}"
        
        # Memory: current usage + 20%
        suggested_mem_mb = stats.memory_mb * 1.2
        suggested_mem_gb = suggested_mem_mb / 1024
        
        if suggested_mem_gb < 1:
            memory_limit = f"{int(suggested_mem_mb)}M"
        else:
            memory_limit = f"{suggested_mem_gb:.1f}G"
        
        return ResourceSuggestion(
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            reasoning=f"Based on current usage ({stats.cpu_percent:.0f}% CPU, {stats.memory_mb:.0f}MB RAM) + 20% headroom",
            based_on="current_usage"
        )
    
    def _suggest_from_profile(
        self, 
        service_type: str, 
        system: SystemResources
    ) -> ResourceSuggestion:
        """Suggest based on service type profile"""
        profile = self.SERVICE_PROFILES[service_type]
        
        return ResourceSuggestion(
            cpu_limit=profile['cpu'],
            memory_limit=profile['memory'],
            reasoning=f"Typical {service_type} service resource requirements",
            based_on="service_profile"
        )
    
    def _suggest_defaults(self, system: SystemResources) -> ResourceSuggestion:
        """Conservative default limits"""
        # Default: 1 CPU, 512MB
        # But scale down if system is constrained
        
        if system.total_cpus < 4:
            cpu_limit = "0.5"
        else:
            cpu_limit = "1.0"
        
        if system.total_ram_gb < 8:
            memory_limit = "256M"
        else:
            memory_limit = "512M"
        
        return ResourceSuggestion(
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            reasoning="Conservative defaults for unknown service type",
            based_on="system_default"
        )
    
    def _detect_service_type(self, image: str) -> Optional[str]:
        """Detect service type from image name"""
        image_lower = image.lower()
        
        # Databases
        if any(db in image_lower for db in ['postgres', 'mysql', 'mariadb', 'mongodb', 'redis']):
            return 'database'
        
        # Media processing
        if any(m in image_lower for m in ['plex', 'emby', 'jellyfin', 'unmanic', 'tdarr']):
            return 'media'
        
        # VPN
        if any(v in image_lower for v in ['gluetun', 'wireguard', 'openvpn']):
            return 'vpn'
        
        # Monitoring
        if any(mon in image_lower for mon in ['prometheus', 'grafana', 'uptime', 'beszel']):
            return 'monitoring'
        
        # Web apps (default for many services)
        if any(w in image_lower for w in ['sonarr', 'radarr', 'nginx', 'caddy', 'apache']):
            return 'web'
        
        return None
    
    def _parse_size(self, size_str: str) -> float:
        """Parse Docker size string to MB"""
        size_str = size_str.strip()
        
        if size_str.endswith('GiB') or size_str.endswith('GB'):
            return float(size_str.rstrip('GiBgb ')) * 1024
        elif size_str.endswith('MiB') or size_str.endswith('MB'):
            return float(size_str.rstrip('MiBmb '))
        elif size_str.endswith('KiB') or size_str.endswith('KB'):
            return float(size_str.rstrip('KiBkb ')) / 1024
        else:
            return float(size_str.rstrip('Bb ')) / (1024**2)


# ─────────────────────────────────────────────────────────────
# Interactive Prompt for Resource Limits
# ─────────────────────────────────────────────────────────────

def prompt_resource_limits(service_name: str, service_image: str) -> dict:
    """Interactive prompt with smart suggestions"""
    profiler = SystemProfiler()
    system = profiler.get_system_resources()
    suggestion = profiler.suggest_resources(service_name, service_image)
    
    console.print(f"\n[bold]Resource Limits for {service_name}[/]")
    console.print(f"  Image: {service_image}")
    console.print(f"\n[dim]System: {system.total_cpus} CPUs, {system.total_ram_gb:.1f}GB RAM[/]")
    console.print(f"[dim]{suggestion.reasoning}[/]\n")
    
    # CPU limit
    cpu = typer.prompt(
        "CPU limit",
        default=suggestion.cpu_limit,
        show_default=True
    )
    
    # Memory limit
    memory = typer.prompt(
        "Memory limit",
        default=suggestion.memory_limit,
        show_default=True
    )
    
    return {
        'cpu': cpu,
        'memory': memory
    }
```

---

## 3. Healthcheck Helper

### Purpose
Generate service-specific healthcheck configurations based on:
- Detected service type
- Exposed ports
- Known healthcheck endpoints

### Implementation

```python
# src/composearr/analyzers/healthcheck_helper.py

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class HealthcheckTemplate:
    name: str
    test_command: List[str]
    interval: str
    timeout: str
    retries: int
    start_period: str
    description: str

class HealthcheckHelper:
    """Generate smart healthcheck configurations"""
    
    # Known healthcheck endpoints for popular services
    KNOWN_ENDPOINTS = {
        'sonarr': '/api/v3/health',
        'radarr': '/api/v3/health',
        'prowlarr': '/api/v1/health',
        'lidarr': '/api/v1/health',
        'readarr': '/api/v1/health',
        'bazarr': '/api/system/status',
        'plex': '/identity',
        'overseerr': '/api/v1/status',
        'tautulli': '/api/v2?cmd=get_activity',
        'qbittorrent': '/api/v2/app/version',
        'sabnzbd': '/api?mode=version',
        'transmission': '/transmission/rpc',
        'jellyfin': '/health',
        'emby': '/emby/System/Info',
    }
    
    def suggest_healthchecks(
        self,
        service_name: str,
        service_image: str,
        exposed_ports: List[int]
    ) -> List[HealthcheckTemplate]:
        """Generate healthcheck options for a service"""
        
        suggestions = []
        
        # Try known endpoint first
        endpoint = self._detect_endpoint(service_name, service_image)
        if endpoint:
            port = self._detect_port(exposed_ports)
            suggestions.append(self._create_http_check(endpoint, port))
        
        # Always offer process check
        process_name = self._detect_process_name(service_name, service_image)
        suggestions.append(self._create_process_check(process_name))
        
        # If we have ports, offer generic HTTP check
        if exposed_ports:
            port = exposed_ports[0]
            suggestions.append(self._create_generic_http_check(port))
        
        # Always offer exit 0 (with warning)
        suggestions.append(self._create_always_pass_check())
        
        return suggestions
    
    def _detect_endpoint(self, service_name: str, image: str) -> Optional[str]:
        """Detect known healthcheck endpoint"""
        name_lower = service_name.lower()
        image_lower = image.lower()
        
        for service_type, endpoint in self.KNOWN_ENDPOINTS.items():
            if service_type in name_lower or service_type in image_lower:
                return endpoint
        
        return None
    
    def _detect_port(self, ports: List[int]) -> int:
        """Select most likely port for healthcheck"""
        # Prefer common web ports
        common_web = [80, 443, 8080, 3000, 5000, 8000]
        for port in common_web:
            if port in ports:
                return port
        
        # Otherwise use first exposed port
        return ports[0] if ports else 8080
    
    def _detect_process_name(self, service_name: str, image: str) -> str:
        """Detect likely process name"""
        # Try service name first
        if service_name.replace('-', '').replace('_', '').isalnum():
            return service_name.replace('-', '').replace('_', '')
        
        # Try extracting from image
        if '/' in image:
            image_name = image.split('/')[-1].split(':')[0]
            return image_name
        
        return service_name
    
    def _create_http_check(self, endpoint: str, port: int) -> HealthcheckTemplate:
        """Create HTTP healthcheck with known endpoint"""
        return HealthcheckTemplate(
            name="HTTP Check (Recommended)",
            test_command=[
                "CMD-SHELL",
                f"curl -sf http://localhost:{port}{endpoint} || exit 1"
            ],
            interval="30s",
            timeout="10s",
            retries=3,
            start_period="30s",
            description=f"Checks if API endpoint responds correctly"
        )
    
    def _create_process_check(self, process_name: str) -> HealthcheckTemplate:
        """Create process-based healthcheck"""
        return HealthcheckTemplate(
            name="Process Check",
            test_command=[
                "CMD-SHELL",
                f"pgrep -f {process_name} || exit 1"
            ],
            interval="60s",
            timeout="10s",
            retries=5,
            start_period="40s",
            description="Checks if main process is running"
        )
    
    def _create_generic_http_check(self, port: int) -> HealthcheckTemplate:
        """Create generic HTTP check on root"""
        return HealthcheckTemplate(
            name="Generic HTTP Check",
            test_command=[
                "CMD-SHELL",
                f"curl -sf http://localhost:{port}/ || exit 1"
            ],
            interval="30s",
            timeout="10s",
            retries=3,
            start_period="30s",
            description="Checks if web server responds on root path"
        )
    
    def _create_always_pass_check(self) -> HealthcheckTemplate:
        """Create always-pass healthcheck (with warning)"""
        return HealthcheckTemplate(
            name="Always Pass (Not Recommended)",
            test_command=["CMD-SHELL", "exit 0"],
            interval="30s",
            timeout="10s",
            retries=3,
            start_period="30s",
            description="⚠️ Always succeeds - provides no health info. Use only temporarily for debugging."
        )


# ─────────────────────────────────────────────────────────────
# Interactive Healthcheck Selection
# ─────────────────────────────────────────────────────────────

def prompt_healthcheck(service_name: str, service: dict) -> dict:
    """Interactive healthcheck selection with smart suggestions"""
    helper = HealthcheckHelper()
    
    # Extract ports
    ports = []
    for port_spec in service.get('ports', []):
        if isinstance(port_spec, str):
            # Parse "8080:8080" → 8080
            host_port = port_spec.split(':')[0]
            ports.append(int(host_port))
        elif isinstance(port_spec, dict):
            ports.append(port_spec.get('published', 8080))
    
    # Get suggestions
    suggestions = helper.suggest_healthchecks(
        service_name,
        service.get('image', ''),
        ports
    )
    
    # Present options
    console.print(f"\n[bold]Healthcheck for {service_name}[/]")
    console.print()
    
    for i, suggestion in enumerate(suggestions, 1):
        console.print(f"[cyan]{i}.[/] [bold]{suggestion.name}[/]")
        console.print(f"   {suggestion.description}")
        console.print(f"   [dim]Test: {' '.join(suggestion.test_command)}[/]")
        console.print()
    
    console.print(f"[cyan]{len(suggestions)+1}.[/] Skip healthcheck")
    console.print()
    
    choice = typer.prompt("Select option", type=int, default=1)
    
    if choice > len(suggestions):
        return None  # Skip
    
    selected = suggestions[choice - 1]
    
    return {
        'test': selected.test_command,
        'interval': selected.interval,
        'timeout': selected.timeout,
        'retries': selected.retries,
        'start_period': selected.start_period
    }
```

---

## 4. Secret Detector

### Purpose
Detect hardcoded secrets using both pattern matching and entropy analysis.

### Implementation

```python
# src/composearr/analyzers/secret_detector.py

import re
import math
from dataclasses import dataclass
from typing import List

@dataclass
class SecretMatch:
    key: str
    value: str
    confidence: float  # 0.0 to 1.0
    reason: str
    line: int

class SecretDetector:
    """Detect hardcoded secrets using patterns + entropy analysis"""
    
    # Regex patterns for common secret keys
    SENSITIVE_PATTERNS = [
        r'.*API[_-]?KEY.*',
        r'.*SECRET.*',
        r'.*PASSWORD.*',
        r'.*TOKEN.*',
        r'.*PRIVATE[_-]?KEY.*',
        r'.*AUTH.*',
        r'.*CREDENTIAL.*',
        r'.*ACCESS[_-]?KEY.*',
        r'.*CLIENT[_-]?SECRET.*',
    ]
    
    # Known safe values (don't flag these)
    SAFE_VALUES = {
        'changeme', 'password', 'secret', 'token',
        'your-api-key-here', 'replace-me',
        'example', 'test', 'demo',
    }
    
    def detect_secrets(
        self,
        environment: dict | list,
        min_entropy: float = 0.6,
        min_length: int = 20
    ) -> List[SecretMatch]:
        """
        Detect secrets in environment variables
        
        Args:
            environment: Dict or list of env vars
            min_entropy: Minimum Shannon entropy (0.0-1.0)
            min_length: Minimum string length to check
        """
        secrets = []
        
        # Normalize to dict format
        env_dict = self._normalize_env(environment)
        
        for key, value in env_dict.items():
            # Skip variable references (${VAR})
            if self._is_variable_reference(value):
                continue
            
            # Skip safe placeholder values
            if value.lower() in self.SAFE_VALUES:
                continue
            
            # Pattern matching
            if self._matches_sensitive_pattern(key):
                # Check if value looks like a secret
                if len(value) >= min_length:
                    entropy = self._calculate_entropy(value)
                    
                    if entropy >= min_entropy:
                        secrets.append(SecretMatch(
                            key=key,
                            value=value,
                            confidence=entropy,
                            reason=f"Sensitive key name + high entropy ({entropy:.2f})",
                            line=0  # Will be filled in by caller
                        ))
        
        return secrets
    
    def _normalize_env(self, environment: dict | list) -> dict:
        """Convert environment to dict format"""
        if isinstance(environment, dict):
            return environment
        
        # List format: ["KEY=value", "KEY2=value2"]
        env_dict = {}
        for item in environment:
            if '=' in item:
                key, value = item.split('=', 1)
                env_dict[key.strip()] = value.strip()
        
        return env_dict
    
    def _is_variable_reference(self, value: str) -> bool:
        """Check if value is a variable reference"""
        # ${VAR}, ${VAR:-default}, $VAR
        return bool(re.match(r'^\$\{?[A-Z_][A-Z0-9_]*', value))
    
    def _matches_sensitive_pattern(self, key: str) -> bool:
        """Check if key matches sensitive patterns"""
        key_upper = key.upper()
        for pattern in self.SENSITIVE_PATTERNS:
            if re.match(pattern, key_upper):
                return True
        return False
    
    def _calculate_entropy(self, string: str) -> float:
        """
        Calculate Shannon entropy (0.0 to 1.0)
        
        High entropy = random-looking string (likely a secret)
        Low entropy = repetitive string (likely not a secret)
        
        Examples:
          "aaaaaaaaaa" → low entropy
          "K7x!mQ2#pL" → high entropy
          "password123" → medium entropy
        """
        if not string:
            return 0.0
        
        # Count character frequencies
        char_counts = {}
        for char in string:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Calculate Shannon entropy
        length = len(string)
        entropy = 0.0
        
        for count in char_counts.values():
            probability = count / length
            entropy -= probability * math.log2(probability)
        
        # Normalize to 0.0-1.0 range
        # Maximum entropy for a string is log2(unique_chars)
        max_entropy = math.log2(min(len(char_counts), 95))  # 95 printable ASCII chars
        
        if max_entropy == 0:
            return 0.0
        
        normalized = entropy / max_entropy
        return min(normalized, 1.0)


# ─────────────────────────────────────────────────────────────
# Example Usage
# ─────────────────────────────────────────────────────────────

detector = SecretDetector()

environment = {
    'PUID': '1000',  # Not a secret
    'WIREGUARD_PRIVATE_KEY': 'bijL6fcCeVv25izRy3JseahatW9rsd0eCpo5aLricRI=',  # SECRET!
    'API_KEY': '${API_KEY}',  # Variable reference, OK
    'PASSWORD': 'changeme',  # Placeholder, OK
}

secrets = detector.detect_secrets(environment)

for secret in secrets:
    print(f"Found secret: {secret.key}")
    print(f"  Confidence: {secret.confidence:.0%}")
    print(f"  Reason: {secret.reason}")
```

---

## 5. Known Services Database

### Purpose
Pre-configured templates for popular Docker images.

### Implementation

```python
# src/composearr/data/known_services.py

KNOWN_SERVICES = {
    'sonarr': {
        'type': 'media',
        'default_port': 8989,
        'healthcheck_endpoint': '/api/v3/health',
        'requires_timezone': True,
        'requires_puid_pgid': True,
        'typical_resources': {'cpu': '1.0', 'memory': '512M'},
        'arr_stack': True,
    },
    'radarr': {
        'type': 'media',
        'default_port': 7878,
        'healthcheck_endpoint': '/api/v3/health',
        'requires_timezone': True,
        'requires_puid_pgid': True,
        'typical_resources': {'cpu': '1.0', 'memory': '512M'},
        'arr_stack': True,
    },
    'plex': {
        'type': 'media',
        'default_port': 32400,
        'healthcheck_endpoint': '/identity',
        'requires_timezone': True,
        'typical_resources': {'cpu': '4.0', 'memory': '2G'},
    },
    'qbittorrent': {
        'type': 'download',
        'default_port': 8080,
        'healthcheck_endpoint': '/api/v2/app/version',
        'typical_resources': {'cpu': '1.0', 'memory': '512M'},
    },
    'gluetun': {
        'type': 'vpn',
        'requires_net_admin': True,
        'requires_root': True,
        'typical_resources': {'cpu': '0.5', 'memory': '256M'},
    },
}

def detect_service_type(image: str) -> Optional[dict]:
    """Detect service configuration from image name"""
    image_lower = image.lower()
    
    for service_name, config in KNOWN_SERVICES.items():
        if service_name in image_lower:
            return config
    
    return None
```

---

## Integration Examples

### CA001 with Tag Analyzer

```python
class NoLatestTag(BaseRule):
    def check(self, context) -> List[LintIssue]:
        analyzer = TagAnalyzer()
        
        for service_name, service in context.services.items():
            image = service.get('image', '')
            
            if ':latest' in image:
                suggestion = analyzer.analyze_image(image)
                
                if suggestion:
                    fix = f"Change to: {suggestion.image}:{suggestion.recommended_tag}"
                    learn_more = suggestion.reasoning
                else:
                    fix = "Pin to a specific version"
                    learn_more = None
                
                yield LintIssue(
                    rule_id="CA001",
                    message="Image uses :latest tag",
                    suggested_fix=fix,
                    learn_more=learn_more
                )
```

### CA204 with System Profiler

```python
class RequireResourceLimits(BaseRule):
    def check(self, context) -> List[LintIssue]:
        profiler = SystemProfiler()
        
        for service_name, service in context.services.items():
            if 'deploy' not in service or 'resources' not in service['deploy']:
                # No limits set
                suggestion = profiler.suggest_resources(
                    service_name,
                    service.get('image', '')
                )
                
                fix = f"""Add to compose.yaml:
deploy:
  resources:
    limits:
      cpus: '{suggestion.cpu_limit}'
      memory: {suggestion.memory_limit}
"""
                
                yield LintIssue(
                    rule_id="CA204",
                    message="Missing resource limits",
                    suggested_fix=fix,
                    learn_more=suggestion.reasoning
                )
```

---

## Configuration

Smart features can be configured in `.composearr.yml`:

```yaml
smart_features:
  tag_analyzer:
    enabled: true
    timeout: 5  # seconds
    cache_duration: 3600  # seconds
  
  system_profiler:
    enabled: true
    suggest_from_current_usage: true  # Check running containers
  
  healthcheck_helper:
    enabled: true
    prefer_http_checks: true  # Over process checks
  
  secret_detector:
    min_entropy: 0.6  # 0.0-1.0
    min_length: 20
    enabled: true
```

---

## Error Handling

All smart features should:
1. **Never crash** - catch all exceptions
2. **Gracefully degrade** - if API is down, skip that feature
3. **Timeout quickly** - don't hang on slow APIs (5s max)
4. **Cache results** - don't hammer APIs

```python
def analyze_image_safe(image: str) -> Optional[TagSuggestion]:
    """Wrapper with error handling"""
    try:
        analyzer = TagAnalyzer()
        return analyzer.analyze_image(image)
    except requests.Timeout:
        # API timeout - just skip
        return None
    except Exception as e:
        # Log but don't crash
        logger.debug(f"Tag analysis failed for {image}: {e}")
        return None
```

---

## SUMMARY

Smart features make ComposeArr intelligent:
- ✅ **Tag Analyzer** - Fetches real tags from registries
- ✅ **System Profiler** - Suggests limits based on actual resources
- ✅ **Healthcheck Helper** - Generates service-specific checks
- ✅ **Secret Detector** - Pattern + entropy analysis
- ✅ **Known Services** - Pre-configured templates

**All features degrade gracefully and never block the core linting.**

---

**NEXT:** Testing strategy, or shall we let Code Claude start building? 🚀
