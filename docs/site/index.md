# ricet

**Automate scientific research using Claude Code with multi-agent orchestration, overnight autonomous execution, and comprehensive tooling.**

Created by **Luca Fusar Bassini** -- turning the scientific method into software.

---

ricet is a CLI tool and framework that manages the full lifecycle of scientific research projects. It pairs Claude Code with a structured agent system, persistent knowledge, reproducibility enforcement, and a complete paper pipeline -- so you can focus on the science while automation handles the scaffolding.

---

## Why ricet?

Running a research project involves dozens of repetitive tasks: environment setup, literature searches, experiment tracking, figure generation, paper writing, and more. ricet provides a single `ricet` command that orchestrates all of these through specialized AI agents operating inside a safe, containerized environment.

| Problem | Solution |
|---------|----------|
| Ad-hoc experiment tracking | Reproducibility engine with run logs, artifact registry, and dataset hashing |
| Scattered knowledge | Persistent encyclopedia that grows automatically with every task |
| Tedious boilerplate | Project templates with agents, hooks, LaTeX, and CI/CD out of the box |
| Unsafe autonomous runs | Docker isolation with four-tier permission model |
| Manual paper formatting | Integrated LaTeX pipeline with colorblind-safe figures and citation management |

---

## Quick Start

```bash
# Install Claude Code (requires Node.js 20+)
npm install -g @anthropic-ai/claude-code

# Clone the repository
git clone https://github.com/lucafusarbassini/research-automation
cd research-automation

# Install the CLI
pip install -e .

# Create your first project
ricet init my-project

# Start an interactive session
cd my-project
ricet start

# Or run overnight
ricet overnight --iterations 20
```

See the full [Quickstart Tutorial](quickstart.md) for a step-by-step walkthrough.

---

## Feature Highlights

- **Multi-Agent Orchestration** -- Master agent routes tasks to Researcher, Coder, Reviewer, Falsifier, Writer, and Cleaner sub-agents, each with dedicated budgets and system prompts.
- **70+ MCP Integrations** -- Automatically discovered and loaded based on task type, organized in eight tiers from essential tools to cloud infrastructure.
- **Overnight Mode** -- Autonomous execution loop with auto-debug, resource monitoring, and recovery. Run `ricet overnight` and check results in the morning.
- **Knowledge Accumulation** -- A project encyclopedia that records learnings, decisions, successful approaches, and failed attempts. Supports HNSW vector search when claude-flow is available.
- **Paper Pipeline** -- LaTeX template, publication-quality figure generation with matplotlib rcParams, BibTeX citation management, and one-command compilation.
- **Reproducibility** -- Every experiment run is logged with parameters, metrics, git hash, and SHA-256 artifact checksums.
- **Docker Isolation** -- Safe containerized execution with four permission levels (Safe, Moderate, Elevated, Dangerous).
- **3-Tier Model Routing** -- Automatic model selection (Haiku/Sonnet/Opus) based on task complexity, with budget-aware fallback.
- **Progressive Instructions** -- Five-phase protocol: Orient, Explore, Plan, Execute, Validate.
- **Cross-Repository Coordination** -- Link multiple repos, coordinate commits, and enforce permission boundaries.
- **Adopt Existing Repos** -- Transform any GitHub repo into a ricet project with `ricet adopt`, including fork, scaffold, and GOAL pre-fill from README.
- **Cross-Repo RAG** -- Link external repositories with `ricet link` so agents can search across all your code while only editing the current project.
- **Auto-Commit & Push** -- Every state-modifying command automatically commits and pushes, controlled by environment variables.
- **Collaborative Research** -- Multiple researchers on the same repo with auto-sync, user attribution, and merge-friendly append-only files.
- **Claude-Powered Intelligence** -- Seven core modules use Claude CLI for intelligent routing, debugging, and suggestions with keyword fallback.
- **Literature Search** -- `ricet cite` and `ricet discover` search Semantic Scholar and arXiv, format BibTeX, and append to your bibliography.
- **Style Transfer** -- `ricet paper adapt-style` rewrites your paper to match a reference paper's writing style with plagiarism checks.
- **Auto Test Generation** -- `ricet test-gen` scans for uncovered source files and generates pytest stubs using Claude.
- **Package Management** -- `ricet package init/build/publish` turns research code into reusable Python packages.
- **Daily Maintenance** -- `ricet maintain` runs test generation, docs update, fidelity check, and verification in one pass. Auto-runs after overnight sessions.
- **Goal Fidelity** -- `ricet fidelity` scores alignment between the codebase and GOAL.md, flagging drift areas.
- **Cross-Project Learning** -- `ricet sync-learnings` shares encyclopedia entries across ricet projects.
- **MCP Discovery** -- `ricet mcp-search` searches 1300+ MCP servers and installs on demand.
- **Dual-Repo Structure** -- `ricet two-repo` manages experiments/ vs clean/ separation with promotion gates.
- **URL Browsing** -- `ricet browse` fetches and extracts text from URLs for literature review.
- **Infrastructure** -- `ricet infra` handles Docker builds, CI/CD, secrets, and dependency checks.
- **Runbook Execution** -- `ricet runbook` parses and executes code blocks from markdown runbooks.
- **Docker Overnight** -- `ricet overnight --docker` runs autonomous sessions inside a Docker sandbox.
- **Resource-Aware Overnight** -- Monitors CPU/RAM/disk between iterations, auto-pauses on low resources.
- **Falsifier Auto-Trigger** -- Falsifier agent validates results after every overnight iteration automatically.
- **Voice Prompting** -- `ricet voice` transcribes audio instructions and structures them into actionable research prompts.
- **Mobile PWA** -- `ricet mobile` sets up Progressive Web App access for remote monitoring.
- **Interactive Dashboard** -- `ricet dashboard` provides a Rich TUI with live agent status, budget, and resource utilization.
- **Figure Gallery** -- `ricet gallery` scans and catalogs experiment figures by run ID for quick review and paper inclusion.
- **Git Worktree Management** -- `ricet worktree` manages parallel branches for concurrent experiments.
- **Task Queue** -- `ricet queue` manages and spools background tasks for batch execution.
- **Website Builder** -- `ricet website` generates and deploys a GitHub Pages documentation site.
- **RAG-Powered MCP Discovery** -- Searchable index of 1300+ MCP servers with keyword-based suggestion and on-demand installation.
- **[PaperBoat](https://paperboatch.com/)** -- Recommended external service for daily cross-discipline paper discovery. Useful as a background SOTA knowledge source that updates daily.

Explore all features in the [Features](features.md) page.

---

## Project Philosophy

ricet is built on six core principles:

1. **Never please the user** -- Be objective, challenge assumptions, report flaws.
2. **Popperian falsification** -- Try to break results, not validate them.
3. **Never guess** -- Search or ask when uncertain.
4. **Test small, then scale** -- Downsample first, run one epoch, then scale up.
5. **Commit aggressively** -- Meaningful commits after every subtask.
6. **Accumulate knowledge** -- The encyclopedia grows with every task.

---

## Project Status

ricet is under active development. The core modules, CLI, Docker setup, templates, and agent system are implemented. Contributions and feedback are welcome.

| Component | Status |
|-----------|--------|
| CLI (`ricet` command) | Implemented |
| Core modules (45+ modules) | Implemented |
| Docker containerization | Implemented |
| Agent orchestration | Implemented |
| Paper pipeline | Implemented |
| MCP auto-discovery (70+) | Implemented |
| claude-flow integration | Implemented (optional) |
| GitHub workflows | Implemented |
| Voice & mobile access | Implemented |
| Interactive dashboard & gallery | Implemented |
| Documentation site | You are here |

---

## About

ricet is designed and maintained by **Luca Fusar Bassini**, a researcher who got tired of doing the same tedious setup for every project and decided to automate the entire scientific workflow instead. What started as a few helper scripts became a full multi-agent research framework.

---

## License

MIT
