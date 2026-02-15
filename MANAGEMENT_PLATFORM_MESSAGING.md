# ComposeArr - Management Platform Detection Messaging

## IMPORTANT UX UPDATE

### Current Behavior (NEEDS IMPROVEMENT)
```
⚠️ Skipped 35 files managed by Komodo
```

**Problem:** Not clear WHY they're skipped or WHAT will be scanned instead.

---

## Required Messaging (IMPLEMENT THIS)

### Detection & Explanation

```python
def show_management_platform_message(
    platform: str,
    skipped_count: int,
    main_files_count: int
) -> None:
    """
    Show clear message about management platform deduplication
    
    Must explain:
    1. What was detected
    2. Why files are being skipped
    3. What WILL be scanned instead
    """
    
    console.print()
    console.print(
        f"[yellow]ℹ️  Detected {platform}-managed stack[/]"
    )
    console.print(
        f"[dim]   Skipped {skipped_count} duplicate compose files that are managed by {platform}.[/]"
    )
    console.print(
        f"[dim]   These are copies of your main compose files.[/]"
    )
    console.print(
        f"[dim]   Scanning {main_files_count} canonical compose files from your stack instead.[/]"
    )
    console.print()

# Example output:
"""
ℹ️  Detected Komodo-managed stack
   Skipped 35 duplicate compose files that are managed by Komodo.
   These are copies of your main compose files.
   Scanning 36 canonical compose files from your stack instead.
"""
```

### Platform-Specific Messages

```python
PLATFORM_MESSAGES = {
    'komodo': {
        'name': 'Komodo',
        'explanation': (
            'Komodo stores copies of your compose files in its repository directory. '
            'We\'re skipping these duplicates and scanning your actual compose files instead.'
        )
    },
    'dockge': {
        'name': 'Dockge',
        'explanation': (
            'Dockge manages compose files in its stacks directory. '
            'We\'re skipping these managed copies and scanning your source files instead.'
        )
    },
    'portainer': {
        'name': 'Portainer',
        'explanation': (
            'Portainer stores compose files in its data directory. '
            'We\'re skipping these managed copies and scanning your original files instead.'
        )
    },
}

def show_detailed_platform_message(platform: str, details: dict) -> None:
    """Show detailed explanation if user wants more info"""
    
    config = PLATFORM_MESSAGES.get(platform)
    
    console.print(f"\n[bold]{config['name']} Detection[/]")
    console.print(f"[dim]{config['explanation']}[/]\n")
    
    console.print("[bold]Files being skipped:[/]")
    for file in details['skipped_files'][:5]:  # Show first 5
        console.print(f"  [dim]• {file}[/]")
    
    if len(details['skipped_files']) > 5:
        console.print(f"  [dim]... and {len(details['skipped_files']) - 5} more[/]")
    
    console.print(f"\n[bold]Files being scanned:[/]")
    for file in details['scanned_files'][:5]:  # Show first 5
        console.print(f"  [green]✓ {file}[/]")
    
    if len(details['scanned_files']) > 5:
        console.print(f"  [dim]... and {len(details['scanned_files']) - 5} more[/]")
```

### Interactive Confirmation (Optional)

```python
def confirm_deduplication(platform: str, details: dict) -> bool:
    """
    Optionally ask user to confirm deduplication strategy
    
    Only show if --interactive flag or uncertain detection
    """
    
    console.print(f"\n[yellow]⚠️  Detected {platform}-managed files[/]")
    console.print(f"[dim]Found {details['duplicate_count']} potential duplicates[/]\n")
    
    choice = typer.confirm(
        f"Skip {platform}-managed duplicates and scan canonical files only?",
        default=True
    )
    
    if choice:
        console.print("[green]✓ Skipping duplicates, scanning canonical files[/]")
    else:
        console.print("[yellow]⚠️  Scanning all files (may show duplicate issues)[/]")
    
    return choice
```

---

## Integration Points

### 1. During Discovery Phase

```python
# src/composearr/scanner/discovery.py

def discover_compose_files(root_path: Path) -> List[Path]:
    """Discover compose files with deduplication"""
    
    # Find all files
    all_files = list(root_path.rglob("**/compose.yaml"))
    
    # Detect management platform
    platform = detect_management_platform(root_path)
    
    if platform:
        # Deduplicate
        canonical_files = deduplicate_managed_stack(all_files, platform)
        
        # Show clear message
        show_management_platform_message(
            platform=platform['name'],
            skipped_count=len(all_files) - len(canonical_files),
            main_files_count=len(canonical_files)
        )
        
        return canonical_files
    
    return all_files
```

### 2. In Summary Output

```python
# Summary should mention deduplication

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 ComposeArr Audit Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scanned:  36 files, 39 services
Skipped:  35 Komodo-managed duplicates  ← MENTION THIS
Found:    8 errors, 81 warnings, 0 info
Time:     7.37 seconds
"""
```

### 3. Verbose Mode Details

```python
# composearr audit --verbose

"""
Discovery phase:
  Found 71 total compose files
  ℹ️  Detected Komodo-managed stack
     Skipped 35 duplicate files managed by Komodo
     Scanning 36 canonical files instead
  
  Canonical files:
    ✓ sonarr/compose.yaml
    ✓ radarr/compose.yaml
    ✓ plex/compose.yaml
    ... (33 more)
  
  Skipped duplicates:
    • komodo/periphery/repos/sonarr-clone/compose.yaml
    • komodo/periphery/repos/radarr-clone/compose.yaml
    ... (33 more)
"""
```

---

## Error Cases

### Unknown Platform Detection

```python
if uncertain_platform_detection():
    console.print(
        "[yellow]⚠️  Possible management platform detected but uncertain[/]"
    )
    console.print(
        "[dim]   Found patterns suggesting Komodo/Dockge/Portainer[/]"
    )
    console.print(
        "[dim]   Scanning all files to be safe[/]"
    )
    console.print(
        "[dim]   Use --deduplicate to force deduplication[/]"
    )
```

### No Deduplication Possible

```python
if cannot_deduplicate():
    console.print(
        "[yellow]⚠️  Management platform detected but cannot determine canonical files[/]"
    )
    console.print(
        "[dim]   Scanning all files (may report duplicate issues)[/]"
    )
    console.print(
        "[dim]   Review results carefully - some issues may appear twice[/]"
    )
```

---

## Configuration Option

```yaml
# .composearr.yml

deduplication:
  enabled: true
  
  # Force specific platform detection
  platform: auto  # auto, komodo, dockge, portainer, none
  
  # Show detailed deduplication info
  verbose: false
  
  # Ask for confirmation before deduplicating
  interactive: false
```

---

## Testing

```python
# tests/test_management_platform_messaging.py

def test_komodo_detection_message(capsys):
    """Test Komodo detection shows clear message"""
    
    # Setup: Create fake Komodo structure
    # ...
    
    # Run discovery
    discover_compose_files(test_path)
    
    # Capture output
    captured = capsys.readouterr()
    
    # Verify message clarity
    assert "Detected Komodo-managed stack" in captured.out
    assert "Skipped 35 duplicate" in captured.out
    assert "Scanning 36 canonical" in captured.out
    assert "managed by Komodo" in captured.out
```

---

## ACTION ITEMS FOR CODE CLAUDE

1. ✅ Update `show_management_platform_message()` with new format
2. ✅ Add detailed explanation about WHY files are skipped
3. ✅ Mention WHAT will be scanned instead
4. ✅ Include duplicate count and canonical count
5. ✅ Show in summary output
6. ✅ Add --verbose details if requested
7. ✅ Test messaging is clear and helpful

**The message must be crystal clear to users who may not understand the concept of "managed duplicates."**

**Make it obvious that we're being smart, not skipping their actual files.** ✨
