# Claude Overnight Autonomous Agent Toolkit

A portable infrastructure for running Claude Code agents autonomously overnight in
isolated Docker containers. Battle-tested across two research projects (BioCypher
knowledge graph pipeline + Raman spectroscopy ML simulation).

## What's In This Toolkit

```
claude-overnight-toolkit/
├── USAGE.md                          # This file — full guide
├── setup-project.sh                  # One-command project setup
├── martinprompt.md                   # The orchestrator prompt (the brain)
├── .gitignore
│
├── sandbox/                          # Docker sandbox infrastructure
│   ├── Dockerfile.python             # For ML/data-science projects (lighter)
│   ├── Dockerfile.dind               # For projects needing Docker-in-Docker
│   ├── docker-compose.sandbox.yml    # Container orchestration
│   ├── .env.example                  # Environment variables template
│   ├── sandbox-entrypoint.sh         # Container init (copy project, setup git, install deps)
│   ├── watchdog.sh                   # Auto-shutdown timer with work-saving
│   ├── start-sandbox.sh              # Start the container
│   ├── stop-sandbox.sh               # Stop the container
│   ├── run-overnight.sh              # Loop: run Claude N times with per-iteration timeout
│   ├── extract-work.sh               # Pull changes out as git patches
│   └── auto-backup.sh               # Periodic sync of results to host
│
├── agents/                           # Subagent prompt definitions
│   ├── agent-experimenter.md         # Runs experiments, collects metrics
│   ├── agent-analyst.md              # Analyzes results, generates figures
│   └── agent-debugger.md             # Diagnoses failures, checks for leakage
│
└── templates/                        # State file templates
    ├── CLAUDE.md                     # Claude Code auto-reads this (project guidance)
    ├── task.md                       # Task specification (you fill this in)
    ├── memory.md                     # Persistent learnings across iterations
    ├── progress.md                   # Achievement log
    ├── todo.md                       # Work items queue
    └── system.md                     # Environment inventory
```

## Quick Start (5 minutes)

### Prerequisites
- Docker installed and running
- Claude CLI installed and authenticated (`npm install -g @anthropic-ai/claude-code`)
- An Anthropic API key with sufficient credits

### Step 1: Set up your project

```bash
# For a Python/ML project (most common):
./setup-project.sh /path/to/your/project

# For a project that needs Docker-in-Docker:
./setup-project.sh /path/to/your/project --dind
```

This copies all sandbox infrastructure, agent definitions, and templates into your project.

### Step 2: Define your task

Edit `task.md` in your project root. Be specific about what success looks like:

```markdown
# Task: Train a classifier for cell-type identification from scRNA-seq data

## Objective
Train a neural network that classifies cell types from single-cell RNA-seq data
with >90% accuracy on held-out donors.

## Requirements
1. Data loading from AnnData format
2. Cross-donor train/test split (no leakage)
3. Baseline comparison (logistic regression, random forest)
4. Negative controls (shuffled labels, permuted features)
5. Reproducible results with fixed seeds
```

### Step 3: Configure the sandbox

```bash
cd your-project/sandbox/
cp .env.example .env
# Edit .env — set SANDBOX_TIMEOUT_HOURS and CONTAINER_NAME
```

### Step 4: Launch

```bash
# Build and start the container
./start-sandbox.sh

# Start the overnight loop (30 iterations, 60 min each)
docker exec -d my-sandbox gosu agent bash /workspace/sandbox/run-overnight.sh 30 60
```

### Step 5: Monitor (optional)

```bash
# Watch Claude's output live
docker exec my-sandbox tail -f /agent-logs/claude-output.log

# Run auto-backup every 15 minutes (in a separate terminal)
./auto-backup.sh 15
```

### Step 6: Extract results

```bash
# Generate a git patch of all changes
./extract-work.sh

# Or generate and apply in one step
./extract-work.sh --apply
```

## Architecture

### How It Works

```
┌─────────────────────────────────────────────────┐
│ HOST MACHINE                                     │
│                                                  │
│  your-project/  ──(read-only mount)──┐          │
│  ~/.claude/     ──(read-only mount)──┤          │
│                                      │          │
│  ┌───────────────────────────────────▼──────┐   │
│  │ DOCKER CONTAINER (sandbox)                │   │
│  │                                           │   │
│  │  /project-source (read-only)              │   │
│  │       │                                   │   │
│  │       ▼ (copied once on first start)      │   │
│  │  /workspace (persistent volume)           │   │
│  │       │                                   │   │
│  │       ├── .git (auto-initialized)         │   │
│  │       ├── task.md                         │   │
│  │       ├── martinprompt.md                 │   │
│  │       ├── memory.md (agent's brain)       │   │
│  │       ├── todo.md                         │   │
│  │       ├── progress.md                     │   │
│  │       ├── experiments/                    │   │
│  │       └── reports/                        │   │
│  │                                           │   │
│  │  run-overnight.sh loop:                   │   │
│  │    for i in 1..N:                         │   │
│  │      timeout 60m claude -p martinprompt   │   │
│  │      git add -A && git commit             │   │
│  │                                           │   │
│  │  watchdog.sh:                             │   │
│  │    sleep until TIMEOUT_HOURS              │   │
│  │    git commit all work                    │   │
│  │    kill container                         │   │
│  └───────────────────────────────────────────┘   │
│                                                  │
│  extract-work.sh:                                │
│    git diff baseline..HEAD → patch file          │
│    docker cp experiments/ → host                 │
└─────────────────────────────────────────────────┘
```

### Safety Model

1. **Project files are read-only** — the container can't corrupt your source
2. **Workspace is a copy** — agent works on an isolated copy in a Docker volume
3. **Watchdog enforces timeout** — auto-saves and shuts down after N hours
4. **Git tracks everything** — every iteration auto-commits; nothing is lost
5. **Patch-based extraction** — you review changes before applying them
6. **Resource limits** — CPU and memory caps prevent runaway processes

### The martinprompt.md (Orchestrator Prompt)

This is the most important file. It tells Claude how to behave as an autonomous agent:

- **Startup procedure**: Read task, discover system, initialize state files
- **Per-iteration workflow**: Pick a TODO, execute, commit, update state
- **Experiment protocol**: Numbered experiment dirs with configs, logs, results
- **Reproducibility protocol**: Consolidate into `reproduce.py`
- **Decision guidelines**: Start simple, falsify results, pivot if stuck

The prompt is domain-agnostic. You customize behavior by editing `task.md`, not
the orchestrator prompt.

### State Files (The Agent's Memory)

The agent maintains persistent state across iterations through these files:

| File | Purpose | Who writes it |
|------|---------|---------------|
| `task.md` | What to accomplish | You (once) |
| `memory.md` | What the agent has learned | Agent (every iteration) |
| `todo.md` | What to do next | Agent (every iteration) |
| `progress.md` | What's been accomplished | Agent (every iteration) |
| `system.md` | Hardware/software inventory | Agent (once, refreshed if stale) |
| `reports/report_latest.md` | Scientific report | Agent (periodically) |

This is how the agent maintains continuity across context window resets.
Each Claude invocation reads these files first, does work, then updates them.

## Customization

### Adjusting the Container

**Resource limits** — edit `docker-compose.sandbox.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '16'       # More CPUs for parallel experiments
      memory: 32G      # More RAM for large datasets
```

**GPU passthrough** — add to compose:
```yaml
services:
  sandbox:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

And change the Dockerfile base to include CUDA:
```dockerfile
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
# ... then install python, node, etc.
```

**Custom dependencies** — add a `requirements.txt` to your project root.
The entrypoint auto-installs it on first start.

### Adjusting the Overnight Loop

```bash
# Fewer iterations, longer timeout per iteration:
docker exec -d my-sandbox gosu agent bash /workspace/sandbox/run-overnight.sh 10 120

# Many short iterations (good for incremental work):
docker exec -d my-sandbox gosu agent bash /workspace/sandbox/run-overnight.sh 50 30
```

### Adding Subagents

Create new `.claude/agents/agent-NAME.md` files. The orchestrator will discover
and use them. Keep agent definitions focused:

```markdown
# Agent: Data-Validator

Validates dataset integrity before training.

## Responsibilities
- Check for missing values
- Verify train/test split has no overlap
- Compute basic statistics
- Flag anomalies

## Tools
- Python for data analysis
- Read for loading data files
```

### Customizing for Non-ML Projects

The martinprompt works for any iterative development task, not just ML. Adjust:

1. Remove ML-specific language from martinprompt.md (training, epochs, GPU)
2. Change the experiment protocol to match your domain
3. Replace `reproduce.py` with whatever your primary deliverable is
4. Adjust agent definitions for your task type

## Troubleshooting

### Container won't start
```bash
# Check Docker is running
docker info

# Check for port conflicts or volume issues
docker compose -f sandbox/docker-compose.sandbox.yml logs
```

### Claude can't authenticate
The sandbox mounts `~/.claude` as read-only and copies credentials on start.
If you see auth errors:
```bash
# Verify credentials exist on host
ls -la ~/.claude/.credentials.json

# Re-authenticate on host first
claude auth login
```

### Agent is stuck / not making progress
```bash
# Check what it's doing
docker exec my-sandbox tail -50 /agent-logs/claude-output.log

# Check its state files
docker exec my-sandbox cat /workspace/todo.md
docker exec my-sandbox cat /workspace/memory.md

# Kill and restart the loop (auto-commits first)
docker exec my-sandbox pkill -f "claude"
sleep 5
docker exec -d my-sandbox gosu agent bash /workspace/sandbox/run-overnight.sh
```

### Extracting work from a stopped container
If the container stopped but volumes still exist:
```bash
# Restart the container (volumes persist!)
cd sandbox/ && docker compose -f docker-compose.sandbox.yml up -d
# Then extract normally
./extract-work.sh
```

### Cleaning up volumes (nuclear option)
```bash
# WARNING: This deletes all workspace data
docker compose -f docker-compose.sandbox.yml down -v
```

## Lessons Learned (from production use)

1. **martinprompt is everything** — spend time getting it right. The agent is only
   as good as its instructions. The most important sections are the startup procedure
   and decision-making guidelines.

2. **State files are the agent's brain** — `memory.md` is critical. A well-maintained
   memory file lets the agent pick up where it left off even after 30+ iterations.

3. **60-minute iteration timeout is the sweet spot** — too short and the agent can't
   finish experiments; too long and it burns context on one approach.

4. **Auto-commit after every iteration is essential** — without this, a crash or
   timeout loses all work from that iteration.

5. **Negative controls first** — the martinprompt emphasizes this for good reason.
   Without negative controls, the agent can convince itself (and you) that random
   noise is a real signal.

6. **Start the auto-backup** — `auto-backup.sh` saved us multiple times when we
   wanted to check intermediate results without stopping the agent.

7. **The agent improves over iterations** — early iterations explore and fail; later
   iterations build on `memory.md` and converge. 20-30 iterations overnight is typical.

8. **Review patches before applying** — `extract-work.sh` generates a patch file.
   Always review it (`less patches/sandbox_work_*.patch`) before applying.
