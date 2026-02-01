# Research Automation

**Automate scientific research using Claude Code with multi-agent orchestration, overnight autonomous execution, and comprehensive tooling.**

Research Automation is a CLI tool and framework that manages the full lifecycle of scientific research projects. It pairs Claude Code with a structured agent system, persistent knowledge, reproducibility enforcement, and a complete paper pipeline -- so you can focus on the science while automation handles the scaffolding.

---

## Why Research Automation?

Running a research project involves dozens of repetitive tasks: environment setup, literature searches, experiment tracking, figure generation, paper writing, and more. Research Automation provides a single `research` command that orchestrates all of these through specialized AI agents operating inside a safe, containerized environment.

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
git clone https://github.com/YOUR_USERNAME/research-automation
cd research-automation

# Install the CLI
pip install -e .

# Create your first project
research init my-project

# Start an interactive session
cd my-project
research start

# Or run overnight
research overnight --iterations 20
```

See the full [Quickstart Tutorial](quickstart.md) for a step-by-step walkthrough.

---

## Feature Highlights

- **Multi-Agent Orchestration** -- Master agent routes tasks to Researcher, Coder, Reviewer, Falsifier, Writer, and Cleaner sub-agents, each with dedicated budgets and system prompts.
- **70+ MCP Integrations** -- Automatically discovered and loaded based on task type, organized in eight tiers from essential tools to cloud infrastructure.
- **Overnight Mode** -- Autonomous execution loop with auto-debug, resource monitoring, and recovery. Run `research overnight` and check results in the morning.
- **Knowledge Accumulation** -- A project encyclopedia that records learnings, decisions, successful approaches, and failed attempts. Supports HNSW vector search when claude-flow is available.
- **Paper Pipeline** -- LaTeX template, publication-quality figure generation with matplotlib rcParams, BibTeX citation management, and one-command compilation.
- **Reproducibility** -- Every experiment run is logged with parameters, metrics, git hash, and SHA-256 artifact checksums.
- **Docker Isolation** -- Safe containerized execution with four permission levels (Safe, Moderate, Elevated, Dangerous).
- **3-Tier Model Routing** -- Automatic model selection (Haiku/Sonnet/Opus) based on task complexity, with budget-aware fallback.
- **Progressive Instructions** -- Five-phase protocol: Orient, Explore, Plan, Execute, Validate.
- **Cross-Repository Coordination** -- Link multiple repos, coordinate commits, and enforce permission boundaries.

Explore all features in the [Features](features.md) page.

---

## Project Philosophy

Research Automation is built on six core principles:

1. **Never please the user** -- Be objective, challenge assumptions, report flaws.
2. **Popperian falsification** -- Try to break results, not validate them.
3. **Never guess** -- Search or ask when uncertain.
4. **Test small, then scale** -- Downsample first, run one epoch, then scale up.
5. **Commit aggressively** -- Meaningful commits after every subtask.
6. **Accumulate knowledge** -- The encyclopedia grows with every task.

---

## Project Status

Research Automation is under active development. The core modules, CLI, Docker setup, templates, and agent system are implemented. Contributions and feedback are welcome.

| Component | Status |
|-----------|--------|
| CLI (`research` command) | Implemented |
| Core modules (20+ modules) | Implemented |
| Docker containerization | Implemented |
| Agent orchestration | Implemented |
| Paper pipeline | Implemented |
| MCP auto-discovery | Implemented |
| claude-flow integration | Implemented (optional) |
| GitHub workflows | Implemented |
| Documentation site | You are here |

---

## License

MIT
