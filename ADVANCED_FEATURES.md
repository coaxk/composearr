# ComposeArr Advanced Features & Edge Cases
## The Hard Stuff - Make It Perfect

This document covers the advanced features and edge cases that separate a good tool from a great one.

---

## 1. COMPOSE SPEC COMPLEXITY HANDLING

### The Challenge
Docker Compose spec has evolved through multiple versions with backwards compatibility nightmares.

### What Code Claude Must Handle

#### Version Detection
```python
# Detect compose spec version
COMPOSE_VERSIONS = {
    '1': 'Legacy (deprecated)',
    '2': 'v2.x',
    '2.1': 'v2.1',
    '3': 'v3.x (Swarm)',
    '3.8': 'v3.8',
    None: 'Compose Spec (no version)'  # Modern
}

def detect_compose_version(compose: dict) -> str:
    """
    Detect which compose spec version is being used
    and validate accordingly
    """
    version = compose.get('version')
    
    if version is None:
        # Modern Compose Spec (no version field)
        return 'compose-spec'
    
    if version.startswith('3'):
        # Swarm mode - different rules apply
        return 'v3-swarm'
    
    if version.startswith('2'):
        return 'v2'
    
    if version == '1':
        # Ancient, warn user
        return 'v1-deprecated'
    
    return 'unknown'
```

#### Extends & Include (Compose Spec)

**The nightmare scenario:**
```yaml
# base.yaml
services:
  base-service:
    image: nginx:1.21
    restart: unless-stopped

# app.yaml
include:
  - base.yaml

services:
  app:
    extends:
      service: base-service
    ports:
      - "8080:80"
```

**Requirements:**
1. Follow `include` directives recursively (max depth: 5)
2. Merge `extends` properly (override semantics)
3. Detect circular dependencies
4. Preserve file context for error messages

```python
class ComposeIncludeResolver:
    """Resolve include/extends directives"""
    
    MAX_DEPTH = 5
    
    def resolve(self, compose_path: Path) -> dict:
        """
        Resolve all includes and extends, return merged compose
        
        Challenges:
        - Circular includes (base.yaml includes app.yaml includes base.yaml)
        - Deep nesting (5+ levels)
        - Conflicting overrides
        - Preserving line numbers for errors
        """
        visited = set()
        return self._resolve_recursive(compose_path, visited, depth=0)
    
    def _resolve_recursive(
        self, 
        path: Path, 
        visited: set, 
        depth: int
    ) -> dict:
        if depth > self.MAX_DEPTH:
            raise ComposeError(f"Include depth exceeded {self.MAX_DEPTH}")
        
        if path in visited:
            raise ComposeError(f"Circular include: {path}")
        
        visited.add(path)
        
        # Parse base file
        compose = parse_compose_file(path)
        
        # Resolve includes first
        if 'include' in compose:
            for include_path in compose['include']:
                included = self._resolve_recursive(
                    path.parent / include_path,
                    visited.copy(),
                    depth + 1
                )
                compose = self._merge_compose(compose, included)
        
        # Then resolve extends
        for service_name, service in compose.get('services', {}).items():
            if 'extends' in service:
                extended = self._resolve_extends(service['extends'], path)
                service = self._merge_service(extended, service)
        
        return compose
```

#### Profile Support

```yaml
services:
  web:
    image: nginx:latest
    profiles: ["production"]
  
  debug:
    image: nginx:latest
    profiles: ["debug"]
```

**Challenge:** Only lint services in active profile.

```python
def filter_by_profile(compose: dict, active_profiles: List[str]) -> dict:
    """
    Filter services by profile
    
    Default: If no profiles specified, include all services
    If profiles specified: Only include matching services
    """
    if not active_profiles:
        return compose
    
    filtered_services = {}
    
    for name, service in compose.get('services', {}).items():
        service_profiles = service.get('profiles', [])
        
        if not service_profiles:
            # No profile = always included
            filtered_services[name] = service
        elif any(p in active_profiles for p in service_profiles):
            # Profile matches
            filtered_services[name] = service
    
    compose['services'] = filtered_services
    return compose
```

---

## 2. ENVIRONMENT VARIABLE COMPLEXITY

### The Challenge
Multiple ways to define env vars, complex resolution order, nested references.

#### All the Ways to Define Env Vars

```yaml
services:
  app:
    environment:
      # Dict style
      KEY1: value1
      KEY2: ${KEY2}
      KEY3: ${KEY3:-default}
      KEY4: ${KEY3:?error if not set}
    
    # List style
    environment:
      - KEY5=value5
      - KEY6=${KEY6}
    
    # From file
    env_file:
      - .env
      - custom.env
    
    # Inline + reference
    environment:
      COMBINED: "prefix_${VAR}_suffix"
```

**Resolution order:**
1. env_file (first file wins)
2. environment dict/list (overrides env_file)
3. Shell environment (if docker compose run)

```python
class EnvResolver:
    """Complex environment variable resolution"""
    
    def resolve_all_sources(
        self,
        service: dict,
        env_files: List[Path],
        shell_env: dict
    ) -> dict:
        """
        Resolve environment variables from all sources
        
        Order of precedence (highest to lowest):
        1. service.environment (inline)
        2. service.env_file
        3. Shell environment
        """
        
        # Start with shell env (lowest priority)
        resolved = shell_env.copy()
        
        # Layer in env_files (bottom to top)
        for env_file in reversed(env_files):
            if env_file.exists():
                resolved.update(load_env_file(env_file))
        
        # Layer in inline environment (highest priority)
        inline = self._normalize_environment(service.get('environment', {}))
        resolved.update(inline)
        
        # Now resolve all ${VAR} references
        return self._resolve_references(resolved)
    
    def _resolve_references(self, env: dict) -> dict:
        """
        Resolve ${VAR}, ${VAR:-default}, ${VAR:?error}
        
        Challenges:
        - Nested references: ${VAR1_${VAR2}}
        - Circular references: A=${B}, B=${A}
        - Complex syntax: ${VAR:+alternate}
        """
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            changed = False
            
            for key, value in env.items():
                if isinstance(value, str) and '${' in value:
                    new_value = self._resolve_value(value, env)
                    if new_value != value:
                        env[key] = new_value
                        changed = True
            
            if not changed:
                break
            
            iteration += 1
        
        if iteration == max_iterations:
            raise ComposeError("Circular environment variable references detected")
        
        return env
    
    def _resolve_value(self, value: str, env: dict) -> str:
        """
        Resolve a single value with variable references
        
        Supports:
        - ${VAR}
        - ${VAR:-default}
        - ${VAR:?error message}
        - ${VAR:+alternate}
        """
        import re
        
        # Pattern: ${VAR} or ${VAR:-default} or ${VAR:?error}
        pattern = r'\$\{([A-Z_][A-Z0-9_]*)(?:([:\-\?\+])(.+?))?\}'
        
        def replace(match):
            var_name = match.group(1)
            operator = match.group(2)
            operand = match.group(3)
            
            var_value = env.get(var_name)
            
            if operator is None:
                # Simple ${VAR}
                return var_value or ''
            
            elif operator == ':-':
                # ${VAR:-default}
                return var_value if var_value else operand
            
            elif operator == ':?':
                # ${VAR:?error}
                if not var_value:
                    raise ComposeError(f"Required variable {var_name} not set: {operand}")
                return var_value
            
            elif operator == ':+':
                # ${VAR:+alternate}
                return operand if var_value else ''
        
        return re.sub(pattern, replace, value)
```

---

## 3. NETWORK COMPLEXITY

### The Challenge
Multiple network modes, custom bridges, host networking, service dependencies.

#### All Network Configurations

```yaml
# Modern named network
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true

services:
  web:
    networks:
      - frontend
      - backend
  
  # Host network mode
  vpn:
    network_mode: host
  
  # Container network mode
  app:
    network_mode: "service:vpn"
  
  # No network
  batch:
    network_mode: none
  
  # Default bridge (legacy)
  legacy:
    # No networks key = default bridge
```

**Challenge:** Understand network topology for cross-file analysis.

```python
class NetworkTopologyAnalyzer:
    """Analyze network connectivity across all services"""
    
    def build_topology(self, all_files: List[ComposeFile]) -> NetworkGraph:
        """
        Build network graph showing which services can communicate
        
        Rules:
        - Same custom network → Can communicate
        - Both on default bridge → Can communicate (legacy)
        - network_mode: host → Can talk to host
        - network_mode: "service:X" → Shares network with X
        - network_mode: none → Isolated
        """
        graph = NetworkGraph()
        
        for file in all_files:
            for service_name, service in file.services.items():
                network_mode = service.get('network_mode')
                
                if network_mode == 'host':
                    graph.add_node(service_name, type='host')
                
                elif network_mode == 'none':
                    graph.add_node(service_name, type='isolated')
                
                elif network_mode and network_mode.startswith('service:'):
                    # Shares network with another service
                    target = network_mode.split(':', 1)[1]
                    graph.add_edge(service_name, target, type='shared')
                
                else:
                    # Custom networks
                    networks = service.get('networks', ['default'])
                    if isinstance(networks, list):
                        for network in networks:
                            graph.add_to_network(service_name, network)
    
    def find_unreachable_dependencies(self, graph: NetworkGraph) -> List[Issue]:
        """
        Find services that depend_on each other but can't communicate
        
        Example:
          app:
            depends_on: [db]
            network_mode: host
          db:
            networks: [backend]
        
        app can't reach db! (host network can't see custom bridge)
        """
        issues = []
        
        for service in graph.nodes:
            dependencies = service.get('depends_on', [])
            
            for dep in dependencies:
                if not graph.can_communicate(service.name, dep):
                    issues.append(LintIssue(
                        rule_id='CA302',
                        message=f"{service.name} depends on {dep} but they can't communicate",
                        severity=Severity.ERROR
                    ))
        
        return issues
```

---

## 4. VOLUME COMPLEXITY

### The Challenge
Named volumes, bind mounts, tmpfs, volume drivers, read-only flags, SELinux labels.

#### All Volume Syntaxes

```yaml
services:
  app:
    volumes:
      # Short syntax
      - /host/path:/container/path
      - /host/path:/container/path:ro
      - /host/path:/container/path:z  # SELinux
      - named-volume:/data
      - type: volume
        source: named-volume
        target: /data
      
      # Long syntax
      - type: bind
        source: /host/path
        target: /container/path
        read_only: true
      
      # Tmpfs
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 1000000
      
      # Named volume with driver
      - type: volume
        source: nfs-volume
        target: /data
        volume:
          nocopy: true

volumes:
  named-volume:
  nfs-volume:
    driver: local
    driver_opts:
      type: nfs
      o: addr=192.168.1.1,rw
      device: ":/path/to/dir"
```

**Challenge:** Parse all formats, validate paths exist, detect permission issues.

```python
class VolumeParser:
    """Parse all Docker volume syntaxes"""
    
    def parse_volume_spec(self, spec: str | dict) -> VolumeMapping:
        """
        Parse volume specification into structured format
        
        Handles:
        - Short: "/host:/container"
        - Short with opts: "/host:/container:ro,z"
        - Long: {type: bind, source: ..., target: ...}
        - Named: "vol-name:/container"
        - Tmpfs: {type: tmpfs, target: /tmp}
        """
        
        if isinstance(spec, dict):
            return self._parse_long_syntax(spec)
        
        # Short syntax: parse the string
        parts = spec.split(':')
        
        if len(parts) == 1:
            # Anonymous volume: "/container"
            return VolumeMapping(
                type='volume',
                source=None,
                target=parts[0],
                read_only=False
            )
        
        elif len(parts) == 2:
            # "/host:/container" or "named-vol:/container"
            return VolumeMapping(
                type=self._detect_type(parts[0]),
                source=parts[0],
                target=parts[1],
                read_only=False
            )
        
        elif len(parts) >= 3:
            # "/host:/container:opts"
            options = parts[2].split(',')
            
            return VolumeMapping(
                type=self._detect_type(parts[0]),
                source=parts[0],
                target=parts[1],
                read_only='ro' in options,
                selinux_label=self._parse_selinux(options)
            )
    
    def _detect_type(self, source: str) -> str:
        """
        Detect if source is:
        - Absolute path → bind mount
        - Named volume → volume
        - Relative path → ERROR (not allowed)
        """
        if source.startswith('/'):
            return 'bind'
        elif source.startswith('./') or source.startswith('../'):
            raise ComposeError(f"Relative volume paths not allowed: {source}")
        else:
            return 'volume'
```

---

## 5. PORT MAPPING HELL

### All Port Syntaxes

```yaml
services:
  web:
    ports:
      # Short syntax
      - "8080:80"
      - "8080:80/udp"
      - "127.0.0.1:8080:80"
      - "8080-8090:80-90"
      - "127.0.0.1:8080-8090:80-90"
      - "6060:6060/udp"
      
      # Long syntax
      - target: 80
        published: 8080
        protocol: tcp
        mode: host
      
      # IPv6
      - "[::1]:8080:80"
      
      # Published without target (random host port)
      - target: 80
        protocol: tcp
```

**Challenge:** Parse all formats, expand ranges, detect conflicts.

```python
class PortParser:
    """Parse all Docker port mapping syntaxes"""
    
    def parse_port_spec(self, spec: str | dict) -> List[PortMapping]:
        """
        Parse port specification, handling ranges
        
        Returns list because ranges expand to multiple mappings
        """
        
        if isinstance(spec, dict):
            return [self._parse_long_syntax(spec)]
        
        # Parse string format
        # Handle IPv6: [::1]:8080:80
        if spec.startswith('['):
            # IPv6
            end_bracket = spec.index(']')
            host_ip = spec[1:end_bracket]
            rest = spec[end_bracket+2:]  # Skip ']:''
        else:
            # IPv4 or no IP
            parts = spec.split(':', 2)
            if len(parts) == 3:
                host_ip = parts[0]
                rest = ':'.join(parts[1:])
            else:
                host_ip = '0.0.0.0'
                rest = spec
        
        # Parse protocol
        if '/' in rest:
            port_part, protocol = rest.rsplit('/', 1)
        else:
            port_part = rest
            protocol = 'tcp'
        
        # Parse port mapping
        port_parts = port_part.split(':')
        
        if len(port_parts) == 1:
            # Just container port
            return [PortMapping(
                host_ip=None,
                host_port=None,  # Random
                container_port=int(port_parts[0]),
                protocol=protocol
            )]
        
        elif len(port_parts) == 2:
            host, container = port_parts
            
            # Check for ranges
            if '-' in host and '-' in container:
                return self._expand_range(host, container, host_ip, protocol)
            
            return [PortMapping(
                host_ip=host_ip,
                host_port=int(host),
                container_port=int(container),
                protocol=protocol
            )]
    
    def _expand_range(
        self,
        host_range: str,
        container_range: str,
        host_ip: str,
        protocol: str
    ) -> List[PortMapping]:
        """
        Expand port range: 8080-8090:80-90
        
        Returns 11 PortMapping objects
        """
        host_start, host_end = map(int, host_range.split('-'))
        cont_start, cont_end = map(int, container_range.split('-'))
        
        if (host_end - host_start) != (cont_end - cont_start):
            raise ComposeError(
                f"Port range mismatch: {host_range} vs {container_range}"
            )
        
        mappings = []
        for i in range(host_end - host_start + 1):
            mappings.append(PortMapping(
                host_ip=host_ip,
                host_port=host_start + i,
                container_port=cont_start + i,
                protocol=protocol
            ))
        
        return mappings
```

---

## 6. HEALTHCHECK EDGE CASES

### Weird Healthchecks

```yaml
services:
  # Multiple commands
  app1:
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost && curl -f http://localhost:8080"]
  
  # With variables
  app2:
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:${PORT}"]
  
  # Disable inherited healthcheck
  app3:
    healthcheck:
      disable: true
  
  # Complex shell script
  app4:
    healthcheck:
      test: |
        #!/bin/bash
        if [ -f /tmp/healthy ]; then
          exit 0
        else
          exit 1
        fi
```

**Challenge:** Detect actually fake vs legitimately complex.

```python
class HealthcheckAnalyzer:
    """Analyze healthcheck quality"""
    
    def is_fake_healthcheck(self, healthcheck: dict) -> bool:
        """
        Determine if healthcheck is fake
        
        Fake indicators:
        - exit 0
        - true
        - /bin/true
        - echo anything
        
        NOT fake:
        - curl with actual endpoint
        - Process checks
        - File existence checks with logic
        """
        
        test = healthcheck.get('test', [])
        
        if not test:
            return False
        
        # Join command into string for analysis
        if isinstance(test, list):
            command = ' '.join(test)
        else:
            command = test
        
        command_lower = command.lower()
        
        # Obvious fakes
        FAKE_PATTERNS = [
            r'^exit\s+0$',
            r'^true$',
            r'^/bin/true$',
            r'^echo\s+',
            r'^sleep\s+',
        ]
        
        for pattern in FAKE_PATTERNS:
            if re.match(pattern, command_lower):
                return True
        
        # If it's doing actual work, not fake
        REAL_INDICATORS = [
            'curl',
            'wget',
            'nc -z',
            'pgrep',
            'pidof',
            'if \[',  # Actual logic
        ]
        
        return not any(ind in command_lower for ind in REAL_INDICATORS)
```

---

## 7. RESOURCE LIMITS EDGE CASES

### All Resource Limit Formats

```yaml
services:
  # Modern (deploy)
  app1:
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 128M
  
  # Legacy (mem_limit, cpus)
  app2:
    mem_limit: 512m
    cpus: 0.5
  
  # Memory swap
  app3:
    mem_limit: 512m
    mem_swappiness: 60
    memswap_limit: 1g
  
  # Device requests (GPU)
  app4:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

**Challenge:** Handle all formats, convert to consistent representation.

---

## 8. SECRETS HELL

### Compose Secrets

```yaml
# File-based secrets (Compose v2+)
secrets:
  db_password:
    file: ./secrets/db_password.txt
  
  api_key:
    external: true  # Managed outside compose

services:
  app:
    secrets:
      - db_password
      - source: api_key
        target: /run/secrets/api
        uid: '1000'
        gid: '1000'
        mode: 0400
```

**Challenge:** Detect if using Docker secrets vs env vars, validate file paths.

---

## 9. THE ULTIMATE EDGE CASE TEST

```yaml
# This compose file has EVERYTHING
version: "3.8"

include:
  - base.yaml

x-common-vars: &common-vars
  PUID: 1000
  PGID: 1000
  TZ: ${TZ:-UTC}

networks:
  frontend:
    driver: bridge
  backend:
    internal: true

volumes:
  data:
    driver: local

secrets:
  db_pass:
    file: ./secrets/db.txt

services:
  web:
    extends:
      service: base-service
      file: base.yaml
    image: nginx:${NGINX_VERSION:-latest}
    networks:
      - frontend
    ports:
      - "8080-8090:80-90"
      - target: 443
        published: 8443
        protocol: tcp
    volumes:
      - type: bind
        source: /host/path
        target: /data
        read_only: true
      - data:/var/lib/data
    environment:
      <<: *common-vars
      API_KEY: ${API_KEY}
      COMBINED: "prefix_${VAR}_suffix"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:${PORT:-80}/health || exit 1"]
      interval: ${HC_INTERVAL:-30s}
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '${CPU_LIMIT:-1.0}'
          memory: ${MEM_LIMIT:-512M}
    profiles: ["prod"]
    secrets:
      - db_pass
```

**Code Claude must handle ALL of this without crashing.** 😈

---

## 10. ERROR HANDLING REQUIREMENTS

### Every Error Needs Context

```python
class ComposeError(Exception):
    """Base exception with full context"""
    
    def __init__(
        self,
        message: str,
        file_path: Path = None,
        line: int = None,
        column: int = None,
        service: str = None
    ):
        self.message = message
        self.file_path = file_path
        self.line = line
        self.column = column
        self.service = service
        
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error with full context"""
        parts = []
        
        if self.file_path:
            parts.append(f"{self.file_path}")
        
        if self.line:
            parts.append(f"line {self.line}")
        
        if self.service:
            parts.append(f"service '{self.service}'")
        
        location = ":".join(parts) if parts else "unknown"
        
        return f"{location}: {self.message}"

# Usage:
raise ComposeError(
    "Port 8080 already in use",
    file_path=Path("sonarr/compose.yaml"),
    line=7,
    service="sonarr"
)
# Output: sonarr/compose.yaml:line 7:service 'sonarr': Port 8080 already in use
```

---

## DELIVERABLES FOR CODE CLAUDE

**You must handle:**
1. ✅ All Compose spec versions (1, 2, 2.1, 3.x, compose-spec)
2. ✅ Include & extends resolution (max depth 5, circular detection)
3. ✅ Profile filtering
4. ✅ All environment variable syntaxes and resolution
5. ✅ All network modes and topology analysis
6. ✅ All volume syntaxes (short, long, tmpfs, named, drivers)
7. ✅ All port mapping syntaxes (ranges, IPv6, protocols)
8. ✅ Complex healthchecks (multi-command, variables, shell scripts)
9. ✅ All resource limit formats (modern deploy, legacy mem_limit)
10. ✅ Compose secrets (file-based, external)
11. ✅ YAML anchors and merges
12. ✅ Error messages with full file context

**Quality bar:**
- Must parse Judd's 35-service stack without errors
- Must handle the "ultimate edge case test" above
- All errors must include file path, line number, and context
- No crashes on malformed input
- Graceful degradation when optional features missing

---

## IF CODE CLAUDE COMPLETES THIS...

He gets a medal. 🏅

And we ship v0.1 to the world.

**No pressure.** 😏
