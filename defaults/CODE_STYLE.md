# Code Style (For The Tool Itself)

This guide is for the research-automation tool's own codebase, not user projects.

---

## Language & Version

- Python 3.11+
- Node.js 20+ (for MCP tooling)
- Bash for scripts

---

## Python Standards

### Formatting
- **Black** formatter (line length 88)
- **isort** for import sorting
- **Type hints** on all public functions

### Import Order
```python
# 1. Standard library
import json
import os
from pathlib import Path
from typing import Optional, List, Dict

# 2. Third-party
import typer
from rich.console import Console

# 3. Local
from core.tokens import estimate_tokens
from core.mcps import get_mcps_for_task
```

### Function Signatures
```python
def process_task(
    task_description: str,
    *,
    session_id: Optional[str] = None,
    verbose: bool = False,
) -> dict:
    """Process a task and return results.
    
    Args:
        task_description: What to do.
        session_id: Optional session identifier.
        verbose: Whether to print progress.
    
    Returns:
        Dict with keys: status, result, tokens_used.
    
    Raises:
        ValueError: If task_description is empty.
    """
```

### Patterns to Use
- `pathlib.Path` over `os.path`
- `dataclasses` for data containers
- `typer` for CLI
- `rich` for terminal output
- `pyyaml` for config files
- `pytest` for testing

### Patterns to Avoid
- Global mutable state
- Wildcard imports (`from x import *`)
- Bare `except:` clauses
- `print()` in library code (use `rich.console` or logging)
- Complex inheritance hierarchies

---

## Project Structure

```
research-automation/
├── cli/
│   └── main.py              # Entry point (typer app)
├── core/
│   ├── __init__.py
│   ├── session.py           # Session management
│   ├── agents.py            # Agent orchestration
│   ├── mcps.py              # MCP loading
│   ├── tokens.py            # Token estimation
│   ├── knowledge.py         # Knowledge system
│   └── notifications.py     # Notifications
├── templates/               # Copied to new projects
├── defaults/                # Default configs
├── docker/                  # Docker files
├── scripts/                 # Shell scripts
├── tests/
│   ├── test_session.py
│   ├── test_agents.py
│   └── ...
├── pyproject.toml           # Project config
└── README.md
```

---

## Shell Scripts

### Shebang
```bash
#!/bin/bash
set -euo pipefail
```

### Variables
```bash
# Use lowercase with underscores
project_path="/home/user/project"
session_name="my_session"

# Quote variables
echo "Path: ${project_path}"

# Use defaults
output_dir="${OUTPUT_DIR:-/tmp/outputs}"
```

### Functions
```bash
log_info() {
    echo "[INFO] $(date -Iseconds) | $*"
}

log_error() {
    echo "[ERROR] $(date -Iseconds) | $*" >&2
}
```

---

## Configuration Files

### YAML (preferred for human-edited config)
```yaml
# config.yml
project:
  name: my-project
  type: ml-research

notifications:
  email:
    enabled: true
    address: user@example.com
  slack:
    enabled: false
```

### JSON (for machine-generated config)
```json
{
  "mcpServers": {
    "paper-search": {
      "source": "openags/paper-search-mcp",
      "enabled": true
    }
  }
}
```

---

## Error Handling

```python
from typing import Optional


class ResearchAutomationError(Exception):
    """Base exception for research-automation."""
    pass


class SessionNotFoundError(ResearchAutomationError):
    """Raised when session doesn't exist."""
    pass


class MCPInstallError(ResearchAutomationError):
    """Raised when MCP installation fails."""
    pass


def get_session(session_id: str) -> dict:
    """Get session data.
    
    Raises:
        SessionNotFoundError: If session doesn't exist.
    """
    path = Path(f"state/sessions/{session_id}.json")
    if not path.exists():
        raise SessionNotFoundError(f"Session not found: {session_id}")
    return json.loads(path.read_text())
```

---

## Testing

```python
# tests/test_tokens.py
import pytest
from core.tokens import estimate_tokens, select_thinking_mode


def test_estimate_tokens():
    """Token estimation should be roughly 4 chars per token."""
    text = "a" * 400
    assert estimate_tokens(text) == 100


def test_select_thinking_mode_critical():
    """Critical tasks should get ultrathink."""
    assert select_thinking_mode("validate the paper results") == "ultrathink"


def test_select_thinking_mode_simple():
    """Simple tasks should get no extended thinking."""
    assert select_thinking_mode("list all files") == "none"


@pytest.fixture
def temp_session(tmp_path):
    """Create a temporary session for testing."""
    session_dir = tmp_path / "state" / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "test.json"
    session_file.write_text('{"name": "test", "status": "active"}')
    return session_file
```

---

## Documentation

### Docstrings (Google Style)
```python
def create_project(
    name: str,
    path: Path,
    project_type: str = "ml-research",
) -> Path:
    """Create a new research project.
    
    Creates directory structure, copies templates, initializes git,
    and sets up initial configuration.
    
    Args:
        name: Project name (used for directory and git).
        path: Parent directory where project will be created.
        project_type: Type of project, affects MCP selection.
            Options: "ml-research", "data-analysis", "paper-writing", "general"
    
    Returns:
        Path to the created project directory.
    
    Raises:
        FileExistsError: If project directory already exists.
        ValueError: If project_type is invalid.
    
    Example:
        >>> project_path = create_project("my-study", Path.home() / "research")
        >>> print(project_path)
        /home/user/research/my-study
    """
```

### README Sections
1. What it does (one paragraph)
2. Installation
3. Quick start
4. Usage examples
5. Configuration
6. Contributing

---

## Git Commits

### Format
```
<type>: <subject>

<body>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `docs`: Documentation only
- `test`: Adding tests
- `chore`: Maintenance tasks

### Examples
```
feat: Add overnight mode with auto-debug loop

- Implements iteration loop with configurable max
- Adds auto-debug on failure (3 attempts)
- Adds resource monitoring between iterations
- Sends notification on completion

fix: Handle missing session file gracefully

Previously crashed with unclear error. Now raises
SessionNotFoundError with helpful message.
```

---

## Dependencies

### pyproject.toml
```toml
[project]
name = "research-automation"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "pyyaml>=6.0",
    "chromadb>=0.4.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
    "isort>=5.0.0",
    "mypy>=1.0.0",
]

[project.scripts]
research = "cli.main:app"
```

---

## Minimal Dependencies Philosophy

Only include what's necessary:
- `typer` + `rich`: CLI (both maintained, well-documented)
- `pyyaml`: Config files
- `chromadb`: Vector store for RAG
- `python-dotenv`: Environment variables

Avoid:
- Heavy frameworks when simple functions suffice
- Multiple libraries that do the same thing
- Unmaintained packages
