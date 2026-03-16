# Features

A complete reference for every major feature in ricet, designed by **Luca Fusar Bassini**.

---

## Research Skills (Slash Commands)

ricet deploys eight research skills as Claude Code slash commands. Each skill is a structured Markdown prompt that gives Claude a complete workflow for a specific research task. Skills are deployed to `.claude/skills/` at `ricet init` and auto-refreshed when ricet is updated.

### Available Skills

| Skill | What it does | Key features |
|-------|-------------|--------------|
| `/lit-review` | Search PubMed/arXiv, synthesize findings | Citation verification, gap analysis, ENCYCLOPEDIA update |
| `/experiment-review` | Six-dimension experiment audit | Traffic-light scoring (RED/YELLOW/GREEN), leakage detection |
| `/paper-draft` | Draft paper sections with lab conventions | AI-detection pass, outline-first workflow, zero fluff enforcement |
| `/falsify` | Adversarial validation (Popper mode) | Permutation tests, leakage checks, code line-by-line audit |
| `/reproduce` | Reproducibility stress test | Multi-seed runs, stability matrix, quantitative verdict |
| `/research-retro` | Session retrospective | Tweetable summary, JSON snapshots for trend tracking |
| `/slides` | Generate polished .pptx presentations | AI-generated schematics, dark theme, 15-25 slide narrative |
| `/overnight` | Autonomous overnight execution | TODO list processing, auto-debug, "Only stop for" rules |

### Skill Design Patterns

Each skill follows consistent design patterns inspired by [gstack](https://github.com/garrytan/gstack):

- **Priority Hierarchy**: Which steps to prioritize when context is limited
- **Important Rules**: Terse numbered list of non-negotiable constraints
- **LEGISLATION citations**: Hard constraints from the project's behavioral rulebook
- **Quality Checklist**: Verify-before-finishing checklist at the end
- **Persistence**: JSON snapshots saved for trend tracking across runs
- **Cross-referencing**: Check for prior reports on the same target

### Task DAG Execution

For complex multi-step tasks, `core/agents.py` provides Task DAG execution with dependency resolution and parallel execution via `ThreadPoolExecutor`. Output ring buffers support mobile-friendly truncated output.

---

## MCP Auto-Discovery

ricet installs 34 MCP integrations at startup, organized into eight tiers. Additional MCPs are loaded automatically based on Opus-powered semantic task analysis.

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

## Persistent Knowledge System

Every project maintains a three-file knowledge system that auto-populates from your interactions:

### Knowledge Files

| File | Purpose | Updated by |
|------|---------|------------|
| `knowledge/RULES.md` | Behavioral rules from user corrections | meta_learn_hook (auto) |
| `knowledge/ENCYCLOPEDIA.md` | Domain knowledge, techniques, what works/fails | meta_learn_hook (auto) |
| `knowledge/DECISION_LOG.md` | Project decisions with rationale | meta_learn_hook (auto) |

### Meta-Learn Hook

The meta-learn hook (`scripts/meta_learn_hook.py`) runs on every user prompt via Claude Code's `UserPromptSubmit` hook. It uses Haiku to extract:
- **Behavioral rules** (corrections, preferences) → RULES.md
- **Domain insights** (techniques, findings) → ENCYCLOPEDIA.md
- **Decisions** (architectural choices with rationale) → DECISION_LOG.md

Quality filters reject garbled text, near-duplicates, and entries shorter than 15 characters.

### Auto-Update

RULES.md is loaded into every session via the CLAUDE.md `@` import directive. ENCYCLOPEDIA.md and DECISION_LOG.md are searched on-demand. Each entry includes a timestamp for traceability.

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
# Or: ricet paper build
```

Runs `pdflatex` -> `biber` -> `pdflatex` -> `pdflatex` for a complete build.

### Style Transfer

The `core/style_transfer.py` module can analyze the style of a reference paper and apply similar patterns to your writing, with plagiarism checks to ensure originality.

---

## Lab/Stable Bipartition

Experimental work lives in `lab/` (chaotic, iterative). When results pass validation, code is promoted to `stable/` with provenance tracking:

```bash
# Experimental work happens in lab/
python lab/analysis.py

# Promote after validation
ricet promote lab/analysis.py
```

Promotion copies the file to `stable/` and creates a provenance JSON file containing:
- Source path and git hash
- Timestamp of promotion
- Falsification result (if run)
- Key metrics at time of promotion

Both directories are created at `ricet init`.

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

Quality-first model selection based on task complexity:

| Complexity | Model | Use Cases |
|-----------|-------|-----------|
| Simple | claude-haiku | Formatting, lookups, classification |
| Medium | claude-sonnet | Code writing, analysis, general tasks |
| Complex | claude-opus | Debugging, architecture, research |
| Critical | claude-opus | Validation, paper writing, production |

### Quality-First Budget Policy

When the remaining budget drops below the configured threshold (default 20%), the router does **not** silently downgrade to a cheaper model. Instead:

- **CRITICAL tasks** (validation, paper writing, falsification) **always** use Opus, regardless of budget. These are never downgraded.
- **Interactive mode**: The user is warned that budget is getting low and asked for explicit confirmation before any downgrade.
- **Overnight / autonomous mode**: Execution pauses and a notification is sent so a human can decide. The system will not continue with a degraded model.

This prevents silent quality degradation that could compromise research results.

### Minimum Quality Tier

A `min_quality_tier` configuration option sets a floor on model selection. For example, setting the floor to `sonnet` means Haiku will never be chosen, regardless of task complexity or budget level. This gives users control over the minimum acceptable quality.

### Model Selection Logging

Every model-selection decision is logged at INFO level with the chosen model, tier, task complexity, remaining budget, and a truncated task description. This allows full auditing of which model was used for which task.

### Configuration

```python
from core.model_router import RouterConfig, ModelTier, configure_router

configure_router(RouterConfig(
    quality_first=True,           # ON by default -- warn/pause instead of silent downgrade
    min_quality_tier=ModelTier.SONNET,  # Never go below Sonnet
    low_budget_threshold_pct=20.0,     # Budget % that triggers the policy
    interactive=True,             # True for interactive sessions, False for overnight
))
```

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

# Create a named personal branch (auto-derived from git email if omitted)
ricet adopt https://github.com/user/repo --branch user-alice
```

### What Adopt Does

1. **Forks** the repo via `gh repo fork --clone` (preserves the original).
2. **Creates a personal branch** (`user-<name>` from git email, or `--branch` value). Creates it on the remote if new.
3. **Overlays** the ricet workspace structure: `knowledge/`, `state/`, `config/`, `paper/`.
4. **Pre-fills** `knowledge/GOAL.md` from the repository README.
5. **Registers** the project in `~/.ricet/projects.json`.
6. **Auto-commits** the scaffolding changes.

### When to Use

- Bringing an old research repo under ricet management.
- Starting a new contribution to an open-source project.
- Setting up a collaborator's fork with ricet tooling.

---

## Collaborative Research (Multi-User Workflow)

Multiple researchers can work on the same ricet repository on their own branches without conflicts.

### How It Works

1. **Personal branches**: Each researcher gets their own `user-*` branch on `ricet adopt`.
2. **Daily sync**: `ricet sync` pulls the latest and pushes your work.
3. **Morning merge**: The lead researcher runs `ricet morning-sync` to merge all user branches into `main`.
4. **User attribution**: Every encyclopedia entry includes the user's git email.
5. **Merge-friendly files**: `.gitattributes` uses `merge=union` for append-only files.

### Daily Workflow

```bash
# Each researcher (once): adopt the repo
ricet adopt https://github.com/lab/project    # → lands on user-alice branch

# Every morning: sync your branch
ricet sync

# Lead researcher: merge everyone's work into main
ricet morning-sync
# Conflict branches are skipped and listed — resolve manually, then re-run
```

### Advanced Options

```bash
ricet morning-sync --main develop     # merge into a different integration branch
ricet morning-sync --no-push          # merge locally but don't push yet
```

---

## Cross-Repository Code Search

Link external repositories so Claude can search across all your code while only writing to the current project.

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

## context-hub: Versioned API Docs for Agents

ricet integrates [context-hub](https://github.com/andrewyng/context-hub) (`chub`) to give coding agents access to accurate, versioned API documentation. This prevents agents from hallucinating library APIs.

```bash
ricet chub search openai              # find available doc sets
ricet chub get openai                 # fetch Python API reference
ricet chub get pandas --lang py       # language-specific variant
ricet chub get openai --full          # complete reference
ricet chub annotate openai "note"     # add a persistent local note
ricet chub feedback openai up         # rate docs as helpful
```

`chub` is auto-installed during `ricet init` (requires Node.js ≥ 18). It is distributed as `npm install -g @aisuite/chub`.

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

## Sandbox Infrastructure

Run autonomous sessions inside a fully isolated Docker sandbox managed by ricet:

```bash
ricet sandbox setup     # Build sandbox image (Ubuntu 24.04 + full toolchain)
ricet sandbox start     # Launch sandbox container
ricet sandbox status    # Check sandbox health and resource usage
ricet sandbox logs      # View sandbox container logs
ricet sandbox extract   # Copy work products from sandbox to host
ricet sandbox backup    # Snapshot the current sandbox state
ricet sandbox destroy   # Tear down the sandbox completely
```

### What the Sandbox Includes

The sandbox image (`ricet-sandbox`) ships with:

- Ubuntu 24.04 with Node.js 20+, Python 3.11, and pip
- Claude Code CLI pre-installed
- Full LaTeX toolchain (texlive-full, biber, latexmk)
- ffmpeg and audio processing libraries
- All ricet Python dependencies
- Your project mounted at `/workspace`
- Claude credentials mounted read-only

### Auto-Backup

During overnight sessions, the sandbox automatically creates backups every 30 minutes. Backups are stored on the host in `sandbox-backups/` with timestamped directories.

### Work Extraction

After a sandbox session completes, extract the results:

```bash
ricet sandbox extract           # Copies sandbox:/workspace → ./sandbox-output/
ricet sandbox extract --path outputs/   # Extract specific directory
```

---

## Slide Deck Generation

Generate polished, presentation-ready `.pptx` decks from your codebase using Claude and AI-generated schematics:

```bash
ricet slides setup      # Copy slide templates into your project (slides/ directory)
ricet slides create     # Claude agent analyzes your project, writes make_slides.py
ricet slides build      # Run the script: generates schematics + builds .pptx
```

### How It Works

1. **Setup**: Templates (`slide_utils.py`, `slides_task.md`, example script) are copied into `slides/`.
2. **Create**: The Slide-Maker agent reads your codebase and `slides_task.md`, then writes `make_slides.py` with a full narrative, schematic prompts, and slide content.
3. **Build**: Running the script calls Nano Banana Pro (Gemini 3 Pro) to generate N schematic diagrams, then assembles the complete `.pptx` deck.

### Nano Banana Pro Schematics

- Model: `gemini-3-pro-image-preview`
- Aspect ratio: 16:9 (matches slide dimensions)
- Resolution: 2K (crisp on projectors)
- Cost: ~$0.02-0.12 per image
- Schematics are full-slide images -- the image IS the slide content

### Slide Templates

| Function | Description |
|----------|-------------|
| `add_title_slide()` | Dark title with accent bar, subtitle, author |
| `add_section_slide()` | Section divider with number and title |
| `add_content_slide()` | Title + bullet points |
| `add_two_column_slide()` | Side-by-side comparison |
| `add_key_metrics_slide()` | Big numbers in a row |
| `add_image_slide()` | Full-slide schematic image |
| `add_closing_slide()` | Thank-you slide |

All slides use a consistent dark theme (teal/blue/gold palette).

### Credential Requirements

Requires a Google API key for Nano Banana Pro. The key is loaded from:
1. `GOOGLE_API_KEY` environment variable
2. Project-level `.env` file
3. Global credential store (`~/.ricet/credentials.env`)

---

## Global Credential Store

Store API keys once and use them across all ricet projects:

```
~/.ricet/credentials.env    # Shared credentials file (chmod 600)
```

### How It Works

During `ricet init`, credentials are collected through a guided walkthrough of 20+ API keys (core, ML, publishing, cloud, integrations). Each entered key is saved to both:
- The project's local `secrets/.env`
- The global `~/.ricet/credentials.env`

New projects automatically inherit all global credentials. Project-level `.env` files can override globals for project-specific keys.

### Security

- The global credential file has `chmod 600` (owner read/write only)
- Stored in `~/.ricet/` (not in any git repository)
- Never committed to version control
- Masked in logs and dashboard output

### Supported Credentials

The onboarding wizard supports 20+ credentials including:

| Category | Keys |
|----------|------|
| Core | `ANTHROPIC_API_KEY`, `GITHUB_TOKEN` |
| ML | `OPENAI_API_KEY`, `HUGGINGFACE_TOKEN`, `WANDB_API_KEY` |
| Search | `SEMANTIC_SCHOLAR_KEY`, `SERP_API_KEY`, `GOOGLE_API_KEY` |
| Publishing | `MEDIUM_TOKEN`, `LINKEDIN_ACCESS_TOKEN` |
| Cloud | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Notifications | `SLACK_WEBHOOK`, SMTP credentials |

---

## Project Updates

Update an existing project with the latest ricet templates, agents, hooks, and skills:

```bash
ricet init my-project --update
```

This overlays the latest template files onto an existing project without overwriting user-modified files. Useful after upgrading ricet to get new agent prompts, hooks, and configuration defaults.

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

---

## Voice Prompting

Transcribe audio instructions and feed them into the agent pipeline:

```bash
ricet voice
```

The voice module:

1. Accepts an audio file (WAV, MP3, FLAC).
2. Transcribes it to text using whisper-cpp or a compatible backend.
3. Detects the language automatically.
4. Structures the transcription into an actionable research prompt.
5. Routes the structured prompt to the appropriate agent.

Useful for capturing ideas on the go or dictating experiment plans.

---

## Mobile & Web Access

Mobile and web access is always enabled -- no configuration needed. During `ricet init`, a Cloudflare Tunnel is automatically set up, providing a public URL with a QR code for instant phone pairing.

### Always-On Architecture

Mobile and web servers start automatically during `ricet init` and with every `ricet start`. No opt-in question is asked -- the feature is always available.

- The HTTPS server runs on port 8443 (mobile) and 8444 (web dashboard)
- A Cloudflare Tunnel is auto-configured for remote access
- QR code is displayed in the terminal for instant phone pairing
- `cloudflared` is auto-installed if not present

### Server Management

```bash
ricet mobile serve          # Start HTTPS server
ricet mobile pair           # Generate bearer token + QR code for pairing
ricet mobile connect-info   # Show connection methods (direct, SSH, tunnel)
ricet mobile tokens         # List active authentication tokens
ricet mobile cert-regen     # Regenerate TLS certificates
ricet mobile status         # Check if server is running
ricet mobile stop           # Stop the server
```

### Security

The mobile server implements defense-in-depth security:

- **TLS encryption** -- Self-signed certificates generated via OpenSSL CLI. SHA-256 fingerprint displayed for verification.
- **Bearer token authentication** -- Only SHA-256 hashes stored on disk (`~/.ricet/mobile_tokens.json`). Plaintext shown once during generation.
- **Rate limiting** -- 10 failed auth attempts from a single IP triggers a 15-minute lockout.

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | PWA dashboard (installable as home screen app) |
| `GET` | `/status` | Server status and queue info |
| `GET` | `/sessions` | List project sessions |
| `GET` | `/progress` | Recent task entries (last 10) |
| `POST` | `/task` | Submit a new task |
| `POST` | `/voice` | Submit voice-transcribed text |
| `GET` | `/projects` | List all registered projects |
| `GET` | `/project/status?name=X` | Get a project's progress |
| `POST` | `/project/task?name=X` | Submit a task to a specific project |
| `POST` | `/project/create` | Create a new project from mobile |
| `GET` | `/dashboard` | Web dashboard (HTML) |
| `GET` | `/dashboard/html` | Alias for web dashboard |
| `GET` | `/agents/output` | Live agent output stream |
| `GET` | `/connect-info` | TLS fingerprint and connection methods |

### Progressive Web App

The built-in PWA (`core/mobile_pwa.py`) provides a native-like mobile experience:

- **Dashboard tab** -- Project list with status badges and progress bars. Auto-refreshes every 30 seconds.
- **Tasks tab** -- Select a project and submit tasks via text input.
- **Voice tab** -- Tap-to-speak voice command input using the Web Speech API. Transcribed text is sent as a task.
- **Monitor tab** -- Live verbose agent output showing what agents are doing in real time.
- **Settings tab** -- Connection info, TLS fingerprint, and token management.
- **Offline support** -- Service worker caches the app shell. API requests degrade gracefully when offline.
- **Installable** -- Supports "Add to Home Screen" on iOS (Safari) and Android (Chrome) with standalone display mode.

### Connection Methods

- **Direct HTTPS** -- Same Wi-Fi network: `https://<local-ip>:8443`
- **SSH tunnel** -- Remote access: `ssh -L 8443:localhost:8443 user@server`
- **WireGuard VPN** -- Peer-to-peer: `https://<wg-ip>:8443`
- **Cloudflare Tunnel** -- Auto-configured during `ricet init`, provides a public URL without opening ports

### Project Creation from Mobile

Create new ricet projects directly from the PWA:

```bash
POST /project/create
Content-Type: application/json
{"name": "my-new-project", "goal": "Investigate attention mechanisms"}
```

See [Mobile Access](mobile.md) for the complete guide.

---

## Interactive Dashboard

A Rich-powered terminal UI for monitoring active sessions:

```bash
ricet dashboard
```

### Panels

- **Agents** -- Active agent types, current tasks, and budget usage.
- **Resources** -- CPU, RAM, GPU, and disk utilization.
- **Memory** -- Recent knowledge entries and vector memory stats.
- **Progress** -- Task completion log and session history.
- **Verbose Agent Output** -- Live output from running agents (last 15 lines per agent). Shows agent name headers and real-time activity.

### Web Dashboard

The dashboard is also accessible via the web at `/dashboard` on the mobile/web server. This renders an HTML version of the same panels, accessible from any browser.

The dashboard auto-refreshes and provides a single-pane view of your project's status.

---

## Figure Gallery

Scan, catalog, and organize experiment figures:

```bash
ricet gallery
```

The gallery module:

- Recursively scans the project for image files (PNG, PDF, SVG).
- Groups figures by run ID and experiment.
- Displays a navigable terminal-based preview.
- Helps quickly select figures for paper inclusion.

---

## Git Worktree Management

Manage parallel experiment branches using git worktrees:

```bash
ricet worktree add feature-branch     # Create a new worktree
ricet worktree list                   # List active worktrees
ricet worktree remove feature-branch  # Remove a worktree
```

Worktrees let you run concurrent experiments on different branches without stashing or switching, keeping each experiment isolated.

---

## Task Queue & Spooler

Manage background task execution:

```bash
ricet queue add "run experiment with lr=0.01"    # Add a task to the queue
ricet queue list                                 # List queued tasks
ricet queue run                                  # Execute all queued tasks
ricet queue clear                                # Clear the queue
```

The task spooler handles batch execution of queued tasks, integrating with the agent system for routing and with the reproducibility module for logging.

---

## Website Builder

Generate and deploy a GitHub Pages documentation site:

```bash
ricet website init       # Scaffold MkDocs site
ricet website build      # Build static site
ricet website deploy     # Deploy to GitHub Pages
```

The website builder creates a Material-themed MkDocs site from your project's documentation, API reference, and README.

---

## Doability Assessment

Assess the feasibility of a task before starting:

The doability module analyzes a task description and returns:

- A feasibility score (0-100).
- Risk factors and potential blockers.
- Estimated complexity classification.
- Recommendations for approach.

This is used internally by the agent system to plan work and can be triggered via `ricet auto` routines.

---

## Prompt Suggestions

AI-powered next-step recommendations:

The prompt suggestions module analyzes current project state and suggests the next 3-5 research steps. Used internally during interactive sessions to guide the user when they are unsure what to work on next.

---

## RAG-Powered MCP Discovery

A searchable index of 1300+ Model Context Protocol servers:

```bash
ricet mcp-search "database migration"
```

The RAG MCP module (`core/rag_mcp.py`) provides:

- **Semantic search** over a comprehensive catalog of MCP servers.
- **Task-based suggestions** -- describe what you need and get ranked MCP recommendations.
- **On-demand installation** -- install suggested MCPs directly from search results.
- **JSON persistence** -- save and load custom indexes for project-specific MCP sets.

The full catalog of 1300+ servers is available at `defaults/raggable_mcps.md`.

---

## Social Media Publishing

Draft, validate, and publish research summaries to social media platforms:

```bash
ricet publish medium      # Publish to Medium
ricet publish linkedin    # Publish to LinkedIn
```

### Supported Platforms

| Platform | Character Limit | Features |
|----------|----------------|----------|
| Medium | ~100,000 | Title, markdown body, up to 5 tags |
| LinkedIn | 3,000 | Professional post with link |
| Twitter/X | 280 | Short-form summary |

### How It Works

The `core/social_media.py` module:

1. **Drafts** a post using Claude to summarize your research for the target audience.
2. **Validates** the draft against platform constraints (character limits, tag counts).
3. **Publishes** via the platform API (requires API tokens in `secrets/.env`).

Posts are automatically formatted for each platform's conventions and character limits.

### Required Credentials

Configure these in `secrets/.env` (prompted during `ricet init`):

- **Medium**: `MEDIUM_TOKEN` (free integration token)
- **LinkedIn**: `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_ACCESS_TOKEN`

---

## Slide Maker

ricet includes a built-in presentation generator that creates polished PPTX slide decks with AI-generated schematics.

### Usage

```bash
# Set up slide infrastructure in your project
ricet slides setup

# Create a deck (Claude agent writes the script)
ricet slides create \
  --title "My Research Results" \
  --audience "conference" \
  --duration 15 \
  --key-message "Our method achieves 2x speedup" \
  --schematics 5

# Build the .pptx (runs the script, generates images via Gemini)
ricet slides build
```

The slide maker uses a two-step workflow:

1. **`ricet slides create`** -- A Claude agent reads your codebase and writes a `make_slides.py` script using `slide_utils.py` helpers (7 slide templates, consistent color palette, professional layout).
2. **`ricet slides build`** -- Runs the script, which generates AI schematics via Google Gemini (Nano Banana Pro) and assembles the final `.pptx` file.

Requires `GOOGLE_API_KEY` for schematic generation.

---

## Code Indexing & Search

Index any codebase for semantic search, then query it:

```bash
ricet index-code reference/code/    # extract function/class signatures + docstrings
ricet search-code "ODE solver"      # semantic search over the index
```

`index-code` walks the directory, extracts function/class signatures and docstrings, and writes `state/code_index.md`. `search-code` reuses the existing RAG infrastructure (`core/rag.py`) to search over this index.

---

## Feature Request Pipeline

Log feature ideas and implement them in parallel worktrees:

```bash
ricet feature-request "add dark mode to dashboard"    # append to state/feature_requests.md
ricet implement-features                               # select which to build
```

`implement-features` displays pending features with numbers. After selection, each feature gets its own git worktree branch via `core/git_worktrees.py`, with one agent per worktree for conflict-free parallel development.

---

## Cascading Self-Update

When ricet itself is updated (via git pull or pip install), `_init_update()` automatically refreshes existing projects:

- `.claude/skills/*.md` -- refreshed if source is newer
- `knowledge/LEGISLATION.md` and `knowledge/PHILOSOPHY.md` -- refreshed from defaults
- User-edited files in `knowledge/` are never overwritten

This ensures all projects benefit from skill improvements without manual intervention.

---

## gstack Integration

Install [gstack](https://github.com/garrytan/gstack) startup workflow skills globally alongside ricet's research skills:

```bash
ricet gstack install    # install gstack skills to ~/.claude/skills/
ricet gstack status     # check installed skills
```

gstack skills (ship, review, retro, QA, plan-ceo-review, etc.) complement ricet's research skills. Both can be used in the same Claude Code session.

---

## Feature Verification Status

Live verification status of all ricet commands, tested against real projects.

### Phase 1: Project Setup

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 1 | `ricet init my-physics-sim` | :white_check_mark: | Interactive wizard, scaffolding, auto-install deps, MCP install |
| 2 | `ricet config` | :white_check_mark: | View generated settings.yml |
| 3 | `ricet config compute` | :white_check_mark: | GPU/cluster reconfiguration |
| 4 | `ricet status` | :white_check_mark: | Project status overview |
| 5 | `ricet dashboard` | :white_check_mark: | Rich TUI terminal dashboard |
| 6 | `ricet dashboard --live` | :white_check_mark: | Auto-refreshing TUI with budget monitoring |

### Phase 2: Knowledge & Goals

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 7 | `ricet fidelity` | :white_check_mark: | Alignment check vs GOAL.md |
| 8 | `ricet memory search "hamilton"` | :construction: | Vector/text search in encyclopedia |
| 9 | `ricet memory log-decision "Use RK4..."` | :white_check_mark: | Decision logging |
| 10 | `ricet memory stats` | :white_check_mark: | Encyclopedia size/stats |
| 11 | `ricet memory export` | :white_check_mark: | Export knowledge |

### Phase 3: Literature & Citations

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 12 | `ricet cite "Runge-Kutta methods..."` | :white_check_mark: | PubMed/arXiv search, BibTeX generation |
| 13 | `ricet browse "https://..."` | :white_check_mark: | URL text extraction |

### Phase 4: Development & Code

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 15 | `ricet start` | :white_check_mark: | Interactive Claude session |
| 16 | `ricet verify "RK4 has 4th-order..."` | :white_check_mark: | Fact-checking / falsification |
| 17 | `ricet debug "python src/solver.py"` | :construction: | Auto-debug loop |
| 18 | `ricet test-gen --file src/solver.py` | :white_check_mark: | Test generation via Claude |
| 19 | `ricet agents` | :white_check_mark: | Agent swarm status |

### Phase 5: Autonomous Execution

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 20 | `ricet queue submit -p "Implement..."` | :white_check_mark: | Task queuing |
| 21 | `ricet queue status` | :construction: | Queue status (with mobile inputs) |
| 22 | `ricet overnight --iterations 1` | :construction: | Autonomous mode with Docker sandbox |
| 23 | `ricet maintain` | :white_check_mark: | Daily maintenance pass |

### Phase 6: Paper Pipeline

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 24 | `ricet paper build` | :construction: | LaTeX compilation |
| 25 | `ricet paper check` | :construction: | Paper quality check |
| 26 | `ricet paper adapt-style` | :construction: | Style transfer |

### Phase 7: Reproducibility

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 27 | `ricet repro log --run-id exp1 --params '{...}'` | :construction: | Experiment logging |
| 28 | `ricet repro list` | :construction: | List tracked runs |
| 29 | `ricet repro hash --path data/` | :construction: | Dataset SHA-256 checksums |

### Phase 8: Mobile & Voice

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 30 | `ricet mobile tunnel` | :white_check_mark: | Phone access via cloudflared |

### Phase 9: MCP Ecosystem

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 33 | `ricet mcp-search "slack connecting mcp"` | :white_check_mark: | Search 1300+ MCP index |
| 34 | `ricet mcp-create physics-benchmark` | :construction: | Custom MCP creation |

### Phase 10: Multi-Project & Git

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 35 | `ricet projects list` | :white_check_mark: | List registered projects |
| 36 | `ricet worktree add experiment-euler` | :white_check_mark: | Parallel experiment branch |
| 37 | `ricet worktree list` | :white_check_mark: | List worktrees |
| 38 | `ricet link /path/to/other/repo` | :construction: | Cross-repo RAG |
| 39 | `ricet two-repo init` | :white_check_mark: | Cross-repository coordination |
| 40 | `ricet sync-learnings /path/to/other` | :construction: | Cross-project learning |

### Phase 11: Publishing & Infra

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 41 | `ricet website init && ricet website build` | :construction: | Project website + GitHub Pages |
| 42 | `ricet publish medium` | :construction: | Social media publishing |
| 43 | `ricet infra check` | :white_check_mark: | Docker/CI/CD status |
| 44 | `ricet docs` | :white_check_mark: | Auto-generate documentation |
| 45 | `ricet package init` | :white_check_mark: | Pip package setup |

### Phase 12: Quality & Audit

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 46 | `ricet audit` | :white_check_mark: | Half-baked feature scan (Claude-powered) |
| 47 | `ricet fresh-audit` | :white_check_mark: | Zero-context code review |
| 48 | `ricet review-claude-md` | :construction: | CLAUDE.md behavioral review |
| 49 | `ricet auto add-routine --name nightly` | :construction: | Scheduled autonomous routines |

### Phase 13: Presentations

| # | Command | Status | What it tests |
|---|---------|--------|---------------|
| 50 | `ricet slides setup` | :construction: | Slide infrastructure setup |
| 51 | `ricet slides create --title "..."` | :construction: | Claude agent writes slide script |
| 52 | `ricet slides build` | :construction: | Generate PPTX with AI schematics |

**Legend:** :white_check_mark: Verified working | :construction: Work in progress / needs fix
