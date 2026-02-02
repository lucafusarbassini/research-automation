# Quickstart: Your First Project in 5 Minutes

This tutorial walks you through creating a research project, running an interactive session, and launching overnight mode.

---

## Step 1: Install

```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Clone and install research-automation
git clone https://github.com/YOUR_USERNAME/research-automation
cd research-automation
pip install -e .

# Authenticate with Claude (no API key needed)
claude auth login
```

---

## Step 2: Create a Project

```bash
ricet init my-first-project
```

The interactive onboarding wizard will ask you:

1. **Project goal** -- A one-liner describing what you want to achieve.
2. **Project type** -- Choose from `ml-research`, `data-analysis`, `paper-writing`, or `general`.
3. **Timeline and constraints** -- Budget, deadlines, compute limits.

The command creates a fully scaffolded project directory:

```
my-first-project/
├── .claude/
│   ├── CLAUDE.md           # Agent instructions
│   ├── agents/             # 7 specialized agent prompts
│   ├── skills/             # Paper writing, figure making, code style
│   └── hooks/              # Pre-task, post-task, on-error hooks
├── knowledge/
│   ├── GOAL.md             # Your project goal
│   ├── ENCYCLOPEDIA.md     # Auto-growing knowledge base
│   └── CONSTRAINTS.md      # Boundaries and rules
├── paper/
│   ├── main.tex            # LaTeX template
│   ├── references.bib      # Bibliography
│   └── Makefile            # Build automation
├── config/
│   └── settings.yml        # Project settings
└── state/                  # Session logs, progress tracking
```

---

## Step 3: Start an Interactive Session

```bash
cd my-first-project
ricet start
```

This creates a tracked session and launches Claude Code. The agent system follows the **Progressive Instruction Protocol**:

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

## Step 4: Check Status

Open a new terminal:

```bash
cd my-first-project
ricet status
```

This displays the current TODO list and progress log.

---

## Step 5: Run Overnight Mode

For longer tasks, use overnight mode:

```bash
ricet overnight --iterations 20
```

This runs Claude in an autonomous loop:

- Reads the TODO list
- Executes tasks one by one
- Auto-commits after each subtask
- Monitors resources and checkpoints progress
- Stops when all tasks are done or the iteration limit is reached

Check results in the morning:

```bash
ricet status
git log --oneline -20
```

---

## Step 6: Build Your Paper

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

## Step 7: View the Dashboard

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

## Step 8: Link Related Repositories

If you work across multiple repos, link them for cross-repository search:

```bash
# Link repos for RAG-powered search
ricet link ~/code/shared-library --name shared
ricet link ~/code/data-pipeline

# Agents can now search across all linked repos
ricet memory "data preprocessing pipeline"

# Re-index after external changes
ricet reindex
```

Linked repos are read-only -- agents search them for context but only write to the current project.

---

## Next Steps

- Read [Features](features.md) for a complete overview of all capabilities.
- Read [Architecture](architecture.md) to understand the module relationships.
- Read [API Reference](api.md) for detailed module documentation.
- Check the [FAQ](faq.md) for common questions.
