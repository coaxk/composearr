# ComposeArr Security & Optimization Requirements

## Critical Security and Performance Standards

---

## 1. SECURITY AUDIT REQUIREMENTS

### Input Validation & Sanitization

```python
# src/composearr/security/input_validator.py

import re
from pathlib import Path

class InputValidator:
    """Validate and sanitize all user inputs"""
    
    # Path traversal prevention
    DANGEROUS_PATH_PATTERNS = [
        r'\.\.',           # Parent directory
        r'~',              # Home directory expansion
        r'\$\{',           # Variable expansion
        r'`',              # Command substitution
        r'\|',             # Pipe
        r';',              # Command chaining
        r'&',              # Background execution
    ]
    
    @staticmethod
    def validate_path(path: str) -> Path:
        """
        Validate file path to prevent:
        - Path traversal attacks
        - Symlink attacks
        - Command injection
        """
        
        # Check for dangerous patterns
        for pattern in InputValidator.DANGEROUS_PATH_PATTERNS:
            if re.search(pattern, path):
                raise SecurityError(f"Dangerous pattern detected in path: {pattern}")
        
        # Convert to absolute path
        abs_path = Path(path).resolve()
        
        # Ensure path exists and is readable
        if not abs_path.exists():
            raise ValueError(f"Path does not exist: {path}")
        
        if not abs_path.is_file() and not abs_path.is_dir():
            raise ValueError(f"Path is not a file or directory: {path}")
        
        # Check we have read permission
        if not os.access(abs_path, os.R_OK):
            raise PermissionError(f"No read permission: {path}")
        
        return abs_path
    
    @staticmethod
    def validate_config_value(key: str, value: any) -> any:
        """
        Validate configuration values
        
        Prevent:
        - Code injection via eval()
        - Command injection
        - Resource exhaustion
        """
        
        # String length limits
        if isinstance(value, str):
            if len(value) > 10000:
                raise SecurityError(f"Config value too long: {key}")
        
        # List/dict size limits
        if isinstance(value, (list, dict)):
            if len(value) > 1000:
                raise SecurityError(f"Config collection too large: {key}")
        
        # No executable code
        if isinstance(value, str):
            if any(pattern in value for pattern in ['eval(', 'exec(', '__import__']):
                raise SecurityError(f"Dangerous code pattern in config: {key}")
        
        return value
    
    @staticmethod
    def validate_rule_id(rule_id: str) -> str:
        """
        Validate rule ID format
        
        Must match: CA[0-9]{3}
        """
        if not re.match(r'^CA[0-9]{3}$', rule_id):
            raise ValueError(f"Invalid rule ID format: {rule_id}")
        
        return rule_id
    
    @staticmethod
    def sanitize_output(text: str) -> str:
        """
        Sanitize text before output to prevent:
        - Terminal escape sequence injection
        - ANSI code injection
        """
        
        # Remove control characters except newline/tab
        sanitized = ''.join(
            char for char in text
            if char.isprintable() or char in '\n\t'
        )
        
        return sanitized
```

### File System Security

```python
class FileSystemSecurity:
    """Secure file system operations"""
    
    @staticmethod
    def safe_read_file(path: Path, max_size_mb: int = 10) -> str:
        """
        Safely read file with size limits
        
        Prevents:
        - Memory exhaustion from huge files
        - Zip bombs
        """
        
        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            raise SecurityError(
                f"File too large: {size_mb:.1f}MB (max {max_size_mb}MB)"
            )
        
        # Read with timeout
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            raise SecurityError(f"File is not valid UTF-8: {path}")
    
    @staticmethod
    def safe_write_file(path: Path, content: str) -> None:
        """
        Safely write file with atomic operations
        
        Prevents:
        - Partial writes on crash
        - Race conditions
        """
        
        # Write to temporary file first
        tmp_path = path.with_suffix('.tmp')
        
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename
            tmp_path.replace(path)
        
        except Exception:
            # Clean up temp file on error
            if tmp_path.exists():
                tmp_path.unlink()
            raise
```

### Secret Handling Security

```python
class SecretHandler:
    """Handle secrets securely"""
    
    @staticmethod
    def mask_secret(value: str) -> str:
        """
        Mask secret for display
        
        Shows first 4 and last 4 chars only
        """
        if len(value) <= 8:
            return '***'
        
        return f"{value[:4]}...{value[-4:]}"
    
    @staticmethod
    def secure_compare(a: str, b: str) -> bool:
        """
        Timing-safe string comparison
        
        Prevents timing attacks
        """
        import hmac
        return hmac.compare_digest(a, b)
    
    @staticmethod
    def validate_secret_strength(value: str) -> dict:
        """
        Validate secret strength
        
        Returns analysis of secret quality
        """
        from composearr.analyzers.secret_detector import SecretDetector
        
        detector = SecretDetector()
        entropy = detector._calculate_entropy(value)
        
        return {
            'length': len(value),
            'entropy': entropy,
            'strength': 'strong' if entropy > 0.7 else 'medium' if entropy > 0.5 else 'weak',
            'recommendation': 'Use at least 32 characters with high entropy' if entropy < 0.7 else None
        }
```

### Network Security (API Calls)

```python
class NetworkSecurity:
    """Secure network operations"""
    
    ALLOWED_REGISTRIES = [
        'registry.hub.docker.com',
        'ghcr.io',
        'lscr.io',
        'gcr.io',
        'quay.io',
    ]
    
    @staticmethod
    def validate_registry(url: str) -> bool:
        """
        Validate registry URL is in allowlist
        
        Prevents SSRF attacks
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if hostname not in NetworkSecurity.ALLOWED_REGISTRIES:
            raise SecurityError(f"Registry not in allowlist: {hostname}")
        
        return True
    
    @staticmethod
    def safe_http_request(
        url: str,
        timeout: int = 5,
        max_redirects: int = 3
    ) -> requests.Response:
        """
        Make HTTP request with security controls
        
        Prevents:
        - SSRF
        - Infinite redirects
        - Slowloris attacks
        """
        
        NetworkSecurity.validate_registry(url)
        
        try:
            response = requests.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                max_redirects=max_redirects,
                headers={'User-Agent': 'ComposeArr/0.1.0'}
            )
            
            response.raise_for_status()
            return response
        
        except requests.Timeout:
            raise SecurityError(f"Request timeout: {url}")
        except requests.TooManyRedirects:
            raise SecurityError(f"Too many redirects: {url}")
```

---

## 2. CODE OPTIMIZATION REQUIREMENTS

### Memory Optimization

```python
class MemoryOptimizer:
    """Optimize memory usage"""
    
    @staticmethod
    def stream_large_file(path: Path) -> Iterator[str]:
        """
        Stream large files line-by-line
        
        Instead of loading entire file into memory
        """
        with open(path, 'r') as f:
            for line in f:
                yield line
    
    @staticmethod
    def lazy_parse_compose(path: Path) -> dict:
        """
        Parse only what's needed
        
        Don't load entire compose into memory if we only need one service
        """
        # Use streaming YAML parser for large files
        pass
    
    @staticmethod
    def clear_cache(max_age_hours: int = 24):
        """Clear old cache entries to prevent memory growth"""
        cache_dir = Path.home() / '.cache' / 'composearr'
        cutoff = time.time() - (max_age_hours * 3600)
        
        for cache_file in cache_dir.glob('*.json'):
            if cache_file.stat().st_mtime < cutoff:
                cache_file.unlink()
```

### CPU Optimization

```python
class CPUOptimizer:
    """Optimize CPU usage"""
    
    @staticmethod
    def parallel_parse(files: List[Path]) -> List[dict]:
        """
        Parse files in parallel (if many files)
        
        Use multiprocessing for CPU-bound parsing
        """
        if len(files) < 20:
            # Sequential for small batches (overhead not worth it)
            return [parse_compose_file(f) for f in files]
        
        # Parallel for large batches
        from concurrent.futures import ProcessPoolExecutor
        
        with ProcessPoolExecutor(max_workers=4) as executor:
            return list(executor.map(parse_compose_file, files))
    
    @staticmethod
    def early_exit_on_error():
        """
        Stop processing on first error (if --fail-fast)
        
        Don't waste CPU scanning remaining files
        """
        pass
    
    @staticmethod
    def rule_short_circuit(service: dict, rule: BaseRule) -> bool:
        """
        Skip rule if obviously not applicable
        
        E.g., don't run healthcheck rule on databases
        """
        # Quick pre-checks before expensive rule execution
        if rule.id == 'CA201':  # require-healthcheck
            image = service.get('image', '')
            if any(db in image.lower() for db in ['postgres', 'mysql', 'redis']):
                return True  # Skip this rule
        
        return False
```

### I/O Optimization

```python
class IOOptimizer:
    """Optimize disk I/O"""
    
    @staticmethod
    def batch_file_reads(files: List[Path]) -> dict:
        """
        Batch read multiple files efficiently
        
        Reduce syscalls
        """
        results = {}
        
        # Read files in order (better for disk cache)
        sorted_files = sorted(files)
        
        for file in sorted_files:
            results[file] = file.read_text()
        
        return results
    
    @staticmethod
    def memory_mapped_read(path: Path) -> bytes:
        """
        Use memory-mapped I/O for very large files
        
        Let OS handle paging
        """
        import mmap
        
        with open(path, 'r+b') as f:
            with mmap.mmap(f.fileno(), 0) as mmapped:
                return mmapped.read()
```

---

## 3. DEPENDENCY SECURITY AUDIT

### Automated Dependency Scanning

```yaml
# .github/workflows/security.yml
name: Security Audit

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -e ".[dev]"
      
      # Scan for known vulnerabilities
      - name: Safety check
        run: |
          pip install safety
          safety check --json
      
      # Check for outdated packages
      - name: pip-audit
        run: |
          pip install pip-audit
          pip-audit
      
      # Scan dependencies with Snyk
      - name: Snyk security scan
        uses: snyk/actions/python@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      
      # Bandit security linter
      - name: Bandit scan
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json
      
      - name: Upload security reports
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: |
            bandit-report.json
            safety-report.json
```

### Dependency Pinning

```toml
# pyproject.toml
[project]
dependencies = [
    "typer[all]>=0.12.0,<0.13.0",     # Pin major versions
    "ruamel.yaml>=0.18.0,<0.19.0",    # Breaking changes possible
    "python-dotenv>=1.0.0,<2.0.0",
    "jsonschema>=4.20.0,<5.0.0",
    "inquirerpy>=0.3.4,<0.4.0",
    "requests>=2.31.0,<3.0.0",        # Security patches important
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0,<9.0.0",
    "pytest-cov>=4.1.0,<5.0.0",
    "black>=24.0.0,<25.0.0",
    "ruff>=0.2.0,<0.3.0",
    "mypy>=1.8.0,<2.0.0",
    "bandit>=1.7.0,<2.0.0",          # Security linter
    "safety>=3.0.0,<4.0.0",           # Vulnerability scanner
]
```

---

## 4. STATIC ANALYSIS INTEGRATION

### Pre-commit Security Hooks

```yaml
# .pre-commit-config.yaml
repos:
  # Security scanning
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-r', 'src/', '-ll']
  
  # Secrets detection
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
  
  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
  
  # Code quality
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
```

### Continuous Security Monitoring

```python
# src/composearr/security/monitor.py

class SecurityMonitor:
    """Monitor for security issues at runtime"""
    
    @staticmethod
    def check_permissions():
        """Verify we're not running as root"""
        if os.geteuid() == 0:
            console.print("[yellow]⚠️  Warning: Running as root is not recommended[/]")
    
    @staticmethod
    def check_file_permissions(path: Path):
        """Verify files have safe permissions"""
        stat = path.stat()
        
        # Check if world-writable
        if stat.st_mode & 0o002:
            raise SecurityError(f"File is world-writable: {path}")
        
        # Check if group-writable (warn only)
        if stat.st_mode & 0o020:
            console.print(f"[yellow]Warning: File is group-writable: {path}[/]")
    
    @staticmethod
    def audit_log(action: str, details: dict):
        """Log security-relevant actions"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'user': os.getenv('USER'),
            'details': details
        }
        
        # Write to audit log
        audit_log_path = Path.home() / '.cache' / 'composearr' / 'audit.log'
        with open(audit_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
```

---

## 5. PERFORMANCE PROFILING

### Built-in Profiler

```python
# src/composearr/profiler.py

import cProfile
import pstats
from contextlib import contextmanager

class Profiler:
    """Performance profiling utilities"""
    
    @staticmethod
    @contextmanager
    def profile(output_file: str = None):
        """
        Profile code execution
        
        Usage:
            with Profiler.profile('audit.prof'):
                run_audit(path)
        """
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            yield profiler
        finally:
            profiler.disable()
            
            if output_file:
                profiler.dump_stats(output_file)
            else:
                stats = pstats.Stats(profiler)
                stats.sort_stats('cumulative')
                stats.print_stats(20)  # Top 20 functions
    
    @staticmethod
    def memory_profile(func):
        """
        Decorator to profile memory usage
        
        Usage:
            @Profiler.memory_profile
            def expensive_function():
                pass
        """
        from memory_profiler import profile
        return profile(func)
    
    @staticmethod
    def time_function(func):
        """
        Decorator to time function execution
        
        Usage:
            @Profiler.time_function
            def slow_function():
                pass
        """
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            
            if elapsed > 1.0:  # Log slow functions
                console.print(f"[yellow]Slow: {func.__name__} took {elapsed:.2f}s[/]")
            
            return result
        
        return wrapper
```

### Performance Regression Tests

```python
# tests/test_performance_regression.py

class TestPerformanceRegression:
    """Ensure performance doesn't degrade over time"""
    
    def test_scan_speed_regression(self, benchmark_stack):
        """Scan must not get slower than v0.1.0 baseline"""
        
        BASELINE_TIME = 10.0  # v0.1.0 baseline
        
        start = time.time()
        run_audit(benchmark_stack)
        elapsed = time.time() - start
        
        # Allow 10% regression
        assert elapsed < BASELINE_TIME * 1.1, \
            f"Performance regression: {elapsed:.2f}s vs {BASELINE_TIME}s baseline"
    
    def test_memory_regression(self, benchmark_stack):
        """Memory usage must not exceed v0.1.0 baseline"""
        
        BASELINE_MEMORY_MB = 200
        
        process = psutil.Process()
        initial = process.memory_info().rss / 1024 / 1024
        
        run_audit(benchmark_stack)
        
        peak = process.memory_info().rss / 1024 / 1024
        used = peak - initial
        
        assert used < BASELINE_MEMORY_MB * 1.1, \
            f"Memory regression: {used:.1f}MB vs {BASELINE_MEMORY_MB}MB baseline"
```

---

## 6. RELEASE SECURITY CHECKLIST

### Pre-Release Security Audit

```bash
# scripts/security-audit.sh

#!/bin/bash
set -e

echo "🔒 Running ComposeArr Security Audit..."

# 1. Dependency vulnerabilities
echo "Checking dependencies..."
pip install safety pip-audit
safety check
pip-audit

# 2. Code security scan
echo "Scanning code..."
bandit -r src/ -ll -f screen

# 3. Secret detection
echo "Checking for secrets..."
detect-secrets scan --all-files

# 4. Type checking
echo "Type checking..."
mypy src/

# 5. Code quality
echo "Code quality..."
ruff check src/

# 6. Test coverage
echo "Running tests..."
pytest --cov=composearr --cov-report=term --cov-report=html

# 7. Build package
echo "Building package..."
python -m build

# 8. Check package
echo "Checking package..."
twine check dist/*

echo "✅ Security audit complete!"
```

### Security.md Documentation

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, email security@composearr.dev with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours.

## Security Measures

ComposeArr implements:
- Input validation and sanitization
- Path traversal prevention
- Command injection prevention
- Secure file operations
- Rate limiting on API calls
- Dependency vulnerability scanning

## Known Limitations

ComposeArr trusts:
- Docker Compose files you point it at
- .env files in your project
- Registry APIs (Docker Hub, GHCR)

ComposeArr does NOT:
- Execute arbitrary code
- Modify files without confirmation
- Send data to external services (except registry APIs)
- Require network access (except for smart features)
```

---

## 7. FINAL SECURITY REQUIREMENTS

**Code Claude must ensure:**

1. ✅ No arbitrary code execution (no eval, exec, __import__)
2. ✅ All user input validated and sanitized
3. ✅ Path traversal prevented
4. ✅ Command injection prevented
5. ✅ SSRF prevented (allowlist registries)
6. ✅ Secrets masked in output
7. ✅ File size limits enforced
8. ✅ Timeout limits on all I/O
9. ✅ Atomic file writes
10. ✅ Safe defaults (fail secure, not open)

**Performance requirements:**
1. ✅ < 10s for 35 files
2. ✅ < 200MB memory for 100 files
3. ✅ < 0.5s CLI startup
4. ✅ Caching for repeat scans
5. ✅ Parallel processing when beneficial

**Monitoring:**
1. ✅ Performance profiling available
2. ✅ Memory tracking
3. ✅ Audit logging for security events
4. ✅ Regression tests

---

## INTEGRATION WITH BUILD PROCESS

Add to Code Claude's workflow:

```python
# Before commit
1. Run security audit: ./scripts/security-audit.sh
2. Run performance tests: pytest -m benchmark
3. Check coverage: pytest --cov
4. Verify all checks pass

# Before release
1. Full security scan
2. Dependency audit
3. Performance baseline
4. Sign release artifacts
```

---

**Security and performance are NOT optional.**

**They're the foundation of trust.** 🔒

**Code Claude: Add this to your checklist.** ✅
