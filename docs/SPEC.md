# Research Automation Specification

## Overview

Research Automation is a CLI tool and framework for managing scientific research projects
with Claude Code. It provides multi-agent orchestration, knowledge persistence,
reproducibility enforcement, and paper pipeline automation.

## Architecture

```
cli/                    # User-facing CLI commands
  main.py               # Typer CLI entry point
  dashboard.py           # TUI dashboard
  gallery.py             # Figure gallery

core/                   # Business logic modules
  agents.py              # Agent orchestration, task DAG, parallel execution
  knowledge.py           # Encyclopedia auto-update
  session.py             # Session management
  tokens.py              # Token budget tracking
  mcps.py                # MCP tier loading
  notifications.py       # Multi-channel notifications
  paper.py               # LaTeX pipeline
  security.py            # Secret scanning, immutable files
  environment.py         # System discovery, conda management
  onboarding.py          # Project initialization questionnaire
  reproducibility.py     # Run logging, artifact registry
  resources.py           # Resource monitoring, checkpoints
  model_router.py        # Multi-model routing, fallback chains
  voice.py               # Audio transcription, prompt structuring
  style_transfer.py      # Paper style analysis, plagiarism checks
  automation_utils.py    # Data handling, experiment running
  meta_rules.py          # Operational rule detection
  cross_repo.py          # Cross-repository coordination
  autonomous.py          # Scheduled routines, monitoring

templates/              # Files copied into new projects
  .claude/               # Agent definitions and system prompts
  .github/workflows/     # CI/CD pipelines
  config/                # Settings templates
  knowledge/             # Goal, encyclopedia, constraints
  paper/                 # LaTeX template
```

## Data Models

### Session
- `name`: string
- `started`: ISO timestamp
- `status`: "active" | "completed"
- `token_estimate`: int
- `tasks_completed`: int
- `tasks_failed`: int
- `checkpoints`: list[string]

### Task
- `id`: string
- `description`: string
- `agent`: AgentType | null
- `deps`: list[string] (dependency task IDs)
- `parallel`: bool
- `status`: "pending" | "running" | "success" | "failure"

### RunLog
- `run_id`: string
- `command`: string
- `started` / `ended`: ISO timestamps
- `status`: string
- `git_hash`: string
- `parameters`: dict
- `metrics`: dict
- `artifacts`: list[string]

### ArtifactRegistry
- Maps artifact name -> {path, checksum, run_id, registered, size_bytes, metadata}
- Supports integrity verification via SHA-256

## Security Model

1. **Secret scanning**: Regex-based detection of API keys, tokens, private keys
2. **Immutable files**: `.env`, `secrets/`, `*.pem`, `*.key` are never modified
3. **Permission boundaries**: Cross-repo actions require explicit permission grants
4. **Audit logging**: All autonomous actions are logged to `state/audit.log`
5. **Confirmation gates**: Purchase suggestions require explicit user confirmation

## Agent Types

| Agent | Role | Budget % |
|-------|------|----------|
| Master | Orchestrator (never executes) | - |
| Researcher | Literature search | 15% |
| Coder | Implementation | 35% |
| Reviewer | Code quality | 10% |
| Falsifier | Validation/attack | 20% |
| Writer | Documentation/paper | 15% |
| Cleaner | Refactoring | 5% |

## MVP Flow

```
1. research init my-project
   -> Onboarding questionnaire
   -> Copy templates
   -> Setup workspace (reference/, local/, secrets/, uploads/)
   -> Write config/settings.yml
   -> Git init

2. research start
   -> Create session
   -> Launch Claude Code with agent system prompts

3. research overnight
   -> Read TODO.md
   -> Execute via Claude CLI in loop
   -> Check for DONE signal

4. research status
   -> Show TODO and Progress

5. research paper build
   -> Compile LaTeX
```

## Model Routing

| Complexity | Model | Use Case |
|-----------|-------|----------|
| Simple | claude-haiku | Formatting, lookups |
| Medium | claude-sonnet | Code writing, analysis |
| Complex | claude-opus | Debugging, architecture |
| Critical | claude-opus | Validation, paper writing |

Budget < 20% remaining -> always route to Haiku.

## Reproducibility

- Every experiment run logged with parameters, metrics, git hash
- Artifacts registered with SHA-256 checksums
- Dataset hashing for integrity verification
- Checkpoint policies with configurable retention

## Claude-Flow Integration

The system integrates with [claude-flow v3](https://github.com/ruvnet/claude-flow) for enhanced
orchestration. All integrations use a graceful fallback pattern: when claude-flow is unavailable,
every module falls back to its original implementation.

### Architecture

```
core/claude_flow.py        # ClaudeFlowBridge wrapping npx claude-flow@v3alpha CLI
scripts/setup_claude_flow.sh   # Node.js check, installation, verification
templates/config/claude-flow.json  # Default config (topology, memory, routing)
```

### Bridge API

| Method | Description | Fallback |
|--------|-------------|----------|
| `spawn_agent(type, task)` | Execute single agent task | Claude CLI subprocess |
| `run_swarm(tasks, topology)` | Multi-agent swarm execution | ThreadPoolExecutor |
| `route_model(description)` | 3-tier model routing | Keyword classification |
| `query_memory(query)` | HNSW semantic search | Keyword grep over markdown |
| `store_memory(text)` | Index in vector memory | Markdown-only append |
| `scan_security(path)` | Security scan | Local regex patterns |
| `get_metrics()` | Token/cost metrics | Char-based estimation |
| `start_session(name)` | Start tracked session | Local JSON file |
| `end_session(name)` | End tracked session | Local JSON update |
| `multi_repo_sync(msg, repos)` | Cross-repo commit | Sequential git commands |

### Fallback Pattern

```python
try:
    bridge = _get_bridge()
    result = bridge.some_method(args)
    return _adapt_result(result)
except ClaudeFlowUnavailable:
    return _legacy_implementation(args)
```

### Agent Type Mapping

| Research Automation | claude-flow |
|-------------------|-------------|
| MASTER | hierarchical-coordinator (queen) |
| RESEARCHER | researcher |
| CODER | coder |
| REVIEWER | code-reviewer |
| FALSIFIER | security-auditor |
| WRITER | api-docs |
| CLEANER | refactorer |

### 3-Tier Model Routing

| Tier | Model | Tasks |
|------|-------|-------|
| Booster | claude-haiku | Simple: formatting, lookups, classification |
| Workhorse | claude-sonnet | Medium: code, analysis, general |
| Oracle | claude-opus | Complex/Critical: reasoning, architecture, validation |

### Files Modified by Integration

**Core modules with bridge integration:**
- `core/agents.py` — spawn_agent, run_swarm, route_model
- `core/model_router.py` — 3-tier routing
- `core/tokens.py` — metrics-based estimation, thinking mode
- `core/session.py` — session start/end
- `core/security.py` — merged scan results
- `core/cross_repo.py` — multi_repo_sync
- `core/resources.py` — merged GPU metrics
- `core/mcps.py` — tier-0 MCP injection
- `core/knowledge.py` — HNSW dual-write, semantic search

**CLI commands:**
- `cli/main.py` — init (setup), start (session), overnight (swarm), status, agents, memory, metrics
- `cli/dashboard.py` — agents panel, resource panel, memory panel

**Templates:**
- `.claude/hooks/*.sh` — claude-flow hook integration
- `.claude/CLAUDE.md` — integration documentation
- `.claude/agents/*.md` — claude-flow-type metadata headers

**Files NOT touched (domain-specific):**
- `core/onboarding.py`, `core/reproducibility.py`, `core/paper.py`
- `core/style_transfer.py`, `core/voice.py`, `core/automation_utils.py`
- `core/meta_rules.py`, `core/notifications.py`, `core/environment.py`
- `core/autonomous.py`, `cli/gallery.py`
