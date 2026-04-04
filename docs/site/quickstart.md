# Quickstart: Your First Project in 5 Minutes

This tutorial walks you through creating a research project, running an interactive session, and launching overnight mode.

---

## Step 1: Install

```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Authenticate with Claude subscription (Pro or Team required, no API key needed)
claude auth login

# Clone and install ricet
git clone https://github.com/lucafusarbassini/research-automation
cd research-automation
pipx install ".[mobile]"
# If pipx is not installed: sudo apt install pipx && pipx ensurepath
```

!!! note "Docker Compose v2 required"
    `ricet up` uses Docker Compose v2 (the `docker compose` plugin). The standalone `docker-compose` v1 is **not supported**. Install the plugin: `sudo apt install docker-compose-plugin`. See the [Docker Setup tutorial](../tutorials/docker-setup.md) for details.

---

## Step 2: Create a Project

```bash
ricet init my-first-project
```

The `ricet init` wizard runs through several automated and interactive steps:

### Step 0: Package Check

The CLI verifies that required Python packages (`typer`, `rich`, `pyyaml`, `python-dotenv`) are installed, auto-installing any that are missing.

### Step 1: System Detection

The wizard auto-detects your system capabilities:

```
Step 1: Detecting system...
  OS:      Linux 6.8.0-52-generic
  Python:  3.11.10
  CPU:     x86_64
  RAM:     32 GB
  GPU:     NVIDIA RTX 4090
  Compute: local-gpu (auto-detected)
  Docker:  Available
  Conda:   Available
```

GPU availability and compute type are inferred automatically -- you do not need to specify them manually.

### Step 2: Claude-Flow Setup

The wizard checks for and installs `claude-flow` (optional orchestration layer) and verifies Claude CLI authentication:

```
Step 2: Setting up claude-flow...
  claude-flow is ready

Step 2b: Checking Claude authentication...
  Claude CLI available
```

### Step 3: Interactive Questionnaire

The streamlined questionnaire asks for:

1. **Notification method** -- `email`, `slack`, or `none`.
2. **Target journal or conference** -- e.g. `Nature Machine Intelligence` or `skip`.
3. **Web dashboard** -- whether you want a project website (`yes`/`no`).
4. **Mobile access** -- whether you want mobile phone control (`yes`/`no`).

!!! note
    The project goal is **not** entered as a one-liner during init. Instead, you write a detailed description in `knowledge/GOAL.md` after the project is created. The wizard prompts you to do this.

### Step 3b: API Credentials

The wizard walks you through optional API credentials one by one, grouped by category (core, ML, publishing, cloud, integrations). Each credential shows where to get it and whether it is free or paid. Press Enter to skip any credential you do not have yet.

```
Step 3b: API credentials
  Press Enter to skip any credential you don't have yet.

  --- Essential credentials (Enter to skip any) ---
  Anthropic API key [PAID, skip unless you need direct API access] (ANTHROPIC_API_KEY):
  GitHub PAT [FREE] (GITHUB_PERSONAL_ACCESS_TOKEN):
  ...
```

All credentials are stored in `secrets/.env` (gitignored) and a `secrets/.env.example` template is generated for reference.

### Step 4: Project Creation

The wizard copies templates, creates workspace directories, writes settings, and optionally creates a conda/mamba environment with packages inferred from your goal description.

### Step 5: GitHub Repository

Optionally creates a private GitHub repository using the `gh` CLI, sets the remote, and configures repo description and topics from `GOAL.md`.

### Step 6: Git Initialization

Initializes git, commits the scaffolded project, and registers it in the global project registry (`~/.ricet/projects.json`).

### Result

The command creates a fully scaffolded project directory:

```
my-first-project/
├── .claude/
│   ├── CLAUDE.md           # Agent instructions
│   ├── agents/             # 7 specialized agent prompts
│   ├── skills/             # Paper writing, figure making, code style
│   └── hooks/              # Pre-task, post-task, on-error hooks
├── knowledge/
│   ├── GOAL.md             # Your project goal (EDIT THIS)
│   ├── ENCYCLOPEDIA.md     # Auto-growing knowledge base
│   └── CONSTRAINTS.md      # Boundaries and rules
├── paper/
│   ├── main.tex            # LaTeX template
│   ├── references.bib      # Bibliography
│   └── Makefile            # Build automation
├── config/
│   └── settings.yml        # Project settings
├── reference/
│   ├── papers/             # Background papers (PDF, etc.)
│   └── code/               # Reference code, scripts, notebooks
├── uploads/
│   ├── data/               # Datasets (large files auto-gitignored)
│   └── personal/           # Your papers, CV, writing samples
├── secrets/
│   ├── .env                # API keys (never committed)
│   └── .env.example        # Template showing all variables
├── state/
│   ├── sessions/           # Session logs
│   ├── TODO.md             # Goal-aware task list
│   └── PROGRESS.md         # Progress tracking
└── environment.yml         # Conda environment spec
```

---

## Step 3: Edit GOAL.md

Before starting your first session, write a detailed project description:

```bash
cd my-first-project
$EDITOR knowledge/GOAL.md
```

Write at least 200 characters of real content describing your research question, methodology, expected outcomes, and constraints. `ricet start` enforces this minimum and will open your editor if the file is insufficient.

!!! tip
    The more detailed your GOAL.md, the better Claude performs. Include your research question, methodology, expected outcomes, datasets, and constraints. One full page is ideal.

---

## Step 4: Launch with `ricet up`

```bash
ricet up
```

This is the primary way to run ricet. It launches a complete, persistent Claude session:

1. **Docker sandbox** -- Builds and starts an isolated container with `--dangerously-skip-permissions` (safe because it's sandboxed). CPU/RAM limits auto-detected.
2. **GNU Screen** -- Claude runs inside a screen session that survives disconnects. If Claude exits, it auto-restarts in 5 seconds.
3. **Session persistence** -- Uses `--continue` to resume the most recent conversation on restart. No work is lost on disconnect.
4. **Mobile dashboard** -- A phone-accessible PWA with voice (Italian auto-translated to English) and text task injection via Tailscale.
5. **Remote Control** -- `/remote-control` QR code for the Claude mobile app.

### Three ways to interact

| Channel | How | Use case |
|---------|-----|----------|
| **CLI** | `screen -r <project-name>` | Full interactive session |
| **Phone app** | Scan `/remote-control` QR code | Claude app on mobile |
| **Dashboard** | Open Tailscale URL in phone browser | Voice commands, text tasks, monitor |

### First-time container setup

On the first `ricet up` after a container rebuild, Claude may need a one-time login:

```bash
# Attach to screen
screen -r <project-name>

# If Claude shows a login prompt:
docker exec -it ricet-<project-name> gosu agent claude auth login

# Once Claude is running, enable remote control:
/remote-control

# Detach from screen: Ctrl+A then D
```

### Multi-project isolation

Each project gets its own screen session, Docker container, and port (derived from the project name). Multiple projects can run simultaneously on the same machine.

### Stopping

```bash
ricet down
```

Tears down: mobile server, Tailscale serve, screen session, and Docker container.

---

## Step 5: Check Status

Open a new terminal:

```bash
cd my-first-project
ricet status
```

This displays the current TODO list and progress log. Or open the mobile dashboard's Monitor tab to see live screen output.

---

## Step 6: Backup and Export

The sandbox workspace is bind-mounted at `sandbox/workspace/` so VS Code can see files in real time.

### Periodic backup

```bash
# From the project directory:
./sandbox/auto-backup.sh 15   # Backup every 15 minutes
```

This syncs experiments, state files, and logs from the container to the host every N minutes.

### Extract work as a patch

```bash
./sandbox/extract-work.sh          # Generate a .patch file
./sandbox/extract-work.sh --apply  # Apply patch to host repo
```

### Watchdog auto-save

The container has a built-in watchdog that auto-commits work before the timeout expires (default 24h for `ricet up`).

---

## Step 7: Overnight Mode (Alternative)

For unattended batch work, use overnight mode instead of `ricet up`:

```bash
ricet overnight --iterations 20 --docker
```

Each iteration is a fresh Claude session that reads the TODO list and works through tasks. Use this for fire-and-forget batch processing rather than interactive work.

---

## Step 7: Build Your Paper

Once you have results:

```bash
# Compile the LaTeX paper
cd paper
make all

# Or use the CLI
ricet paper build
```

The paper pipeline provides:

- Publication-quality figure generation with colorblind-safe palettes
- Automatic citation management via BibTeX
- One-command PDF compilation

---

## Step 8: View the Dashboard

For a richer view of your project:

```bash
ricet dashboard
```

The TUI dashboard shows:

- Active agents and their status
- Token budget usage
- Resource utilization (CPU, RAM, GPU)
- Recent progress entries

---

## Step 9: Mobile Access

If you enabled mobile access during init, the server starts automatically with `ricet start`. You can also manage it manually:

```bash
# Start the mobile HTTPS server
ricet mobile serve

# Pair your phone (generates token + QR code)
ricet mobile pair

# View connection methods
ricet mobile connect-info
```

Open the generated URL on your phone to access the PWA dashboard with task submission, voice commands, and project monitoring. See [Mobile Access](mobile.md) for the full guide.

---

## What Happens Under the Hood

When you run `ricet start`, the system:

1. Creates a session record in `state/sessions/`.
2. Loads tier-1 MCPs (paper search, git, GitHub, filesystem, memory).
3. Activates agent prompts from `.claude/agents/`.
4. Starts the pre-task hook to log the session and load knowledge.
5. Routes your request through the Master agent to the appropriate specialist.
6. After each task, the post-task hook auto-commits and updates progress.

Token usage is tracked throughout. At 50%, 75%, and 90% of the session budget, you get warnings. When budget is low, the model router automatically switches to cheaper models.

---

## Alternative: Adopt an Existing Repository

Already have a repo? Use `ricet adopt` instead of `ricet init`:

```bash
# Fork a GitHub repo and scaffold it as a ricet project
ricet adopt https://github.com/user/existing-repo

# Or scaffold a local directory in place
ricet adopt /path/to/my-code
```

This overlays the ricet workspace structure without disturbing existing code, pre-fills the goal from README, and registers the project.

---

## Step 10: Link Related Repositories

If you work across multiple repos, link them for cross-repository search:

```bash
# Link repos for RAG-powered search
ricet link ~/code/shared-library --name shared
ricet link ~/code/data-pipeline

# Claude can now search across all linked repos
ricet memory search "data preprocessing pipeline"

# Re-index after external changes
ricet reindex
```

Linked repos are read-only -- agents search them for context but only write to the current project.

---

## Next Steps

- Read [Features](features.md) for a complete overview of all capabilities.
- Read [Mobile Access](mobile.md) for phone-based project control.
- Read [Architecture](architecture.md) to understand the module relationships.
- Read [API Reference](api.md) for detailed module documentation.
- Check the [FAQ](faq.md) for common questions.
