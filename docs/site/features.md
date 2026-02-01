# Features

A complete reference for every major feature in Research Automation.

---

## Multi-Agent Orchestration

Research Automation uses a hierarchical agent system where a Master agent routes tasks to six specialized sub-agents.

### Agent Types

| Agent | Role | Default Budget |
|-------|------|----------------|
| **Master** | Orchestrator -- parses requests, routes, merges results | -- |
| **Researcher** | Literature search, paper synthesis, citation management | 15% |
| **Coder** | Code writing, implementation, bug fixes | 35% |
| **Reviewer** | Code quality audits, improvement suggestions | 10% |
| **Falsifier** | Adversarial validation, data leakage checks, statistical audits | 20% |
| **Writer** | Paper sections, documentation, reports | 15% |
| **Cleaner** | Refactoring, optimization, dead code removal | 5% |

### Task Routing

Tasks are routed based on keyword matching. The Master agent analyzes your request and dispatches it to the best-fit sub-agent. For example:

- "Search for papers on attention mechanisms" routes to **Researcher**
- "Implement a data loader for the CSV files" routes to **Coder**
- "Check if there is data leakage in the pipeline" routes to **Falsifier**
- "Write the methods section" routes to **Writer**

### Task DAG Execution

Complex tasks can be decomposed into a directed acyclic graph (DAG) of subtasks. The orchestrator resolves dependencies and runs independent tasks in parallel using `ThreadPoolExecutor`.

When claude-flow is available, swarm execution delegates to the bridge for enhanced coordination.

---

## MCP Auto-Discovery

Research Automation includes a catalog of 70+ Model Context Protocol (MCP) integrations organized into eight tiers. MCPs are loaded automatically based on task keywords.

### Tiers

| Tier | Category | Example MCPs | Loaded When |
|------|----------|-------------|-------------|
| 1 | Essential | paper-search, arxiv, git, github, filesystem, memory, fetch | Always |
| 2 | Data | postgres, sqlite, duckdb, chroma | "database", "sql", "data" |
| 3 | ML/DL | jupyter, huggingface, mlflow, wandb | "model", "training", "neural" |
| 4 | Math | wolfram, sympy | "math", "equation", "derivative" |
| 5 | Paper | latex, overleaf | "paper", "latex", "manuscript" |
| 6 | Communication | slack, gmail, sendgrid | "notify", "email", "slack" |
| 7 | Cloud | aws, docker, terraform | "deploy", "aws", "cloud" |
| 8 | Startup | vercel, gamma, stripe, notion | "website", "slides", "presentation" |

### Tier 0: claude-flow

When claude-flow is installed, it is injected as a tier-0 MCP providing swarm orchestration, HNSW vector memory, and 3-tier model routing.

---

## Overnight Mode

Run autonomous research while you sleep:

```bash
research overnight --iterations 20
```

### How It Works

1. Reads `state/TODO.md` for the task list.
2. Sends each task to Claude via the CLI in `--dangerously-skip-permissions` mode.
3. After each iteration, checks for a `state/DONE` signal file.
4. Auto-commits changes after each completed subtask.
5. Monitors resources and creates checkpoints.
6. Sends notifications on errors or completion (if configured).

### Enhanced Overnight Script

The `scripts/overnight-enhanced.sh` script adds:

- Automatic error recovery and retry logic
- Resource monitoring between iterations
- State snapshots for rollback
- Configurable iteration limits and timeouts

---

## Knowledge Accumulation

Every project maintains a living encyclopedia at `knowledge/ENCYCLOPEDIA.md`.

### Sections

- **Environment** -- System info, package versions, hardware.
- **Machines** -- Local and remote compute resources.
- **Tricks** -- Useful patterns and shortcuts discovered during work.
- **Decisions** -- Design choices and their rationale.
- **What Works** -- Successful approaches for future reference.
- **What Doesn't Work** -- Failed approaches to avoid repeating.

### Auto-Update

After every task, the post-task hook and knowledge module can append new entries. Each entry includes a timestamp for traceability.

### Vector Search

When claude-flow is available, knowledge entries are dual-written to both the markdown file and an HNSW vector index. This enables semantic search over accumulated knowledge using `research memory search "query"`.

### Cross-Project Knowledge

The shared volume (`/shared/knowledge`) enables knowledge transfer across projects. Learnings from one project can inform another.

---

## Paper Pipeline

A complete academic paper workflow:

### LaTeX Template

Every project includes a LaTeX template (`paper/main.tex`) with:

- Standard sections: Abstract, Introduction, Methods, Results, Discussion, Conclusion
- natbib citation support
- Pre-configured packages: amsmath, graphicx, hyperref, booktabs, microtype

### Figure Generation

Publication-quality figures with colorblind-safe defaults:

```python
from core.paper import apply_rcparams, COLORS

apply_rcparams()  # Sets matplotlib to publication quality

# Colorblind-safe palette
COLORS = {
    "blue": "#0077BB",
    "orange": "#EE7733",
    "green": "#009988",
    "red": "#CC3311",
    "purple": "#AA3377",
    "grey": "#BBBBBB",
}
```

Figure specifications:

- Vector PDF output at 300 DPI
- Arial/Helvetica font, 8-10pt
- Single column (3.5in) or double column (7in) widths
- Spines removed from top and right for clean appearance

### Citation Management

```python
from core.paper import add_citation

add_citation(
    "Smith2024",
    author="Smith, J. and Doe, A.",
    title="Efficient Transformers for Scientific Discovery",
    year="2024",
    journal="Nature Machine Intelligence",
    doi="10.1038/s42256-024-00001-1",
)
```

### Compilation

```bash
cd paper && make all
# Or: research paper build
```

Runs `pdflatex` -> `biber` -> `pdflatex` -> `pdflatex` for a complete build.

### Style Transfer

The `core/style_transfer.py` module can analyze the style of a reference paper and apply similar patterns to your writing, with plagiarism checks to ensure originality.

---

## Reproducibility

### Run Logging

Every experiment run is recorded:

```python
from core.reproducibility import RunLog, log_run

run = RunLog(
    run_id="exp_001",
    command="python train.py --lr 0.001",
    parameters={"lr": 0.001, "epochs": 50, "batch_size": 32},
    git_hash="abc1234",
)
log_run(run)
```

Each log captures: command, parameters, metrics, git hash, start/end timestamps, and artifact references.

### Artifact Registry

Artifacts (models, datasets, figures) are registered with SHA-256 checksums:

```python
from core.reproducibility import register_artifact

register_artifact(
    "trained_model",
    path="outputs/model.pt",
    run_id="exp_001",
    metadata={"accuracy": 0.95},
)
```

Integrity can be verified at any time to detect unintended modifications.

### Dataset Hashing

Datasets are hashed to ensure consistency across runs. If a dataset changes unexpectedly, the system flags a warning.

---

## Security

### Secret Scanning

Regex-based detection of API keys, tokens, and private keys in committed files:

- OpenAI keys (`sk-...`)
- GitHub PATs (`ghp_...`)
- AWS credentials
- PEM/private key files
- Generic password/token patterns

### Immutable Files

These paths are never modified by automation:

- `.env`, `.env.local`
- `secrets/*`
- `*.pem`, `*.key`

### Permission Levels

| Level | Examples | Policy |
|-------|----------|--------|
| **Safe** | Read workspace, run Python, git operations | Auto-approve |
| **Moderate** | Network requests, create directories | Log and proceed |
| **Elevated** | Delete files, modify config, push to remote | Ask in interactive, proceed in overnight |
| **Dangerous** | Sudo, modify secrets, spend money, send emails | Always ask |

### Audit Logging

All autonomous actions are recorded in `state/audit.log` with timestamps and action descriptions.

---

## Model Routing

Automatic model selection based on task complexity:

| Complexity | Model | Use Cases |
|-----------|-------|-----------|
| Simple | claude-haiku | Formatting, lookups, classification |
| Medium | claude-sonnet | Code writing, analysis, general tasks |
| Complex | claude-opus | Debugging, architecture, research |
| Critical | claude-opus | Validation, paper writing, production |

### Budget-Aware Fallback

When the remaining budget drops below 20%, all tasks route to Haiku regardless of complexity.

### Thinking Mode Selection

| Task Type | Thinking Mode | Budget Impact |
|-----------|--------------|---------------|
| Simple | None | Minimal |
| Medium | Standard | Normal |
| Complex | Extended | 3% of budget |
| Critical | Ultra-think | Maximum |

---

## Session Management

### Creating Sessions

```bash
research start                          # Auto-named by timestamp
research start --session-name "exp-v2"  # Named session
```

### Session Data

Each session tracks:

- Name and timestamps
- Status (active / completed)
- Token usage estimate
- Tasks completed and failed
- Checkpoint history

### Snapshots and Recovery

Sessions can be snapshotted for recovery. If an error occurs, the on-error hook saves the current state directory for debugging.

---

## Notifications

### Channels

- **Slack** -- Via webhook URL
- **Email** -- Via SMTP (Gmail and others)
- **Desktop** -- Via `notify-send` on Linux

### Throttling

Notifications of the same type are throttled to a configurable interval (default: 5 minutes) to prevent spam during long overnight runs.

### Configuration

```bash
# Set via state/notification_config.json or during project init
{
    "slack_webhook": "https://hooks.slack.com/...",
    "email_to": "you@example.com",
    "desktop_enabled": true,
    "throttle_seconds": 300
}
```

---

## Environment Discovery

The `core/environment.py` module auto-detects:

- Operating system and version
- Python version
- CPU architecture
- GPU availability and model
- RAM capacity
- Conda and Docker availability

This information is written to the project encyclopedia during initialization and used for resource-aware task planning.

---

## Cross-Repository Coordination

### Linking Repos

```python
from core.cross_repo import link_repo

link_repo("data-pipeline", "/path/to/data-pipeline", permissions=["read", "write"])
```

### Coordinated Commits

Push the same commit message across linked repos:

```python
from core.cross_repo import coordinated_commit

coordinated_commit("Sync shared schema v2", repos=["data-pipeline", "analysis"])
```

### Permission Boundaries

Each linked repo has explicit permission grants. Cross-repo actions require matching permissions, preventing unauthorized modifications.

---

## Autonomous Routines

Schedule recurring tasks:

```python
from core.autonomous import ScheduledRoutine, add_routine

routine = ScheduledRoutine(
    name="nightly-validation",
    description="Re-run all experiments and check reproducibility",
    schedule="daily",
    command="research overnight --iterations 5",
)
add_routine(routine)
```

### Confirmation Gates

Routines that involve spending money or sending external communications require explicit user confirmation, even in autonomous mode.
