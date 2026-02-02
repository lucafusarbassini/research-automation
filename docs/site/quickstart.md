# Quickstart: Your First Project in 5 Minutes

This tutorial walks you through creating a research project, running an interactive session, and launching overnight mode.

---

## Step 1: Install

```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Clone and install research-automation
git clone https://github.com/lucafusarbassini/research-automation
cd research-automation
pip install -e .

# Authenticate with Claude subscription (Pro or Team required, no API key needed)
claude auth login
```

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
    The more detailed your GOAL.md, the better the agents perform. Include your research question, methodology, expected outcomes, datasets, and constraints. One full page is ideal.

---

## Step 4: Start an Interactive Session

```bash
ricet start
```

This creates a tracked session and launches Claude Code. On start, the system:

1. Syncs with remote (`git pull --rebase`) for collaborative workflows.
2. Validates that `knowledge/GOAL.md` has sufficient content.
3. Infers and installs Python packages based on your goal description.
4. Starts the mobile server if enabled in settings.
5. Re-indexes linked repositories for cross-repo RAG.
6. Suggests next research steps based on your goal and progress.
7. Launches Claude Code with a tracked session UUID.

The agent system follows the **Progressive Instruction Protocol**:

1. **Orient** -- Reads GOAL.md, CONSTRAINTS.md, and TODO.md to understand context.
2. **Explore** -- Examines relevant code and data, builds a mental model.
3. **Plan** -- Breaks the goal into subtasks with difficulty estimates.
4. **Execute** -- Works through subtasks one at a time, checkpointing after each.
5. **Validate** -- Runs falsifier checks and documents learnings.

Try giving it a task:

```
Search for recent papers on transformer efficiency and summarize the top 5 findings.
```

The Master agent routes this to the Researcher agent, which uses paper-search MCPs to find and synthesize literature.

---

## Step 5: Check Status

Open a new terminal:

```bash
cd my-first-project
ricet status
```

This displays the current TODO list and progress log.

---

## Step 6: Run Overnight Mode

For longer tasks, use overnight mode:

```bash
ricet overnight --iterations 20
```

This runs Claude in an autonomous loop:

- Reads the TODO list
- Executes tasks one by one
- Auto-commits after each subtask
- Monitors resources and checkpoints progress
- Runs the falsifier agent after every iteration
- Stops when all tasks are done or the iteration limit is reached

For Docker-sandboxed execution:

```bash
ricet overnight --iterations 30 --docker
```

Check results in the morning:

```bash
ricet status
git log --oneline -20
```

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

# Agents can now search across all linked repos
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
