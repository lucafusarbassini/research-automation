# Tutorial 3: Your First Project

This tutorial walks you through creating a research project from scratch,
running your first interactive session, checking status, and understanding the
files that were generated. By the end you will have a fully initialized project
with agents, knowledge files, a paper template, and a TODO list.

**Time:** ~30 minutes

**Prerequisites:**
- [Tutorial 1: Getting API Keys](getting-api-keys.md) -- Anthropic key set
- Python 3.11+ and Node.js 20+ installed (or [Tutorial 2: Docker Setup](docker-setup.md) completed)
- Claude Code CLI installed: `npm install -g @anthropic-ai/claude-code`

---

## Table of Contents

1. [Install ricet](#1-install-ricet)
2. [Create a New Project](#2-create-a-new-project)
3. [Understand the Generated Files](#3-understand-the-generated-files)
4. [Start an Interactive Session](#4-start-an-interactive-session)
5. [Check Project Status](#5-check-project-status)
6. [Edit the TODO List](#6-edit-the-todo-list)
7. [Make Your First Commit](#7-make-your-first-commit)
8. [Next Steps](#8-next-steps)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Install ricet

### From the cloned repository

```bash
$ cd research-automation
$ pip install -e ".[all]"
```

### Verify the installation

```bash
$ ricet--version
ricet 0.2.0

$ ricet--help
Usage: ricet [OPTIONS] COMMAND [ARGS]...

Scientific ricet - manage research projects with Claude Code.

Commands:
  init            Initialize a new research project with full onboarding.
  start           Start an interactive research session.
  overnight       Run overnight autonomous mode.
  status          Show current project status.
  config          View or reconfigure project settings.
  list-sessions   List all sessions.
  agents          Show swarm agent status.
  memory          Search claude-flow vector memory.
  metrics         Show claude-flow performance metrics.
  paper           Paper pipeline commands.
```

> **Screenshot:** Terminal showing the help output of the `ricet` command with
> all available subcommands listed.

---

## 2. Create a New Project

Pick a directory where you want your projects to live, then run:

```bash
$ cd ~/projects    # or wherever you keep your work
$ ricetinit my-first-project
```

The onboarding wizard will ask you a series of questions. Here is what each
question means and example answers:

```
Creating project: my-first-project

Project Setup
What is the main goal of this project? Classify cell types from single-cell RNA-seq data
Project type (ml-research, data-analysis, paper-writing, computational, general) [ml-research]: ml-research
GitHub repository URL (or 'skip') [skip]: skip
Success criteria (comma-separated, or 'skip') [skip]: >90% accuracy on test set, reproduce baseline results, write methods section
Target completion date (or 'flexible') [flexible]: 2026-04-01
Compute resources (local-cpu, local-gpu, cloud, cluster) [local-cpu]: local-gpu
GPU name: NVIDIA RTX 4090
Notification method (email, slack, none) [none]: slack
Slack webhook URL: https://hooks.slack.com/services/T00/B00/XXX
```

> **Screenshot:** Terminal showing the interactive onboarding wizard prompts with
> the user typing answers to each question.

After answering all questions, the tool:

1. Copies templates into `my-first-project/`
2. Creates workspace directories (`reference/`, `local/`, `secrets/`, `uploads/`)
3. Writes `config/settings.yml` with your answers
4. Fills in `knowledge/GOAL.md` with your goal and success criteria
5. Creates `state/TODO.md` with starter tasks
6. Sets up claude-flow (if available)
7. Initializes a git repository with an initial commit

You will see:

```
Setting up claude-flow...
claude-flow ready

Project created at /home/you/projects/my-first-project

Next steps:
  cd /home/you/projects/my-first-project
  ricet start
```

---

## 3. Understand the Generated Files

```bash
$ cd my-first-project
$ ls -la
```

Here is what was created:

```
my-first-project/
├── .claude/                  # Claude Code agent definitions
│   ├── CLAUDE.md             # Main system prompt (progressive instruction protocol)
│   ├── agents/               # Specialized agent prompts
│   │   ├── master.md         # Orchestrator (routes tasks, never executes)
│   │   ├── coder.md          # Writes and modifies code
│   │   ├── researcher.md     # Literature search and synthesis
│   │   ├── reviewer.md       # Code quality review
│   │   ├── falsifier.md      # Adversarial validation (Popperian)
│   │   ├── writer.md         # Paper and documentation writing
│   │   └── cleaner.md        # Refactoring and cleanup
│   ├── skills/               # Domain-specific skill guides
│   │   ├── paper-writing.md  # Academic writing conventions
│   │   ├── figure-making.md  # Publication-quality figures
│   │   └── code-style.md     # Python code style rules
│   └── hooks/                # Lifecycle scripts
│       ├── pre-task.sh       # Runs before each task
│       ├── post-task.sh      # Runs after each task (auto-commits)
│       └── on-error.sh       # Runs on errors (snapshots state)
├── config/                   # Project configuration
│   ├── settings.yml          # Your onboarding answers
│   └── claude-flow.json      # Claude-flow orchestration config
├── knowledge/                # Persistent knowledge base
│   ├── GOAL.md               # Your project goal and success criteria
│   └── ENCYCLOPEDIA.md       # Auto-updated learnings (grows over time)
├── paper/                    # LaTeX paper template
│   ├── main.tex              # Paper source
│   ├── references.bib        # Bibliography
│   └── Makefile              # Build commands (make all, make clean)
├── state/                    # Runtime state
│   ├── TODO.md               # Current task list
│   ├── PROGRESS.md           # Completed tasks log
│   └── sessions/             # Session logs
├── reference/                # Read-only reference materials
├── local/                    # Local working files
├── secrets/                  # Credentials (gitignored)
└── uploads/                  # User-uploaded files
```

### Key files to understand

**`knowledge/GOAL.md`** -- This is the north star for every agent. Open it and
verify your goal and success criteria are correct:

```bash
$ cat knowledge/GOAL.md
```

**`state/TODO.md`** -- The task list that drives both interactive and overnight
modes:

```bash
$ cat state/TODO.md
# TODO

- [ ] Review GOAL.md and refine success criteria
- [ ] Set up environment
- [ ] Begin first task
```

**`.claude/CLAUDE.md`** -- The master system prompt. Every Claude Code session
reads this first. It defines the five-phase protocol: Orient, Explore, Plan,
Execute, Validate.

---

## 4. Start an Interactive Session

```bash
$ ricetstart
```

This command:

1. Creates a timestamped session file in `state/sessions/`
2. Launches Claude Code with the `--session-id` flag
3. Claude Code reads `.claude/CLAUDE.md` and enters the Orient phase

You can also name your session:

```bash
$ ricetstart --session-name "literature-review"
```

> **Screenshot:** Terminal showing Claude Code starting up, reading CLAUDE.md,
> and presenting its initial Orient-phase summary of the project goal.

### Your first interaction

Once Claude Code is running, try these commands:

```
You: Read knowledge/GOAL.md and state/TODO.md, then tell me what you understand about this project.
```

Claude will read the files and summarize the project. Then:

```
You: Let's start with the first task -- setting up the Python environment. What packages do we need?
```

Claude will analyze the project type and suggest an appropriate environment
setup.

### End the session

Press `Ctrl+C` or type `/exit` to end the session. Your progress is saved in
`state/sessions/` and any commits made during the session are preserved in git.

---

## 5. Check Project Status

From your project directory, at any time:

```bash
$ ricetstatus
```

Output:

```
TODO:
# TODO

- [ ] Review GOAL.md and refine success criteria
- [ ] Set up environment
- [ ] Begin first task

Progress:
# Progress

```

As you complete tasks, the post-task hook automatically updates `PROGRESS.md`
and checks off items in `TODO.md`.

### List past sessions

```bash
$ ricetlist-sessions
  20260201_143022 - active (2026-02-01)
  literature-review - active (2026-02-01)
```

### View agent status

```bash
$ ricetagents
```

### View resource metrics

```bash
$ ricetmetrics
```

---

## 6. Edit the TODO List

The TODO list is a plain Markdown file. You can edit it manually:

```bash
$ nano state/TODO.md     # or use any editor
```

A good TODO list for a new ML research project might look like:

```markdown
# TODO

## Phase 1: Setup
- [ ] Set up conda environment with required packages
- [ ] Download and inspect the dataset
- [ ] Write data loading utilities

## Phase 2: Baseline
- [ ] Implement baseline model from reference paper
- [ ] Train on small subset (100 samples) to verify pipeline
- [ ] Train on full dataset and record baseline metrics

## Phase 3: Experiment
- [ ] Implement proposed improvement
- [ ] Run ablation studies
- [ ] Compare against baseline

## Phase 4: Paper
- [ ] Write methods section
- [ ] Generate figures
- [ ] Write results section
```

Claude reads this file at the start of every session and during overnight mode.
Keep it up to date.

---

## 7. Make Your First Commit

ricet encourages aggressive committing. The post-task hook
auto-commits after each completed task, but you can also commit manually:

```bash
$ git status
$ git add -A
$ git commit -m "Refine TODO list and success criteria"
```

To push to GitHub (if you set up a remote):

```bash
$ git remote add origin git@github.com:YOUR_USERNAME/my-first-project.git
$ git push -u origin main
```

---

## 8. Next Steps

Now that your project is initialized, here are the recommended next tutorials:

| What you want to do | Tutorial |
|---------------------|----------|
| Write a paper with LaTeX | [Paper Writing](paper-writing.md) |
| Run tasks unattended overnight | [Overnight Mode](overnight-mode.md) |
| Build an academic website | [Website Setup](website-setup.md) |
| Check progress from your phone | [Mobile Access](mobile-access.md) |

### Tips for productive sessions

1. **Be specific in your prompts.** Instead of "analyze the data", say "load
   `data/train.csv`, compute summary statistics, and plot the distribution of
   the target variable."

2. **Let Claude orient first.** Start each session by asking Claude to read
   GOAL.md and TODO.md before jumping into tasks.

3. **Review commits.** After each session, run `git log --oneline -10` to see
   what was done.

4. **Update the encyclopedia.** If you learn something important (a hyperparameter
   that works, a library quirk), ask Claude to add it to `knowledge/ENCYCLOPEDIA.md`.

5. **Use the falsifier.** Before considering results final, say: "Run the
   falsifier agent on these results." It will try to find flaws.

---

## 9. Troubleshooting

### `research: command not found`

The CLI was not installed or is not on your PATH.

```bash
# If installed via pip:
$ pip install -e ".[all]"

# Check where it was installed:
$ which research

# If using a virtual environment, make sure it is activated:
$ source venv/bin/activate
```

### `claude: command not found`

Claude Code CLI is not installed.

```bash
$ npm install -g @anthropic-ai/claude-code
```

### Onboarding exits unexpectedly

This can happen if `typer` is not installed:

```bash
$ pip install typer rich pyyaml python-dotenv
```

### Git init fails

If git is not configured with your identity:

```bash
$ git config --global user.name "Your Name"
$ git config --global user.email "your_email@example.com"
```

### "claude-flow setup skipped"

This is normal. Claude-flow is an optional orchestration layer. The system
works without it by falling back to direct Claude CLI calls.

### Session does not persist

Make sure you are running `ricet start` from inside your project directory
(the one containing `.claude/` and `state/`).

---

**Next:** [Tutorial 4: Paper Writing](paper-writing.md)
