# Features

A complete reference for every major feature in ricet.

---

## Multi-Agent Orchestration

ricet uses a hierarchical agent system where a Master agent routes tasks to six specialized sub-agents.

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

Tasks are routed using Claude CLI intelligence (with keyword fallback). The Master agent analyzes your request and dispatches it to the best-fit sub-agent. For example:

- "Search for papers on attention mechanisms" routes to **Researcher**
- "Implement a data loader for the CSV files" routes to **Coder**
- "Check if there is data leakage in the pipeline" routes to **Falsifier**
- "Write the methods section" routes to **Writer**

### Task DAG Execution

Complex tasks can be decomposed into a directed acyclic graph (DAG) of subtasks. The orchestrator resolves dependencies and runs independent tasks in parallel using `ThreadPoolExecutor`.

When claude-flow is available, swarm execution delegates to the bridge for enhanced coordination.

---

## MCP Auto-Discovery

ricet includes a catalog of 70+ Model Context Protocol (MCP) integrations organized into eight tiers. MCPs are loaded automatically based on task keywords.

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
ricet overnight --iterations 20
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

When claude-flow is available, knowledge entries are dual-written to both the markdown file and an HNSW vector index. This enables semantic search over accumulated knowledge using `ricet memory search "query"`.

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
ricet start                          # Auto-named by timestamp
ricet start --session-name "exp-v2"  # Named session
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

Via CLI:

```bash
ricet link /path/to/data-pipeline --name data
ricet link /path/to/shared-lib
```

Or programmatically:

```python
from core.cross_repo import link_repository

link_repository("data-pipeline", "/path/to/data-pipeline", permissions=["read", "write"])
```

### Coordinated Commits

Push the same commit message across linked repos:

```python
from core.cross_repo import coordinated_commit

coordinated_commit("Sync shared schema v2", repo_names=["data-pipeline", "analysis"])
```

### RAG Indexing

Linked repos are automatically indexed for search:

```python
from core.cross_repo import index_linked_repo, search_all_linked, reindex_all

# Index a single repo
index_linked_repo(repo)

# Search across all linked repos
results = search_all_linked("attention mechanism")

# Re-index everything
reindex_all()
```

### Permission Boundaries

Each linked repo has explicit permission grants. Cross-repo actions require matching permissions, preventing unauthorized modifications. Linked repos default to read-only.

---

## Auto-Commit & Push

Every state-modifying CLI command automatically commits and pushes changes to git. This ensures your work is always versioned and backed up.

### Configuration

Control via environment variables:

```bash
export RICET_AUTO_COMMIT=true   # Enable/disable (default: true)
export AUTO_PUSH=true           # Push after commit (default: true)
```

### Covered Commands

Auto-commit runs after: `init`, `start`, `config`, `overnight`, `paper build`, `verify`, `debug`, `projects register`, `worktree add`, `worktree remove`. Read-only commands (`status`, `agents`, `memory`, `metrics`) are excluded.

---

## Claude-Powered Intelligence

Seven core modules use the Claude CLI for intelligent decisions before falling back to keyword heuristics:

| Module | Function | What Claude Decides |
|--------|----------|-------------------|
| `agents` | `route_task` | Best agent type for a task |
| `model_router` | `classify_task_complexity` | Simple / medium / complex / critical |
| `auto_debug` | `suggest_fix` | One-sentence fix for an error |
| `doability` | `assess_doability` | Feasibility assessment with scores |
| `prompt_suggestions` | `suggest_next_steps` | Next 3-5 research steps |
| `verification` | `_extract_factual_sentences` | Claims with confidence scores |
| `onboarding` | `install_inferred_packages` | Alternative packages on failure |

### Disabling Claude Calls

Set `RICET_NO_CLAUDE=true` to disable Claude CLI calls (useful for CI or offline work). All functions fall back gracefully to keyword heuristics.

---

## Adopt Existing Repositories

Transform any existing GitHub repo into a ricet project with one command:

```bash
# Fork + clone + scaffold (recommended -- keeps original intact)
ricet adopt https://github.com/user/repo

# Clone without forking
ricet adopt https://github.com/user/repo --no-fork

# Scaffold a local directory in place
ricet adopt /path/to/local/repo

# Custom name and target directory
ricet adopt https://github.com/user/repo --name my-project --path ~/research
```

### What Adopt Does

1. **Forks** the repo via `gh repo fork --clone` (preserves the original).
2. **Overlays** the ricet workspace structure: `knowledge/`, `state/`, `config/`, `paper/`.
3. **Pre-fills** `knowledge/GOAL.md` from the repository README.
4. **Registers** the project in `~/.ricet/projects.json`.
5. **Auto-commits** the scaffolding changes.

### When to Use

- Bringing an old research repo under ricet management.
- Starting a new contribution to an open-source project.
- Setting up a collaborator's fork with ricet tooling.

---

## Collaborative Research

Multiple researchers can work on the same ricet repository without conflicts.

### How It Works

1. **Sync on start**: `ricet start` runs `git pull --rebase` before beginning the session.
2. **User attribution**: Every encyclopedia entry includes the user's git email.
3. **Merge-friendly files**: `.gitattributes` uses `merge=union` for append-only files (`ENCYCLOPEDIA.md`, `PROGRESS.md`), which auto-merges without conflicts.

### Setup

Collaboration works automatically. Just ensure both researchers have push access to the repository and run `ricet start` at the beginning of each session.

---

## Cross-Repository RAG

Link external repositories so agents can search across all your code while only writing to the current project.

### Linking Repos

```bash
# Link a repository for RAG search (read-only by default)
ricet link /path/to/other-repo --name my-lib

# Auto-named from directory name
ricet link /path/to/data-pipeline

# Re-index all linked repos
ricet reindex

# Remove a linked repo
ricet unlink my-lib
```

### How Indexing Works

Linked repos are walked recursively. Files with extensions `.py`, `.md`, `.txt`, `.tex`, `.rst`, `.yml`, `.yaml`, `.json` are indexed. Hidden directories, `node_modules`, and `.git` are skipped.

When claude-flow is available, files are stored in HNSW vector memory for semantic search. Otherwise, a local JSON index is created under `state/linked_indexes/`.

### Searching

Cross-repo results are automatically included when you search knowledge:

```bash
ricet memory "attention mechanism implementation"
```

Results from linked repos are tagged with their source name (e.g. `[my-lib] def attention(...)`).

### Permission Boundaries

Linked repos default to `["read"]` permissions. The permission system prevents any write operations to linked repos, ensuring you can search but never accidentally modify external code.

### Connecting Repos During Setup

When initializing a new project, you can link repos immediately after:

```bash
ricet init my-project
cd my-project
ricet link ~/code/shared-utils --name utils
ricet link ~/code/data-pipeline --name data
ricet start   # linked repos are re-indexed on every start
```

### Connecting Repos Later

You can link and unlink repos at any time during active development:

```bash
# In your existing project directory
ricet link /path/to/new-dependency
ricet reindex   # manual re-index (also happens on ricet start)
```

---

## Auto-Documentation

When you develop new code in a ricet project, documentation can update automatically.

### Manual Trigger

```bash
ricet docs           # scan project, update docs/API.md, README.md, docs/MODULES.md
ricet docs --force   # run even if RICET_AUTO_DOCS is not set
```

### Automatic Mode

Set `RICET_AUTO_DOCS=true` to have documentation update after every state-modifying ricet command (via the auto-commit hook) and after every Claude task (via the post-task shell hook).

What gets generated:

| File | Content |
|------|---------|
| `docs/API.md` | API reference with function signatures and docstrings |
| `docs/MODULES.md` | Table of all modules with public item counts |
| `README.md` | Missing CLI commands appended to the command table |

Existing content is never overwritten -- only new modules and commands are appended. The system scans `src/`, `lib/`, `core/`, `app/` and any top-level directories containing `.py` files.

### How It Works

1. AST-parses every `.py` file in source directories.
2. Extracts public functions and classes (skips `_private` names).
3. Compares against existing `docs/API.md` and `README.md`.
4. Appends markdown stubs for anything missing.
5. Regenerates `docs/MODULES.md` as a full index.

---

## Autonomous Routines

Schedule recurring tasks:

```python
from core.autonomous import ScheduledRoutine, add_routine

routine = ScheduledRoutine(
    name="nightly-validation",
    description="Re-run all experiments and check reproducibility",
    schedule="daily",
    command="ricet overnight --iterations 5",
)
add_routine(routine)
```

### Confirmation Gates

Routines that involve spending money or sending external communications require explicit user confirmation, even in autonomous mode.

---

## Literature Search & Citation

Discover and cite papers directly from the CLI:

```bash
# Search for papers by topic
ricet cite "attention mechanisms in transformers"

# Discover related work across multiple databases
ricet discover "graph neural networks for drug discovery"
```

`ricet cite` searches Semantic Scholar and arXiv, formats results as BibTeX entries, and appends them to `paper/references.bib`. `ricet discover` performs a broader literature scan, returning ranked results with abstracts and citation counts.

---

## Style Transfer

Analyze a reference paper's writing style and apply it to your own manuscript:

```bash
ricet paper adapt-style --reference path/to/reference.pdf
```

The style transfer module extracts stylistic patterns (sentence structure, formality, section conventions) from the reference and rewrites your paper sections to match, with plagiarism checks to ensure originality.

---

## Automated Test Generation

Automatically generate tests for new or modified source files:

```bash
ricet test-gen
```

Scans the project for source files that lack corresponding test coverage and generates pytest-compatible test stubs. Uses Claude to analyze function signatures, docstrings, and usage patterns for meaningful test cases.

---

## Package Management

Create, build, and publish Python packages from your research code:

```bash
ricet package init     # Scaffold pyproject.toml, setup.cfg, package structure
ricet package build    # Build sdist and wheel
ricet package publish  # Publish to PyPI (or TestPyPI with --test)
```

Useful for turning experiment code into reusable libraries that other projects can depend on.

---

## Daily Maintenance

Run all standard health checks in a single command:

```bash
ricet maintain
```

Executes four daily routines:

| Routine | Description |
|---------|-------------|
| `test-gen` | Auto-generate tests for new/changed source files |
| `docs-update` | Auto-update project documentation from source |
| `fidelity-check` | Check GOAL.md alignment and flag drift |
| `verify-pass` | Run verification on recent outputs |

Maintenance runs automatically at the end of every `ricet overnight` session, ensuring the project stays healthy between human check-ins.

---

## Goal Fidelity

Check whether the project is still aligned with its stated research goal:

```bash
ricet fidelity
```

Compares the current state of the codebase and outputs against `knowledge/GOAL.md`. Returns a fidelity score (0-100) and flags specific drift areas with recommendations. Integrated into overnight mode as a pre-flight check.

---

## Cross-Project Learning

Share learnings between ricet projects:

```bash
ricet sync-learnings
```

Reads the current project's encyclopedia and publishes key patterns, decisions, and what-works/what-doesn't entries to a shared knowledge volume. Other ricet projects can pull these learnings to bootstrap their own knowledge base.

---

## MCP Server Discovery

Search a catalog of 1300+ Model Context Protocol servers and install them on demand:

```bash
ricet mcp-search "database migration"
```

Results include server name, description, install command, and compatibility info. Select a result to install it directly into your project's MCP configuration.

---

## Dual-Repository Structure

Manage a clean separation between experimental and production code:

```bash
ricet two-repo init       # Set up experiments/ and clean/ directories
ricet two-repo promote    # Promote validated code from experiments/ to clean/
ricet two-repo status     # Show what's in each side
```

The `experiments/` directory is for rapid iteration; `clean/` holds reviewed, tested code. Promotion requires passing verification checks.

---

## URL Browsing

Fetch and extract text from any URL for use in literature review:

```bash
ricet browse https://example.com/paper-landing-page
```

Uses headless browser automation when available (Puppeteer MCP), falling back to HTTP fetch. Extracts readable text content and stores it in the project knowledge base.

---

## Infrastructure Management

Run infrastructure checks, Docker builds, CI/CD setup, and secrets management:

```bash
ricet infra check     # Verify Docker, CI, dependencies
ricet infra build     # Build project Docker image
ricet infra secrets   # Manage project secrets
ricet infra ci        # Generate/update CI workflow files
```

---

## Runbook Execution

Parse and execute code blocks from a markdown runbook:

```bash
ricet runbook docs/setup-runbook.md
```

Extracts fenced code blocks from the markdown file and executes them sequentially, reporting pass/fail for each step. Useful for onboarding, environment setup, and reproducible deployment procedures.

---

## Autonomous Overnight Enhancements

### Docker Sandbox

Run overnight sessions inside a Docker container for full isolation:

```bash
ricet overnight --iterations 30 --docker
```

Automatically builds the `ricet:latest` image if it does not exist, mounts the project directory and Claude credentials, then runs the overnight loop inside the container.

### Falsifier Auto-Trigger

After every overnight iteration, the falsifier agent automatically validates results. It checks for data leakage, statistical validity, confounders, and reproducibility issues. No manual intervention needed.

### Resource-Aware Scheduling

Overnight mode monitors CPU, RAM, and disk usage between iterations. If resources drop below safe thresholds, the run pauses and checkpoints. High memory triggers an automatic checkpoint commit. Old checkpoints are cleaned up to free disk space.

---

## Automated Research Workflow

Run the full research automation pipeline:

```bash
ricet auto add-routine --name nightly-check --command "ricet verify" --schedule daily
ricet auto list-routines
ricet auto monitor --topic "large language models"
```

### Reproducibility Tracking

```bash
ricet repro log --command "python train.py" --run-id exp-001
ricet repro list
ricet repro show --run-id exp-001
ricet repro hash --path data/dataset.csv
```

Every experiment run is logged with parameters, git hash, metrics, and SHA-256 artifact checksums.
