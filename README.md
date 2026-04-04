<p align="center">
  <img src="docs/site/assets/ricet.png" alt="ricet logo" width="300">
</p>

<p align="center">
  <h1 align="center">ricet</h1>
  <p align="center">
    Scientific research automation powered by Claude Code.
  </p>
</p>

<p align="center">
  <a href="https://github.com/lucafusarbassini/research-automation/actions/workflows/ci.yml"><img src="https://github.com/lucafusarbassini/research-automation/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/research-automation/"><img src="https://img.shields.io/badge/pypi-v0.3.0-blue.svg" alt="PyPI v0.3.0"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+">
  <a href="https://github.com/lucafusarbassini/research-automation/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="https://lucafusarbassini.github.io/research-automation/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen.svg" alt="Docs"></a>
</p>

**[Full walkthrough demo](docs/demo.md)** -- realistic end-to-end workflow from init to publication.

---

ricet turns a research idea into reproducible code, validated results, and a publication-ready LaTeX paper -- all from your terminal. Eight research skills (slash commands) give Claude structured workflows for literature review, experiment auditing, paper drafting, adversarial validation, reproducibility testing, and more. A persistent knowledge system ensures insights compound across sessions instead of being lost.

## Prerequisites

| Requirement | Minimum version | Setup guide |
|-------------|----------------|-------------|
| **Python** | 3.11+ | [python.org/downloads](https://www.python.org/downloads/) |
| **Node.js** | 20+ | [nodejs.org](https://nodejs.org/) |
| **Docker** | 24+ | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **Git** | 2.40+ | [git-scm.com](https://git-scm.com/) |
| **Claude subscription** (Pro or Team) | -- | `claude auth login` (required and recommended). [API key](https://console.anthropic.com/) is an optional fallback for CI only |
| **GitHub SSH key** | -- | [docs.github.com/authentication](https://docs.github.com/en/authentication/connecting-to-github-with-ssh) |

> Docker is optional for local-only usage but strongly recommended for overnight autonomous runs.

## Quick Start

```bash
# 1. Install
git clone https://github.com/lucafusarbassini/research-automation
cd research-automation
pipx install ".[mobile]"

# 2. Create a new project (interactive onboarding)
ricet init my-experiment

# 3. Edit your research goal
cd my-experiment
$EDITOR knowledge/GOAL.md

# 4. Launch a persistent Claude session
ricet up
```

**The core workflow is `ricet init` → `ricet up`.** Everything else is skills.

`ricet up` launches a Docker-sandboxed Claude inside a GNU Screen with three input channels: CLI, Claude Remote Control (QR code), and a mobile dashboard via Tailscale. Sessions auto-resume on disconnect. `ricet down` tears everything down.

### GitHub PAT (per-project, for automated pushes)

```bash
# Generate at https://github.com/settings/tokens (Fine-grained, repo scope only)
# Store in the project's secrets/.env:
echo 'GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_...' >> secrets/.env
```

### Sandbox backup and export

The sandbox workspace is bind-mounted at `sandbox/workspace/` (visible in VS Code). Additionally:

- **Auto-backup**: `./sandbox/auto-backup.sh 15` syncs state files every 15 minutes
- **Extract work**: `./sandbox/extract-work.sh --apply` generates a git patch and applies it to the host repo
- **Watchdog**: auto-commits inside the container before timeout expires (default 24h)

## Features

### Research Skills (Slash Commands)

Instead of a rigid agent hierarchy, ricet deploys eight research skills as Claude Code slash commands. Each skill is a structured Markdown prompt that gives Claude a complete workflow for a specific research task:

| Skill | What it does |
|-------|-------------|
| `/lit-review` | Search PubMed/arXiv, synthesize findings, update Encyclopedia |
| `/experiment-review` | Six-dimension experiment audit (data, stats, code, methodology, leakage, sanity) |
| `/paper-draft` | Draft a paper section with lab style conventions and zero AI artifacts |
| `/falsify` | Adversarial validation -- try to break current results (Popper mode) |
| `/reproduce` | Re-run analysis with different seeds/splits, produce stability matrix |
| `/research-retro` | Session retrospective with tweetable summary, JSON snapshots for trends |
| `/slides` | Generate a polished .pptx presentation with AI-generated schematics |
| `/overnight` | Autonomous overnight session -- execute TODO list unattended |

Skills are deployed to `.claude/skills/` at `ricet init` and auto-refreshed when ricet is updated.

### Persistent Knowledge System

Every insight, decision, and behavioral correction is captured and persisted across sessions:

| File | Purpose | Updated by |
|------|---------|------------|
| `knowledge/RULES.md` | Behavioral rules from user corrections | meta_learn_hook (auto) |
| `knowledge/ENCYCLOPEDIA.md` | Domain knowledge, techniques, what works/fails | meta_learn_hook (auto) |
| `knowledge/DECISION_LOG.md` | Project decisions with rationale | meta_learn_hook (auto) |

The **meta-learn hook** runs on every user prompt via Haiku. It extracts rules, insights, and decisions from your interactions and appends them to the right file. Knowledge compounds across sessions instead of being lost.

```bash
ricet memory search "effect of learning rate on convergence"
```

### Lab/Stable Bipartition

Experimental work lives in `lab/`. When results pass validation, code is promoted to `stable/` with provenance tracking:

```bash
# Experimental work
python lab/analysis.py

# Promote after validation
ricet promote lab/analysis.py
# → copies to stable/analysis.py with provenance JSON (git hash, timestamp, metrics)
```

### Paper Pipeline

A complete LaTeX publication workflow ships with every project:

- `main.tex` template adapted from [Albert Dominguez, Gioele La Manno & Martin Weigert's manuscript template](https://github.com/weigertlab/manuscript_lipiddevatlas)
- BibTeX citation management with `ricet cite <query>` (search, format, append to .bib)
- Automatic figure reference checking
- Style analysis and transfer: `ricet paper adapt-style --reference <paper>`
- One-command compilation via **tectonic** (auto-installs LaTeX packages, no TeX distribution needed):

```bash
ricet paper build
```

### Remote Access & Background Sessions {#remote-access-via-mobile}

Run ricet unattended on a remote workstation and control it from your phone or another machine:

```bash
# Start a named screen session on the workstation
screen -S ricet-session
ricet overnight --iterations 20
# Detach: Ctrl+A D

# Reconnect from anywhere
ssh workstation "screen -r ricet-session"
```

Mobile access uses Tailscale (default) or Cloudflare Tunnel for secure access from any device.

### Overnight Autonomous Mode

Queue a task list and let the system work unattended:

```bash
ricet overnight --iterations 30
```

The system executes your TODO list iteratively, checkpoints progress after every subtask, and stops when the completion signal is detected or the iteration cap is reached.

### Adopt Existing Repos

Transform any existing GitHub repository into a ricet project:

```bash
ricet adopt https://github.com/user/repo              # fork + clone + scaffold
ricet adopt https://github.com/user/repo --no-fork    # clone only
ricet adopt /path/to/local/repo                        # scaffold in place
ricet adopt https://github.com/user/repo --branch alice  # use named user branch
```

The command forks the repo (keeping the original intact), overlays the ricet workspace structure, pre-fills `GOAL.md` from the README, registers the project, and creates a personal branch (auto-derived from your git email if `--branch` is omitted).

### Collaborative Research (Multi-User Workflow)

Multiple researchers can collaborate on the same repo, each on their own branch:

```bash
# Each collaborator adopts the repo -- gets their own branch automatically
ricet adopt https://github.com/lab/project
# → creates branch user-alice, user-bob, etc. from git email

# Daily workflow: sync your branch with the latest
ricet sync

# Lead researcher: merge all user branches into main every morning
ricet morning-sync
```

`morning-sync` pulls every `user-*` branch, merges it into `main` with `--no-ff`, and pushes. Conflicts are reported and skipped so nothing is lost. Merge conflicts on append-only files are minimized via `.gitattributes merge=union`.

### Code Indexing & Search

Index any codebase for semantic search, then query it:

```bash
ricet index-code reference/code/    # extract function/class signatures
ricet search-code "ODE solver"      # semantic search over the index
```

### Feature Request Pipeline

Log feature ideas and implement them in parallel worktrees:

```bash
ricet feature-request "add dark mode to dashboard"
ricet implement-features    # select which to build, each gets a worktree
```

### Cross-Repository RAG

Link external repositories so Claude can search across all your code while only editing the current project:

```bash
ricet link /path/to/other-repo --name my-lib   # index for search
ricet reindex                                    # re-index all linked repos
ricet unlink my-lib                              # remove
```

### context-hub: Versioned API Docs for Agents {#context-hub}

ricet integrates [context-hub](https://github.com/andrewyng/context-hub) (`chub`) -- a curated, versioned API documentation registry designed for coding agents.

```bash
ricet chub search openai            # discover available doc sets
ricet chub get openai               # fetch Python API reference
```

### gstack Integration

Install [gstack](https://github.com/garrytan/gstack) startup workflow skills globally alongside ricet's research skills:

```bash
ricet gstack install    # install gstack skills to ~/.claude/skills/
ricet gstack status     # check installed skills
```

### Voice Prompting

Transcribe audio instructions in 30+ languages and execute them:

```bash
ricet voice
```

### Auto-Debug Loop

When a command fails, the auto-debug module captures the error, analyses the traceback, proposes a fix, applies it, and retries -- all without manual intervention.

### Cascading Self-Update

When ricet is updated, `_init_update()` automatically refreshes skills and defaults in all existing projects without overwriting user-edited files.

### Sandbox Infrastructure

Run autonomous sessions inside a fully isolated Docker sandbox:

```bash
ricet sandbox setup     # Build sandbox image with full toolchain
ricet sandbox start     # Launch sandbox container
ricet sandbox extract   # Copy work products to host
```

### Slide Deck Generation

Generate presentation-ready `.pptx` decks with AI-generated schematics:

```bash
ricet slides create     # Claude designs narrative + writes make_slides.py
ricet slides build      # Run script to generate schematics + build .pptx
```

### Additional Features

- **Auto-Commit & Push** -- Every state-modifying CLI command automatically commits and pushes
- **Global Credential Store** -- `~/.ricet/credentials.env` stores API keys once across all projects
- **Interactive Dashboard** -- `ricet dashboard` Rich TUI with live progress and resource monitoring
- **Figure Gallery** -- Scans, catalogs, and organizes experiment figures by run ID
- **Security** -- Credential isolation, Docker containerization, full audit logging
- **MCP Discovery** -- `ricet mcp-search` searches 1300+ MCP servers and installs on demand
- **claude-flow (ruflo)** -- Optional multi-agent MCP server for complex coordination tasks

## Installation

### From PyPI (recommended)

ricet uses [uv](https://github.com/astral-sh/uv) for fast, reproducible package management.

```bash
# Install uv first (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Then install ricet
uv pip install ricet
```

uv is auto-installed during `ricet init` so you don't have to do this manually on new machines.

### With ML extras

```bash
uv pip install "ricet[ml]"     # numpy, pandas, scipy, scikit-learn, matplotlib
uv pip install "ricet[all]"    # + chromadb, sentence-transformers, torch, jupyter
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
uv pip install -e ".[dev]"
```

### What `ricet init` auto-installs

Running `ricet init` in a new project bootstraps the full toolchain with no manual steps:

| Tool | Purpose |
|------|---------|
| **uv** | Fast Python package manager (replaces pip) |
| **tectonic** | Single-binary LaTeX engine (replaces a full TeX distribution) |
| **biber 2.17** | BibLaTeX backend, version-matched to tectonic's bundled biblatex |
| **screen** | Background sessions and [remote phone access](#remote-access-via-mobile) |
| **Tailscale** | Secure tunnel for mobile access (default), Cloudflare Tunnel as fallback |
| **chub** | [context-hub](#context-hub) -- versioned API docs for agents |

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

A Claude subscription (Pro or Team) is required and recommended. Authenticate
with browser login -- no API key needed:

```bash
claude auth login
```

For CI/headless environments only, you may optionally store an API key as a
fallback in a `.env` file at the project root (auto-loaded, never committed).

## CLI Commands

| Command | Description |
|---------|-------------|
| `ricet init <name>` | Scaffold a new research project with interactive onboarding |
| `ricet start` | Launch an interactive Claude Code session |
| `ricet overnight` | Run autonomous overnight mode with configurable iterations |
| `ricet status` | Show current TODO, progress, and resource metrics |
| `ricet config [section]` | View or update project settings |
| `ricet adopt <source>` | Adopt an existing repo as a ricet project (fork + scaffold) |
| `ricet morning-sync` | Merge all user-* branches into main |
| `ricet sync` | Pull, rebase, push the current branch |
| `ricet paper <action>` | Paper pipeline: `build`, `check`, `update`, `modernize` |
| `ricet cite <query>` | Search papers and append BibTeX to references.bib |
| `ricet memory <query>` | Semantic search across project knowledge |
| `ricet promote <path>` | Promote lab/ file to stable/ after validation |
| `ricet index-code <path>` | Index a codebase for semantic search |
| `ricet search-code <query>` | Search indexed code |
| `ricet feature-request <desc>` | Log a feature request |
| `ricet implement-features` | Build selected features in parallel worktrees |
| `ricet slides <action>` | Slide deck generation: `setup`, `create`, `build` |
| `ricet mobile` | Manage mobile companion server |
| `ricet voice` | Record and execute a voice prompt |
| `ricet gstack <action>` | Manage gstack startup workflow skills |
| `ricet sandbox <action>` | Sandbox: `setup`, `start`, `stop`, `extract`, `backup`, `destroy` |
| `ricet dashboard` | Launch the Rich TUI dashboard |
| `ricet link <path>` | Link a repository for cross-repo RAG search |
| `ricet mcp-search <need>` | Search 1300+ MCP servers |
| `ricet enable-ruflo` | Enable claude-flow MCP server |
| `ricet disable-ruflo` | Disable claude-flow MCP server |
| `ricet docs` | Auto-update project documentation |
| `ricet test-gen` | Auto-generate tests for new/changed files |
| `ricet package <action>` | Package management: `init`, `build`, `publish` |
| `ricet zenodo <action>` | Publish to Zenodo with DOI |
| `ricet maintain` | Run daily maintenance pass |
| `ricet fidelity` | Check GOAL.md alignment and flag drift |
| `ricet verify` | Run verification on recent outputs |
| `ricet browse <url>` | Fetch and extract text from a URL |
| `ricet chub <action>` | Query context-hub for versioned API docs |
| `ricet discover <topic>` | Broad literature discovery across databases |
| `ricet two-repo <action>` | Manage experiments/ vs clean/ dual-repo |
| `ricet worktree <action>` | Manage git worktrees for parallel experiments |
| `ricet queue <action>` | Queue prompts for batch execution |
| `ricet infra <action>` | Infrastructure checks, Docker, CI/CD |
| `ricet runbook <file>` | Parse and execute markdown runbooks |

Run `ricet <command> --help` for full option details.

## Architecture

```
research-automation/
|
|-- cli/                        # Typer CLI entry points
|   |-- main.py                 #   ricet command definitions (55+ commands)
|   |-- dashboard.py            #   Rich TUI dashboard
|   +-- gallery.py              #   Figure gallery viewer
|
|-- core/                       # Python library modules (50+)
|   |-- adopt.py                #   Transform existing repos into ricet projects
|   |-- agents.py               #   Task DAG execution, output ring buffers
|   |-- auto_commit.py          #   Auto-commit & push after operations
|   |-- auto_debug.py           #   Auto-debug loop
|   |-- autonomous.py           #   Overnight autonomous runner
|   |-- claude_flow.py          #   claude-flow bridge (swarm, memory, metrics)
|   |-- code_index.py           #   Code indexing for semantic search
|   |-- collaboration.py        #   Multi-user sync, merge, user identity
|   |-- knowledge.py            #   Encyclopedia & RAG search
|   |-- notifications.py        #   Email / Slack notifications
|   |-- onboarding.py           #   Project setup wizard (tectonic, biber, uv, chub)
|   |-- paper.py                #   LaTeX compilation & citation management
|   |-- promotion.py            #   Lab → stable promotion with provenance
|   |-- slack_delivery.py       #   Slack file uploads via v2 API
|   |-- slides.py               #   Slide deck generation
|   |-- style_transfer.py       #   Academic writing style analysis
|   |-- updater.py              #   Cascading self-update for existing projects
|   +-- voice.py                #   Voice transcription (30+ languages)
|
|-- templates/                  # Scaffolded into every new project
|   |-- .claude/                #   CLAUDE.md project instructions
|   |   +-- skills/             #   8 research skills (slash commands)
|   |-- knowledge/              #   GOAL.md, ENCYCLOPEDIA.md, RULES.md, etc.
|   |-- paper/                  #   LaTeX template, references.bib
|   |-- config/                 #   settings.yml, mcp configs
|   |-- lab/                    #   Experimental scripts (chaotic)
|   +-- stable/                 #   Validated code (promoted from lab/)
|
|-- defaults/                   # LEGISLATION.md, PHILOSOPHY.md, MCP catalog
|-- scripts/                    # meta_learn_hook.py, shell helpers
|-- docs/                       # GitHub Pages site, tutorials
+-- tests/                      # Pytest suite (50+ test modules)
```

### How it works

```
You --> ricet start --> Claude Code session (with skills + knowledge loaded)
                              |                    |
                         /lit-review          knowledge/
                         /falsify             ENCYCLOPEDIA.md
                         /paper-draft         RULES.md
                         /overnight           DECISION_LOG.md
                              |                    |
                         meta_learn_hook      Auto-extracts rules,
                         (every prompt)       insights, decisions
```

1. `ricet init` scaffolds a project from templates, runs interactive onboarding, installs toolchain (uv, tectonic, biber), and registers the meta-learn hook.
2. `ricet start` launches a Claude Code session with project instructions, knowledge files, and 8 research skills loaded.
3. You invoke skills (`/lit-review`, `/falsify`, `/paper-draft`, etc.) for structured research workflows, or just work with Claude directly.
4. The meta-learn hook automatically captures behavioral rules, domain insights, and decisions from every interaction.
5. Knowledge compounds across sessions via ENCYCLOPEDIA.md, RULES.md, and DECISION_LOG.md.
6. `ricet overnight` runs the TODO list autonomously with auto-debug and checkpointing.

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

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) by Anthropic -- The core AI coding agent that powers all execution in this system.
- [gstack](https://github.com/garrytan/gstack) by Garry Tan -- Skill-based workflow patterns that influenced the design of ricet's research slash commands. The "Important Rules", "Priority Hierarchy", and persistence patterns in ricet's skills are directly inspired by gstack's approach.
- [claude-flow](https://github.com/ruvnet/claude-flow) by ruvnet -- Multi-agent orchestration patterns, HNSW vector memory, and swarm coordination. The project's agent bridge (`core/claude_flow.py`) integrates directly with claude-flow when available.
- [MCP Servers](https://github.com/modelcontextprotocol/servers) by the Model Context Protocol team -- Official MCP server implementations (filesystem, git, memory, fetch, GitHub, Puppeteer, and others) used as the foundation for MCP integrations.
- [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) by punkpeye -- Comprehensive catalog of MCP servers that guided the selection and tiering of integrations.
- [arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server) by blazickjp -- ArXiv paper search MCP server used for literature discovery.
- [context-hub](https://github.com/andrewyng/context-hub) by Andrew Ng -- Versioned API documentation registry for coding agents, integrated as `ricet chub`.
- [manuscript_lipiddevatlas](https://github.com/weigertlab/manuscript_lipiddevatlas) by Albert Dominguez, Gioele La Manno & Martin Weigert -- LaTeX manuscript template adapted for ricet's paper pipeline.
- [Claude Code Tutorial](https://lamanno-epfl.github.io/tutorial_claude_code/) by the La Manno Lab (EPFL) -- Research workflow patterns and paper-writing guidance that informed the project's academic automation design.
- [claude-code-tips](https://github.com/ykdojo/claude-code-tips) by ykdojo -- Practical Claude Code best practices that shaped instruction protocols and progressive prompting strategy.
## License

[MIT](LICENSE)
