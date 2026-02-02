<p align="center">
  <h1 align="center">ricet</h1>
  <p align="center">
    Scientific research automation powered by Claude Code.
  </p>
</p>

<p align="center">
  <a href="https://github.com/lucafusarbassini/research-automation/actions/workflows/ci.yml"><img src="https://github.com/lucafusarbassini/research-automation/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/research-automation/"><img src="https://img.shields.io/pypi/v/research-automation.svg" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+">
  <a href="https://github.com/lucafusarbassini/research-automation/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="https://lucafusarbassini.github.io/research-automation/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen.svg" alt="Docs"></a>
</p>

**[Full walkthrough demo](docs/demo.md)** -- realistic end-to-end workflow from init to publication.

---

ricet turns a research idea into reproducible code, validated results, and a publication-ready LaTeX paper -- all from your terminal. A master agent breaks your goal into subtasks and dispatches them to specialized sub-agents (researcher, coder, reviewer, falsifier, writer, cleaner) that execute inside a Docker-isolated environment with 70+ MCP integrations auto-discovered on demand.

## Prerequisites

| Requirement | Minimum version | Setup guide |
|-------------|----------------|-------------|
| **Python** | 3.11+ | [python.org/downloads](https://www.python.org/downloads/) |
| **Node.js** | 20+ | [nodejs.org](https://nodejs.org/) |
| **Docker** | 24+ | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **Git** | 2.40+ | [git-scm.com](https://git-scm.com/) |
| **Claude authentication** | -- | `claude auth login` (preferred) or [API key](https://console.anthropic.com/) for CI |
| **GitHub SSH key** | -- | [docs.github.com/authentication](https://docs.github.com/en/authentication/connecting-to-github-with-ssh) |

> Docker is optional for local-only usage but strongly recommended for overnight autonomous runs.

## Quick Start

```bash
# 1. Install
pip install ricet

# 2. Create a new project (interactive onboarding)
ricet init my-experiment

# 3. Launch an interactive research session
cd my-experiment
ricet start
```

That's it. The onboarding wizard will ask for your research goal, compute preferences, and notification settings, then scaffold a fully configured project.

## Features

### Multi-Agent Orchestration

A hierarchical swarm of specialized Claude agents collaborates on your research. The **master agent** parses every request and routes it to the right sub-agent:

| Agent | Role |
|-------|------|
| **Researcher** | Literature search, paper retrieval, background synthesis |
| **Coder** | Implementation, experiments, data processing |
| **Reviewer** | Code review, improvement suggestions |
| **Falsifier** | Attacks results, finds flaws, enforces Popperian falsification |
| **Writer** | Paper sections, documentation, reports |
| **Cleaner** | Refactoring, optimization, code hygiene |

Token budgets are automatically distributed across agents and monitored throughout the session.

### Vector Memory & Knowledge Accumulation

Every insight, decision, and finding is persisted to a growing **Encyclopedia** backed by HNSW vector search (via claude-flow). Agents query memory semantically so knowledge compounds across sessions instead of being lost.

```bash
ricet memory "effect of learning rate on convergence"
```

### Paper Pipeline

A complete LaTeX publication workflow ships with every project:

- Structured `main.tex` template with standard sections
- BibTeX citation management with `ricet cite <query>` (search → format → append to .bib)
- Automatic figure reference checking
- Style analysis and transfer: `ricet paper adapt-style --reference <paper>`
- One-command compilation: `ricet paper build`

For exhaustive cross-discipline paper discovery, we recommend [PaperBoat](https://paperboatch.com/) — an AI-powered service that scans thousands of journals daily and delivers personalized paper matches. Useful as a background SOTA knowledge source that updates daily across all disciplines.

### Overnight Autonomous Mode

Queue a task list and let the system work unattended:

```bash
ricet overnight --iterations 30
```

The system executes your TODO list iteratively, checkpoints progress after every subtask, and stops when the completion signal is detected or the iteration cap is reached. Supports both claude-flow swarm orchestration and a raw-loop fallback.

### Auto-Debug Loop

When a command fails, the auto-debug module captures the error, analyses the traceback, proposes a fix, applies it, and retries -- all without manual intervention. Every fix and its outcome are logged for reproducibility.

### 3-Tier Model Routing

Requests are automatically routed to the most cost-effective model:

| Tier | Model | Used for |
|------|-------|----------|
| Booster | Claude Haiku | Formatting, lookups, classification |
| Workhorse | Claude Sonnet | Code writing, analysis, general tasks |
| Oracle | Claude Opus | Architecture, validation, paper writing |

### Browser Automation

Headless browser sessions for web scraping, screenshot capture, and PDF generation. Delegates to a Puppeteer MCP server when available; falls back to lightweight HTTP tools otherwise.

### Auto-Commit & Push

Every state-modifying CLI command (`init`, `start`, `config`, `overnight`, `paper`, `verify`, `debug`, etc.) automatically commits and pushes changes. Controlled by environment variables:

```bash
export RICET_AUTO_COMMIT=true   # default: true
export AUTO_PUSH=true           # default: true
```

### Claude-Powered Routing

Seven core modules (agents, model router, auto-debug, doability, prompt suggestions, verification, onboarding) now try the Claude CLI for intelligent decisions before falling back to keyword heuristics. This improves task routing accuracy, fix suggestions, and complexity classification. Disable in tests or CI with `RICET_NO_CLAUDE=true`.

### Adopt Existing Repos

Transform any existing GitHub repository into a ricet project:

```bash
ricet adopt https://github.com/user/repo          # fork + clone + scaffold
ricet adopt https://github.com/user/repo --no-fork # clone only
ricet adopt /path/to/local/repo                    # scaffold in place
```

The command forks the repo (keeping the original intact), overlays the ricet workspace structure, pre-fills `GOAL.md` from the README, and registers the project.

### Collaborative Research

Multiple researchers can use ricet on the same repository. On `ricet start`, the system pulls the latest changes before beginning. Encyclopedia entries include user identity for attribution. Merge conflicts are minimized via `.gitattributes merge=union` on append-only files.

### Cross-Repository RAG

Link external repositories so agents can search across all your code while only editing the current project:

```bash
ricet link /path/to/other-repo --name my-lib   # index for search
ricet link /path/to/data-pipeline               # auto-named from path
ricet reindex                                    # re-index all linked repos
ricet unlink my-lib                              # remove
```

Linked repos are indexed into HNSW vector memory (with JSON fallback) and searched automatically during `ricet memory` queries. Permission boundaries ensure linked repos are read-only.

### Cross-Repository Coordination

Link multiple repositories, run coordinated commits, and enforce permission boundaries across projects -- useful for mono-repo experiments that span data pipelines and model code.

### Voice Prompting

Transcribe audio instructions, detect language, and structure them into actionable prompts that feed directly into the agent pipeline.

### Interactive Dashboard

A Rich-powered TUI that shows live progress, TODO status, session history, and resource utilization at a glance.

### Figure Gallery

Automatically scans, catalogs, and organizes experiment figures by run ID and format for quick review and paper inclusion.

### Security & Reproducibility

- Credential isolation via `.env` files (never committed)
- Docker containerization for safe, reproducible execution
- Full audit logging in `state/audit.log`
- Git checkpoint after every subtask

## Installation

### From PyPI (recommended)

```bash
pip install ricet
```

### With ML extras

```bash
pip install "ricet[ml]"     # numpy, pandas, scipy, scikit-learn, matplotlib
pip install "ricet[all]"    # + chromadb, sentence-transformers, torch, jupyter
```

### Docker

```bash
docker build -t ricet docker/
docker run -it -v $(pwd):/workspace ricet
```

### From source

```bash
git clone https://github.com/lucafusarbassini/research-automation.git
cd research-automation
pip install -e ".[dev]"
```

## Configuration

After running `ricet init`, your project contains `config/settings.yml`:

```yaml
project:
  name: "my-experiment"

compute:
  type: "local-gpu"       # local-cpu | local-gpu | cloud | cluster
  gpu: "RTX 4090"

notifications:
  enabled: true
  method: "slack"          # email | slack | none

preferences:
  auto_commit: true
  checkpoint_interval: 30  # minutes
  max_overnight_iterations: 20
```

Reconfigure any section interactively:

```bash
ricet config notifications
ricet config compute
```

### Authentication

The recommended way to authenticate with Claude is browser login (no API key needed):

```bash
claude auth login
```

For CI/headless environments, store an API key in a `.env` file at the project root (auto-loaded, never committed):

```
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `ricet init <name>` | Scaffold a new research project with interactive onboarding |
| `ricet start` | Launch an interactive Claude Code session |
| `ricet overnight` | Run autonomous overnight mode with configurable iterations |
| `ricet status` | Show current TODO, progress, and resource metrics |
| `ricet config [section]` | View or update project settings |
| `ricet paper <action>` | Paper pipeline: `build`, `check`, `update`, `modernize` |
| `ricet memory <query>` | Semantic search across vector memory |
| `ricet agents` | Show active swarm agent status |
| `ricet metrics` | Display token usage, cost, and system resource stats |
| `ricet adopt <source>` | Adopt an existing repo as a ricet project (fork + scaffold) |
| `ricet link <path>` | Link a repository for cross-repo RAG search |
| `ricet unlink <name>` | Remove a linked repository |
| `ricet reindex` | Re-index all linked repositories |
| `ricet docs` | Auto-update project docs from source code |
| `ricet mcp-search <need>` | Search 1300+ MCP servers and install on demand |
| `ricet two-repo <action>` | Manage experiments/ vs clean/ dual-repo structure |
| `ricet browse <url>` | Fetch and extract text from a URL (literature review) |
| `ricet infra <action>` | Infrastructure checks, Docker builds, CI/CD, secrets |
| `ricet runbook <file>` | Parse and execute code blocks from a markdown runbook |
| `ricet paper adapt-style` | Rewrite your paper in a reference paper's style |
| `ricet cite <query>` | Search papers and append BibTeX to references.bib |
| `ricet discover <topic>` | Broad literature discovery across databases |
| `ricet test-gen` | Auto-generate tests for new/changed source files |
| `ricet package <action>` | Package management: `init`, `build`, `publish` |
| `ricet maintain` | Run daily maintenance pass (tests, docs, fidelity, verify) |
| `ricet fidelity` | Check GOAL.md alignment and flag drift |
| `ricet sync-learnings` | Share learnings across ricet projects |
| `ricet auto <action>` | Manage autonomous routines and topic monitoring |
| `ricet repro <action>` | Reproducibility: `log`, `list`, `show`, `hash` |
| `ricet verify` | Run verification on recent outputs |
| `ricet list-sessions` | List all past and active sessions |
| `ricet --version` | Print version |

Run `ricet <command> --help` for full option details.

## Architecture

```
research-automation/
|
|-- cli/                        # Typer CLI entry points
|   |-- main.py                 #   ricet command definitions
|   |-- dashboard.py            #   Rich TUI dashboard
|   +-- gallery.py              #   Figure gallery viewer
|
|-- core/                       # Python library modules
|   |-- agents.py               #   Agent definitions & routing
|   |-- auto_debug.py           #   Auto-debug loop
|   |-- autonomous.py           #   Overnight autonomous runner
|   |-- browser.py              #   Headless browser integration
|   |-- auto_commit.py          #   Auto-commit & push after operations
|   |-- claude_flow.py          #   claude-flow bridge (swarm, memory, metrics)
|   |-- claude_helper.py        #   Shared Claude CLI helper for intelligent fallbacks
|   |-- collaboration.py        #   Multi-user sync, merge, user identity
|   |-- cross_repo.py           #   Multi-repo coordination & RAG indexing
|   |-- adopt.py                #   Transform existing repos into ricet projects
|   |-- knowledge.py            #   Encyclopedia & keyword search
|   |-- mcps.py                 #   MCP discovery & management (70+ integrations)
|   |-- meta_rules.py           #   Automatic meta-rule capture
|   |-- model_router.py         #   3-tier model routing
|   |-- notifications.py        #   Email / Slack notifications
|   |-- onboarding.py           #   Project setup wizard
|   |-- paper.py                #   LaTeX compilation & citation management
|   |-- reproducibility.py      #   Reproducibility tracking
|   |-- resources.py            #   System resource monitoring
|   |-- security.py             #   Credential & permission guards
|   |-- session.py              #   Session lifecycle management
|   |-- style_transfer.py       #   Academic writing style analysis
|   |-- tokens.py               #   Token budget tracking
|   |-- verification.py         #   Result verification
|   +-- voice.py                #   Voice transcription & prompt structuring
|
|-- templates/                  # Scaffolded into every new project
|   |-- .claude/                #   Agent definitions, hooks, skills
|   |-- paper/                  #   LaTeX template, Makefile, references.bib
|   |-- knowledge/              #   GOAL.md, ENCYCLOPEDIA.md, CONSTRAINTS.md
|   |-- config/                 #   settings.yml, mcp-nucleus.json, claude-flow.json
|   +-- .github/workflows/      #   CI: tests, linting, paper build
|
|-- docker/                     # Dockerfile & docker-compose
|-- scripts/                    # Shell helpers (setup, overnight, interactive)
|-- defaults/                   # Philosophy, code style, prompt library, MCP catalog
+-- tests/                      # Pytest suite (40+ test modules)
```

### How it works

```
You --> ricet start --> Master Agent --> Sub-agents (researcher, coder, ...)
                              |                    |
                         claude-flow          Vector Memory
                         (swarm, MCP)         (HNSW index)
                              |                    |
                         Docker sandbox     knowledge/ENCYCLOPEDIA.md
```

1. `ricet init` scaffolds a project from templates and runs interactive onboarding.
2. `ricet start` launches a Claude Code session governed by the master agent.
3. The master agent reads your goal, plans subtasks, and dispatches them to specialized sub-agents.
4. Each sub-agent executes inside the project environment, commits results, and updates shared memory.
5. The falsifier agent validates outputs before anything is marked complete.
6. `ricet overnight` repeats this cycle unattended until the task list is done.

## Disclaimer

This is an experimental hobby project, not production-hardened software. With the power of autonomous AI agents comes real responsibility: the more freedom you grant Claude (especially in overnight mode), the higher the risk of unintended changes, runaway costs, or unreviewed code making it into your repo. Measures like Docker isolation, permission guards, and auto-commit checkpoints are in place, but they do not eliminate risk. Always review agent outputs before publishing or deploying, set sensible iteration limits, and keep API spend alerts enabled. Use at your own discretion.

## Contributing

Contributions are welcome. To get started:

```bash
git clone https://github.com/lucafusarbassini/research-automation.git
cd research-automation
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Please ensure all tests pass and code follows the project style (Black, isort, mypy) before submitting a pull request.

See the [Contributing Guide](CONTRIBUTING.md) for full details.

## Acknowledgments

This project was inspired by and builds upon the work of several open-source projects and communities:

- [claude-flow](https://github.com/ruvnet/claude-flow) by ruvnet -- Multi-agent orchestration patterns, HNSW vector memory, and swarm coordination. The project's agent bridge (`core/claude_flow.py`) integrates directly with claude-flow when available.
- [MCP Servers](https://github.com/modelcontextprotocol/servers) by the Model Context Protocol team -- Official MCP server implementations (filesystem, git, memory, fetch, GitHub, Puppeteer, and others) used as the foundation for the 70+ MCP integrations configured in this project.
- [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) by punkpeye -- Comprehensive catalog of MCP servers that guided the selection and tiering of integrations in the MCP nucleus configuration.
- [arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server) by blazickjp -- ArXiv paper search MCP server used for literature discovery in the researcher agent pipeline.
- [Claude Code Tutorial](https://lamanno-epfl.github.io/tutorial_claude_code/) by the La Manno Lab (EPFL) -- Research workflow patterns and paper-writing guidance that informed the project's academic automation design.
- [claude-code-tips](https://github.com/ykdojo/claude-code-tips) by ykdojo -- Practical Claude Code best practices that shaped the agent instruction protocols and progressive prompting strategy.
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) by Anthropic -- The core AI coding agent that powers all sub-agent execution in this system.

## License

[MIT](LICENSE)
