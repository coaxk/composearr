# ComposeArr Testing Strategy

Comprehensive testing approach for v0.1 and beyond.

---

## Testing Philosophy

**1. Real-World First**
- Test against Judd's actual 35-service stack
- Real configs have edge cases synthetic tests miss
- If it works on his stack, it works for homelabbers

**2. Fast Feedback**
- Unit tests run in < 5 seconds
- Integration tests run in < 30 seconds
- Full suite runs in < 2 minutes

**3. Regression Prevention**
- Every bug gets a test
- Every new rule gets fixtures
- No manual "seems to work" testing

---

## Test Pyramid

```
        /\
       /  \        E2E Tests (5)
      /____\       - Full audit on real stacks
     /      \      
    /        \     Integration Tests (20)
   /__________\    - Multi-file scenarios
  /            \   
 /              \  Unit Tests (50+)
/________________\ - Individual rules, parsers, formatters
```

---

## 1. UNIT TESTS

### Structure

```
tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures
├── fixtures/
│   ├── valid/
│   │   ├── simple.yaml
│   │   ├── complete.yaml
│   │   └── arrstack.yaml
│   ├── invalid/
│   │   ├── malformed.yaml
│   │   ├── latest-tags.yaml
│   │   └── hardcoded-secrets.yaml
│   └── edge_cases/
│       ├── empty.yaml
│       ├── comments-only.yaml
│       └── nested-includes.yaml
├── test_scanner.py
├── test_rules.py
├── test_formatters.py
├── test_config.py
└── test_smart_features.py
```

### Scanner Tests

```python
# tests/test_scanner.py

import pytest
from pathlib import Path
from composearr.scanner.discovery import discover_compose_files
from composearr.scanner.parser import parse_compose_file
from composearr.scanner.env_resolver import load_env_file

class TestDiscovery:
    """Test file discovery logic"""
    
    def test_finds_compose_yaml(self, tmp_path):
        """Should find compose.yaml files recursively"""
        # Create test structure
        (tmp_path / "service1").mkdir()
        (tmp_path / "service1" / "compose.yaml").write_text("services: {}")
        (tmp_path / "service2").mkdir()
        (tmp_path / "service2" / "compose.yaml").write_text("services: {}")
        
        files = discover_compose_files(tmp_path)
        assert len(files) == 2
    
    def test_ignores_hidden_directories(self, tmp_path):
        """Should skip .git, .github, etc"""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "compose.yaml").write_text("services: {}")
        
        files = discover_compose_files(tmp_path)
        assert len(files) == 0
    
    def test_handles_empty_directory(self, tmp_path):
        """Should return empty list for directory with no compose files"""
        files = discover_compose_files(tmp_path)
        assert files == []

class TestParser:
    """Test YAML parsing"""
    
    def test_parses_valid_compose(self):
        """Should parse valid compose.yaml"""
        yaml_content = """
services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
"""
        compose = parse_compose_string(yaml_content)
        assert 'services' in compose
        assert 'web' in compose['services']
    
    def test_preserves_comments(self):
        """Should preserve comments in YAML"""
        yaml_content = """
# Important comment
services:
  web:
    image: nginx:latest  # Also important
"""
        compose = parse_compose_string(yaml_content)
        # Verify comments are preserved (ruamel.yaml specific)
        assert compose.ca.comment is not None
    
    def test_handles_malformed_yaml(self):
        """Should raise clear error on malformed YAML"""
        yaml_content = """
services:
  web:
    image: nginx:latest
  invalid syntax here
"""
        with pytest.raises(ComposeParseError) as exc:
            parse_compose_string(yaml_content)
        
        assert "line 4" in str(exc.value).lower()
    
    def test_handles_empty_file(self):
        """Should handle empty compose files gracefully"""
        compose = parse_compose_string("")
        assert compose == {} or compose == {'services': {}}

class TestEnvResolver:
    """Test .env file loading and variable resolution"""
    
    def test_loads_env_file(self, tmp_path):
        """Should load key=value pairs from .env"""
        env_file = tmp_path / ".env"
        env_file.write_text("""
PUID=1000
PGID=1000
TZ=Australia/Sydney
""")
        
        env_vars = load_env_file(env_file)
        assert env_vars['PUID'] == '1000'
        assert env_vars['TZ'] == 'Australia/Sydney'
    
    def test_handles_comments(self, tmp_path):
        """Should ignore comments in .env"""
        env_file = tmp_path / ".env"
        env_file.write_text("""
# This is a comment
PUID=1000  # Inline comment
# Another comment
PGID=1000
""")
        
        env_vars = load_env_file(env_file)
        assert len(env_vars) == 2
    
    def test_resolves_variables(self):
        """Should resolve ${VAR} references"""
        env = {'PUID': '1000', 'PGID': '1000'}
        
        resolved = resolve_env_var('${PUID}', env)
        assert resolved == '1000'
        
        resolved = resolve_env_var('${UNKNOWN:-999}', env)
        assert resolved == '999'
```

### Rule Tests

```python
# tests/test_rules.py

import pytest
from composearr.rules.CA0xx_images import NoLatestTag
from composearr.rules.CA1xx_security import NoInlineSecrets
from composearr.rules.CA2xx_reliability import RequireHealthcheck

class TestCA001_NoLatestTag:
    """Test :latest tag detection"""
    
    def test_detects_latest_tag(self):
        """Should flag image:latest"""
        compose = {
            'services': {
                'web': {'image': 'nginx:latest'}
            }
        }
        
        rule = NoLatestTag()
        issues = rule.check(compose)
        
        assert len(issues) == 1
        assert issues[0].rule_id == 'CA001'
        assert 'latest' in issues[0].message.lower()
    
    def test_detects_implicit_latest(self):
        """Should flag image with no tag"""
        compose = {
            'services': {
                'web': {'image': 'nginx'}  # No tag = :latest
            }
        }
        
        rule = NoLatestTag()
        issues = rule.check(compose)
        
        assert len(issues) == 1
    
    def test_ignores_pinned_version(self):
        """Should not flag pinned versions"""
        compose = {
            'services': {
                'web': {'image': 'nginx:1.21.3'}
            }
        }
        
        rule = NoLatestTag()
        issues = rule.check(compose)
        
        assert len(issues) == 0
    
    def test_respects_suppression(self):
        """Should skip if suppressed"""
        compose = {
            'services': {
                'watchtower': {
                    'image': 'containrrr/watchtower:latest',
                    '_suppressed': ['CA001']  # Mock suppression
                }
            }
        }
        
        rule = NoLatestTag()
        issues = rule.check(compose)
        
        assert len(issues) == 0

class TestCA101_NoInlineSecrets:
    """Test secret detection"""
    
    def test_detects_api_key(self):
        """Should flag hardcoded API keys"""
        compose = {
            'services': {
                'app': {
                    'environment': {
                        'API_KEY': 'sk_live_abc123def456'
                    }
                }
            }
        }
        
        rule = NoInlineSecrets()
        issues = rule.check(compose)
        
        assert len(issues) == 1
        assert 'API_KEY' in issues[0].message
    
    def test_ignores_variable_reference(self):
        """Should not flag ${VAR} references"""
        compose = {
            'services': {
                'app': {
                    'environment': {
                        'API_KEY': '${API_KEY}'
                    }
                }
            }
        }
        
        rule = NoInlineSecrets()
        issues = rule.check(compose)
        
        assert len(issues) == 0
    
    def test_ignores_placeholders(self):
        """Should not flag obvious placeholders"""
        compose = {
            'services': {
                'app': {
                    'environment': {
                        'PASSWORD': 'changeme'
                    }
                }
            }
        }
        
        rule = NoInlineSecrets()
        issues = rule.check(compose)
        
        assert len(issues) == 0

class TestCA201_RequireHealthcheck:
    """Test healthcheck requirement"""
    
    def test_flags_missing_healthcheck(self):
        """Should flag services without healthcheck"""
        compose = {
            'services': {
                'web': {
                    'image': 'nginx:1.21',
                    # No healthcheck
                }
            }
        }
        
        rule = RequireHealthcheck()
        issues = rule.check(compose)
        
        assert len(issues) == 1
        assert 'healthcheck' in issues[0].message.lower()
    
    def test_ignores_databases(self):
        """Should skip databases (they have internal health)"""
        compose = {
            'services': {
                'db': {
                    'image': 'postgres:14'
                    # No healthcheck - but that's OK
                }
            }
        }
        
        rule = RequireHealthcheck()
        issues = rule.check(compose)
        
        assert len(issues) == 0
```

### Cross-File Tests

```python
# tests/test_cross_file.py

class TestCA301_PortConflict:
    """Test cross-file port conflict detection"""
    
    def test_detects_same_host_port(self):
        """Should flag when two services use same host port"""
        file1 = {
            'services': {
                'sonarr': {
                    'ports': ['8080:8989']
                }
            }
        }
        
        file2 = {
            'services': {
                'radarr': {
                    'ports': ['8080:7878']
                }
            }
        }
        
        rule = PortConflict()
        issues = rule.check_cross_file([file1, file2])
        
        assert len(issues) == 1
        assert '8080' in issues[0].message
        assert 'sonarr' in issues[0].message
        assert 'radarr' in issues[0].message
    
    def test_ignores_different_interfaces(self):
        """Should not flag if bound to different IPs"""
        file1 = {
            'services': {
                'sonarr': {
                    'ports': ['127.0.0.1:8080:8989']
                }
            }
        }
        
        file2 = {
            'services': {
                'radarr': {
                    'ports': ['192.168.1.10:8080:7878']
                }
            }
        }
        
        rule = PortConflict()
        issues = rule.check_cross_file([file1, file2])
        
        assert len(issues) == 0

class TestCA401_PuidMismatch:
    """Test PUID/PGID consistency"""
    
    def test_detects_mismatch(self):
        """Should flag inconsistent PUID across services"""
        files = [
            {'services': {'sonarr': {'environment': {'PUID': '1000'}}}},
            {'services': {'radarr': {'environment': {'PUID': '1000'}}}},
            {'services': {'qbit': {'environment': {'PUID': '568'}}}},
        ]
        
        rule = PuidMismatch()
        issues = rule.check_cross_file(files)
        
        assert len(issues) == 1
        assert '1000' in issues[0].message
        assert '568' in issues[0].message
```

---

## 2. INTEGRATION TESTS

### Real Stack Testing

```python
# tests/test_integration.py

class TestRealStack:
    """Test against Judd's actual 35-service stack"""
    
    @pytest.fixture
    def judd_stack(self):
        """Path to Judd's real stack"""
        return Path("C:/DockerContainers")
    
    def test_scans_without_crashing(self, judd_stack):
        """Should complete scan without errors"""
        files = discover_compose_files(judd_stack)
        
        assert len(files) > 30  # Should find most services
        
        # Should parse all files
        for file in files:
            compose = parse_compose_file(file)
            assert 'services' in compose
    
    def test_detects_known_issues(self, judd_stack):
        """Should catch the issues we know exist"""
        results = run_audit(judd_stack)
        
        # We know there are PUID mismatches
        puid_issues = [i for i in results if i.rule_id == 'CA401']
        assert len(puid_issues) > 0
        
        # We know there are port conflicts
        port_issues = [i for i in results if i.rule_id == 'CA301']
        assert len(port_issues) > 0
    
    def test_completes_in_reasonable_time(self, judd_stack):
        """Should complete in < 10 seconds"""
        import time
        
        start = time.time()
        results = run_audit(judd_stack)
        elapsed = time.time() - start
        
        assert elapsed < 10.0  # 35 files in < 10 sec
```

### Multi-Service Scenarios

```python
class TestMultiServiceScenarios:
    """Test realistic multi-service setups"""
    
    def test_arrstack_scenario(self, tmp_path):
        """Test typical *arr media stack"""
        # Create realistic *arr stack
        create_service(tmp_path / "sonarr", {
            'image': 'lscr.io/linuxserver/sonarr:latest',
            'environment': {'PUID': '1000', 'UMASK': '022'},
            'volumes': ['/mnt/nas/Media:/media', '/mnt/nas/Torrents:/downloads'],
            'ports': ['8989:8989']
        })
        
        create_service(tmp_path / "radarr", {
            'image': 'lscr.io/linuxserver/radarr:latest',
            'environment': {'PUID': '1000', 'UMASK': '022'},
            'volumes': ['/mnt/nas/Media:/media', '/mnt/nas/Torrents:/downloads'],
            'ports': ['7878:7878']
        })
        
        create_service(tmp_path / "qbittorrent", {
            'image': 'lscr.io/linuxserver/qbittorrent:latest',
            'environment': {'PUID': '568', 'UMASK': '002'},  # Different!
            'volumes': ['/mnt/nas/Torrents:/downloads'],
            'ports': ['8080:8080']
        })
        
        results = run_audit(tmp_path)
        
        # Should catch PUID mismatch
        assert any(i.rule_id == 'CA401' for i in results)
        
        # Should catch UMASK inconsistency
        assert any(i.rule_id == 'CA402' for i in results)
        
        # Should catch hardlink path issues
        assert any(i.rule_id == 'CA601' for i in results)
```

---

## 3. END-TO-END TESTS

### CLI Tests

```python
# tests/test_cli.py

from click.testing import CliRunner
from composearr.cli import app

class TestCLI:
    """Test CLI commands"""
    
    def test_audit_command(self, tmp_path):
        """Test composearr audit"""
        # Create test compose file
        (tmp_path / "compose.yaml").write_text("""
services:
  web:
    image: nginx:latest
""")
        
        runner = CliRunner()
        result = runner.invoke(app, ['audit', str(tmp_path)])
        
        assert result.exit_code == 0
        assert 'CA001' in result.output  # Should detect :latest
    
    def test_rules_command(self):
        """Test composearr rules"""
        runner = CliRunner()
        result = runner.invoke(app, ['rules'])
        
        assert result.exit_code == 0
        assert 'CA001' in result.output
        assert 'no-latest-tag' in result.output
    
    def test_format_json(self, tmp_path):
        """Test --format json output"""
        (tmp_path / "compose.yaml").write_text("""
services:
  web:
    image: nginx:latest
""")
        
        runner = CliRunner()
        result = runner.invoke(app, ['audit', str(tmp_path), '--format', 'json'])
        
        assert result.exit_code == 0
        
        import json
        output = json.loads(result.output)
        assert 'files' in output
        assert 'summary' in output
```

---

## 4. REGRESSION TESTS

### Bug Tracking

Every bug gets a test to prevent regression:

```python
# tests/test_regressions.py

class TestRegressions:
    """Tests for fixed bugs"""
    
    def test_issue_1_komodo_duplicate_detection(self):
        """
        Issue #1: Komodo-managed stacks were scanned as duplicates
        Fixed: Added platform detection and deduplication
        """
        # Test that we properly skip Komodo duplicates
        pass
    
    def test_issue_2_progress_bar_blocking(self):
        """
        Issue #2: Progress bar blocked on slow filesystems
        Fixed: Added timeout and async discovery
        """
        pass
    
    def test_issue_3_port_range_parsing(self):
        """
        Issue #3: Port ranges (8080-8090:80-90) not parsed correctly
        Fixed: Added range expansion in port parser
        """
        compose = {
            'services': {
                'web': {
                    'ports': ['8080-8090:80-90']
                }
            }
        }
        
        ports = parse_port_mappings(compose)
        assert len(ports) == 11  # 8080-8090 inclusive
```

---

## 5. PERFORMANCE TESTS

```python
# tests/test_performance.py

class TestPerformance:
    """Performance benchmarks"""
    
    def test_scan_1000_files_under_30_seconds(self):
        """Should handle large stacks efficiently"""
        # Generate 1000 test compose files
        # Measure scan time
        # Assert < 30 seconds
        pass
    
    def test_cross_file_analysis_scales(self):
        """Cross-file rules should scale linearly"""
        # Test with 10, 50, 100 files
        # Measure time for port conflict detection
        # Assert linear scaling
        pass
```

---

## 6. TESTING WORKFLOW

### Local Development

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_rules.py

# Run specific test
pytest tests/test_rules.py::TestCA001_NoLatestTag::test_detects_latest_tag

# Run with coverage
pytest --cov=composearr --cov-report=html

# Run only fast tests (skip integration/E2E)
pytest -m "not slow"
```

### Pre-Commit Hook

```bash
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: Run tests
        entry: pytest tests/ -m "not slow"
        language: system
        pass_filenames: false
```

### CI/CD (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Run unit tests
        run: pytest tests/ -v --cov=composearr
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 7. TEST DATA FIXTURES

### Fixture Library

```python
# tests/conftest.py

import pytest
from pathlib import Path

@pytest.fixture
def valid_compose():
    """Minimal valid compose file"""
    return {
        'services': {
            'web': {
                'image': 'nginx:1.21',
                'restart': 'unless-stopped',
                'healthcheck': {
                    'test': ['CMD', 'curl', '-f', 'http://localhost'],
                    'interval': '30s'
                }
            }
        }
    }

@pytest.fixture
def arrstack_compose():
    """Typical *arr service"""
    return {
        'services': {
            'sonarr': {
                'image': 'lscr.io/linuxserver/sonarr:latest',
                'environment': {
                    'PUID': '1000',
                    'PGID': '1000',
                    'TZ': 'Australia/Sydney',
                    'UMASK': '002'
                },
                'volumes': [
                    '/mnt/nas:/data'
                ],
                'ports': ['8989:8989'],
                'restart': 'unless-stopped'
            }
        }
    }

@pytest.fixture
def judd_real_stack():
    """Judd's actual 35-service stack"""
    return Path("C:/DockerContainers")
```

---

## 8. COVERAGE TARGETS

### Minimum Coverage

- **Overall:** 80%
- **Rules:** 90% (critical path)
- **Scanner:** 85%
- **Formatters:** 70% (mostly UI code)

### Critical Paths (100% coverage required)

- Port conflict detection
- Secret detection
- PUID/PGID analysis
- Config loading
- Suppression parsing

---

## 9. TESTING CHECKLIST

Before each release:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Tested on Judd's 35-service stack
- [ ] No regressions from previous version
- [ ] Coverage > 80%
- [ ] Performance benchmarks met
- [ ] CLI commands work as expected
- [ ] Documentation examples tested
- [ ] Edge cases handled gracefully

---

## 10. DEBUGGING AIDS

### Useful Test Markers

```python
# Mark slow tests
@pytest.mark.slow
def test_full_stack_audit():
    pass

# Mark integration tests
@pytest.mark.integration
def test_cross_file_analysis():
    pass

# Mark tests that need network
@pytest.mark.network
def test_tag_analyzer_api():
    pass
```

### Debugging Flags

```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Drop into debugger on failure
pytest --pdb

# Only run failed tests from last run
pytest --lf
```

---

## SUMMARY

**Test Coverage:**
- 50+ unit tests (scanner, rules, formatters)
- 20 integration tests (multi-file scenarios)
- 5 E2E tests (full audit workflow)
- Real stack validation (Judd's 35 services)

**Test Speed:**
- Unit: < 5 seconds
- Integration: < 30 seconds
- Full suite: < 2 minutes

**Quality Gates:**
- 80%+ coverage
- All tests passing
- Real stack validation
- Performance benchmarks

**Every release is battle-tested against real homelabs.** ✅
