# FAQ

Frequently asked questions about ricet.

---

## General

### What is ricet?

ricet is a CLI tool and framework that manages scientific research projects using Claude Code. It provides multi-agent orchestration, persistent knowledge, reproducibility enforcement, a paper pipeline, and overnight autonomous execution -- all from a single `ricet` command.

### Who is this for?

Researchers, data scientists, and engineers who use AI assistants for scientific work and want a structured, reproducible, and automated workflow around them.

### What models does it use?

ricet is built around Anthropic's Claude models. The model router selects between Claude Haiku (simple tasks), Claude Sonnet (medium tasks), and Claude Opus (complex/critical tasks) based on task complexity and remaining budget.

### Is claude-flow required?

No. claude-flow is an optional integration that enhances orchestration with swarm execution, HNSW vector memory, and 3-tier model routing. Without it, every feature falls back to a built-in implementation. The system works identically either way.

### What programming languages are supported?

The tool itself is written in Python 3.11+. The agent system can work with any language your research uses -- Python, R, Julia, MATLAB, etc. -- since Claude Code executes arbitrary commands.

---

## Installation

### What are the minimum requirements?

- Python 3.11 or newer
- Node.js 20 or newer (for Claude Code CLI)
- Git
- A Claude subscription (Pro or Team) -- authenticate via `claude auth login`

### Can I use it without Docker?

Yes. Docker is optional. The `pip install -e .` method works without Docker. Docker provides a pre-configured, isolated environment with all system dependencies (LaTeX, ffmpeg, GPU libraries) but is not required for core functionality.

### How do I update?

```bash
cd research-automation
git pull origin master
pip install -e .
```

### Does it work on Windows?

The core Python modules work on Windows. Some shell scripts (`scripts/*.sh`) and hooks (`templates/.claude/hooks/*.sh`) are Bash-specific and require WSL or Git Bash. Docker mode works on any platform with Docker Desktop.

---

## Usage

### How do I create a new project?

```bash
ricet init my-project
```

This runs an interactive wizard that auto-detects your system (GPU, conda, Docker), sets up claude-flow, walks you through notification and credential configuration, creates the project structure from templates, optionally creates a conda environment with inferred packages, and initializes a GitHub repository. The project goal is written to `knowledge/GOAL.md` after init -- the wizard does not ask for it as a one-liner.

### What happens during `ricet start`?

1. Syncs with remote (`git pull --rebase`) for collaborative workflows.
2. Validates that `knowledge/GOAL.md` has at least 200 characters of real content. Opens your `$EDITOR` if insufficient.
3. Infers and installs Python packages based on your goal description.
4. Starts the mobile server if enabled in settings.
5. Re-indexes linked repositories for cross-repo RAG search.
6. Creates a session record in `state/sessions/`.
7. Suggests next research steps based on your goal and progress.
8. Launches Claude Code with a tracked session UUID.
9. The Master agent follows the Progressive Instruction Protocol: Orient, Explore, Plan, Execute, Validate.

### Is overnight mode safe?

Overnight mode uses `--dangerously-skip-permissions` to run without interactive approval. The safety model relies on:

- Docker isolation (when used)
- Four-tier permission levels
- Immutable file protection
- Secret scanning
- Audit logging
- Confirmation gates for dangerous operations (spending money, sending emails)

Review the permission model in `docker/permissions.md` and configure it for your risk tolerance.

### How does token budget tracking work?

Each session has a token limit (default: 100,000) and a daily limit (default: 500,000). The system estimates token usage at ~4 characters per token (or uses actual metrics from claude-flow). Warnings fire at 50%, 75%, and 90% usage. When budget drops below 20%, all tasks automatically route to Claude Haiku.

### Can I use multiple projects at once?

Yes. Each project is a self-contained directory with its own state, knowledge, and configuration. The shared volume (`/shared/knowledge`) enables knowledge transfer between projects, and `core/cross_repo.py` supports coordinated commits across linked repositories.

---

## Agents

### What are the agent types?

| Agent | Role |
|-------|------|
| Master | Orchestrator -- routes tasks, never executes directly |
| Researcher | Literature search and synthesis |
| Coder | Code writing and bug fixes |
| Reviewer | Code quality audits |
| Falsifier | Adversarial validation (Popperian) |
| Writer | Paper and documentation writing |
| Cleaner | Refactoring and optimization |

### Can I customize agent prompts?

Yes. Agent prompts live in `.claude/agents/` inside your project. Edit them directly. Changes take effect on the next session.

### How does task routing work?

The Master agent analyzes your request against keyword sets for each agent type. For example, words like "search", "literature", "arxiv" route to the Researcher. Words like "implement", "function", "bug" route to the Coder. You can also explicitly name an agent in your request.

### What is the Falsifier agent?

Inspired by Karl Popper's philosophy of science, the Falsifier's job is to destroy results rather than validate them. It checks for data leakage, statistical validity, code correctness, methodology issues, and reproducibility problems. It produces a structured report with critical issues, warnings, and passed checks.

---

## Knowledge

### What is the encyclopedia?

The file `knowledge/ENCYCLOPEDIA.md` is a living document that accumulates project knowledge. It has sections for environment info, tricks, design decisions, successful approaches, and failed approaches. Entries are timestamped and can be added automatically after tasks or manually.

### How does vector search work?

When claude-flow is installed, knowledge entries are dual-written to both the markdown file and an HNSW vector index. The `ricet memory search "query"` command performs semantic search over indexed entries. Without claude-flow, search falls back to keyword grep.

### Is knowledge shared across projects?

It can be. The Docker setup mounts a `/shared/knowledge` volume. The `sync_shared_knowledge()` function copies relevant entries to the shared location, and new projects can read from it.

---

## Paper Pipeline

### What LaTeX template is included?

A standard article template with sections for Abstract, Introduction, Methods, Results, Discussion, and Conclusion. It uses natbib for citations and includes packages for math, graphics, hyperlinks, tables, and microtypography.

### How do I generate publication-quality figures?

```python
from core.paper import apply_rcparams, COLORS

apply_rcparams()
# Now all matplotlib plots use publication defaults:
# Arial font, 300 DPI, clean spines, colorblind-safe colors
```

### How do I add citations?

```python
from core.paper import add_citation

add_citation(
    "Smith2024",
    author="Smith, J.",
    title="A Great Paper",
    year="2024",
    journal="Nature",
)
```

This appends a BibTeX entry to `paper/references.bib`. Use `\cite{Smith2024}` in your LaTeX.

---

## Reproducibility

### What gets logged for each run?

- Run ID
- Full command
- Start and end timestamps
- Git hash at time of execution
- All parameters as a dict
- All metrics as a dict
- List of artifact paths
- Status (running, success, failure)

### How does artifact verification work?

When you register an artifact, its SHA-256 checksum is recorded. Later, `verify_artifact()` recomputes the checksum and compares. If the file has changed, it flags a mismatch.

---

## Security

### What secrets are detected?

The scanner looks for: API keys, passwords, tokens, AWS credentials, OpenAI keys (`sk-...`), GitHub PATs (`ghp_...`), and PEM/private key headers. Custom patterns can be added via the `extra_patterns` parameter.

### What files are immutable?

`.env`, `.env.local`, `secrets/*`, `*.pem`, and `*.key` are never modified by automation. This list is configurable via `DEFAULT_IMMUTABLE` in `core/security.py`.

### Is there an audit log?

Yes. All autonomous actions are recorded in `state/audit.log` with ISO timestamps and descriptions. Review this file to verify what the system did during overnight runs.

---

## Troubleshooting

### The system routes tasks to the wrong agent

Agent routing uses intelligent Opus-powered semantic analysis. If tasks are misrouted:

1. Be more explicit in your request ("As the Coder agent, implement...").
2. Ensure Claude Opus is available (check that `RICET_NO_CLAUDE` is not set).
3. As a last resort, adjust the `ROUTING_KEYWORDS` fallback dict in `core/agents.py`.
4. Modify the agent prompts in `.claude/agents/` to better define boundaries.

### Overnight mode stops unexpectedly

Check `state/sessions/current.log` for error entries. Common causes:

- API rate limits (the system retries but may hit a wall)
- Disk space exhaustion (check `df -h`)
- Token budget exceeded (increase `session_limit` in `core/tokens.py`)

### The knowledge encyclopedia is not updating

Verify that:

1. `knowledge/ENCYCLOPEDIA.md` exists with the expected section headers.
2. The post-task hook (`templates/.claude/hooks/post-task.sh`) is executable.
3. Section names match exactly: "Tricks", "Decisions", "What Works", "What Doesn't Work".

### claude-flow commands fail

Run the setup script to verify installation:

```bash
bash scripts/setup_claude_flow.sh
```

If claude-flow is unavailable, the system silently falls back to local implementations. No functionality is lost.

### Mobile server does not start

- Ensure `openssl` is installed (required for TLS certificate generation)
- Check that port 8777 is not already in use: `lsof -i :8777`
- Verify mobile access is enabled: check `config/settings.yml` for `features.mobile: true`
- Start manually with: `ricet mobile serve`

### Cannot connect to mobile server from phone

- Both devices must be on the same network (or use an SSH tunnel / VPN)
- Check firewall: `sudo ufw allow 8777/tcp`
- The self-signed certificate will show a browser warning -- verify the fingerprint with `ricet mobile connect-info` before accepting
- Ensure the bearer token is included in the `Authorization` header or URL parameter

### Mobile PWA shows "offline"

- The PWA service worker caches the app shell but API calls require a live connection
- Check that the server is running: `ricet mobile status`
- Verify network connectivity between phone and server
