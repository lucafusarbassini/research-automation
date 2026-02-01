# BOOTSTRAP: Scientific Research Automation System

## WHAT YOU ARE BUILDING

A comprehensive system for automating scientific research using Claude Code. This tool ships with sensible defaults and templates. Users provide project-specific inputs (goals, credentials, references) via an interactive onboarding wizard.

**Key Principle**: The tool does the setup work. Users provide minimal input.

---

## ARCHITECTURE OVERVIEW

```
research-automation/           # THIS TOOL (what you're building now)
├── cli/                       # CLI entry point (`research` command)
├── templates/                 # Templates copied into new projects
│   ├── .claude/               # Agent definitions, skills, hooks
│   ├── paper/                 # LaTeX template
│   ├── knowledge/             # Knowledge file templates
│   └── config/                # Default MCP config, conda.yml
├── defaults/                  # Default prompts, philosophy, code style
├── core/                      # Core Python modules
│   ├── session.py             # Session management
│   ├── agents.py              # Agent orchestration
│   ├── mcps.py                # MCP auto-discovery and loading
│   ├── tokens.py              # Token estimation and budgeting
│   ├── knowledge.py           # Encyclopedia updates
│   └── notifications.py       # Email/Slack notifications
├── docker/                    # Dockerfile, docker-compose templates
├── scripts/                   # Setup, overnight, interactive scripts
└── docs/                      # Documentation
```

When a user runs `ricetinit my-project`, the tool:
1. Runs interactive onboarding (asks for goal, credentials, preferences)
2. Creates project directory with templates
3. Sets up Docker container
4. Installs MCPs based on project type
5. Creates initial TODO.md

---

## Core Documents (Agents MUST Read)
1. `defaults/PHILOSOPHY.md` - High-level principles
2. `defaults/LEGISLATION.md` - Detailed working rules (NON-NEGOTIABLE)

## IMPLEMENTATION PHASES

Execute phases in order. Commit after each phase with message: `Phase N: <description>`.

---

### Phase 1: Safe Foundation (Docker)

Create the Docker setup that isolates all project work.

**Files to create:**

`docker/Dockerfile`:
```dockerfile
FROM ubuntu:24.04

# System packages
RUN apt-get update && apt-get install -y \
    python3.11 python3-pip python3.11-venv \
    nodejs npm \
    git curl wget \
    texlive-full biber latexmk \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Python packages
RUN pip3 install --break-system-packages \
    numpy pandas scipy scikit-learn \
    torch torchvision torchaudio \
    matplotlib seaborn plotly \
    jupyter notebook \
    chromadb sentence-transformers \
    tqdm rich typer \
    python-dotenv pyyaml

# Working directory
WORKDIR /workspace

# Entry point
ENTRYPOINT ["/bin/bash"]
```

`docker/docker-compose.yml`:
```yaml
version: '3.8'
services:
  research:
    build: .
    volumes:
      - ${PROJECT_PATH}:/workspace:rw          # Project files
      - ${REFERENCE_PATH}:/reference:ro        # Papers, code (read-only)
      - ${OUTPUTS_PATH}:/outputs:rw            # Deliverables
      - ${SECRETS_PATH}:/secrets:ro            # API keys (read-only)
      - ${SHARED_PATH}:/shared:rw              # Cross-project knowledge
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    networks:
      - research-net
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 32G

networks:
  research-net:
    driver: bridge
```

`docker/permissions.md`:
```markdown
# Permission Levels

## SAFE (auto-approve)
- Read any file in /workspace, /reference, /shared
- Write to /workspace, /outputs
- Run Python/bash in /workspace
- Git operations in /workspace
- Install pip/npm packages

## MODERATE (log, proceed)
- Network requests to allowlisted domains
- Create new directories
- Modify .claude/ files

## ELEVATED (ask user in interactive, proceed in overnight)
- Delete files
- Modify config files
- Install system packages
- Push to git remote

## DANGEROUS (always ask)
- Any sudo command
- Modify /secrets
- Network requests to non-allowlisted domains
- Spend money (cloud resources, APIs with cost)
- Send emails/notifications
```

**Commit**: `Phase 1: Docker foundation with permission levels`

---

### Phase 2: Repository Templates

Create the template files that get copied into every new project.

**Directory: `templates/.claude/`**

`templates/.claude/CLAUDE.md`:
```markdown
# Project Instructions

You are working on a scientific research project. Follow these protocols:

## Progressive Instruction Protocol

**Phase 1: ORIENT** (always first)
1. Read knowledge/GOAL.md
2. Read knowledge/CONSTRAINTS.md  
3. Read state/TODO.md
4. Summarize your understanding
5. Ask clarifying questions if needed

**Phase 2: EXPLORE**
1. Read relevant code/data
2. Build mental model
3. Propose approach (don't execute yet)

**Phase 3: PLAN**
1. Break into subtasks
2. Estimate difficulty/risk per subtask
3. Get approval (or auto-approve if SAFE)

**Phase 4: EXECUTE**
1. Execute one subtask at a time
2. Checkpoint after each
3. Validate results before proceeding

**Phase 5: VALIDATE**
1. Run falsifier checks
2. Compare to original goal
3. Document learnings in knowledge/ENCYCLOPEDIA.md

## Core Rules

1. **Never guess** - Search or ask when uncertain
2. **Test small first** - Downsample data, run 1 epoch, then scale
3. **Commit aggressively** - Meaningful commits after each subtask
4. **Be verbose** - Log extensively for self-diagnosis
5. **Update knowledge** - Every task should potentially update ENCYCLOPEDIA.md
6. **Don't please** - Be objective, challenge assumptions, report flaws

## Token Awareness

- Estimate tokens before expensive operations (~4 chars/token)
- Warn at 50%, 75%, 90% of session budget
- Use cheap operations where possible (local LLMs for simple tasks)

## Thinking Mode Selection

Automatically select based on task:
- SIMPLE (formatting, lookups): No extended thinking
- MEDIUM (code writing, analysis): Standard thinking
- COMPLEX (debugging, architecture): Extended thinking (3% budget)
- CRITICAL (validation, paper writing): Maximum thinking budget
```

**Directory: `templates/.claude/agents/`**

Create these agent files (I'll show key ones, create all 7):

`templates/.claude/agents/master.md`:
```markdown
# Master Agent

You are the orchestrator. You NEVER execute tasks directly.

## Responsibilities
- Parse user requests
- Route to appropriate sub-agent
- Monitor progress across all sub-agents
- Merge results
- Manage token budget distribution

## Routing Rules

| Task Type | Route To |
|-----------|----------|
| Literature review, paper search | researcher |
| Write/modify code | coder |
| Review code, suggest improvements | reviewer |
| Attack results, find flaws | falsifier |
| Write paper sections, docs | writer |
| Refactor, optimize, document | cleaner |

## Budget Allocation

Default split for complex tasks:
- researcher: 15%
- coder: 35%
- reviewer: 10%
- falsifier: 20%
- writer: 15%
- cleaner: 5%

Adjust based on task requirements.

## Communication

After each sub-agent completes:
1. Log result to state/PROGRESS.md
2. Check if goal is achieved
3. If not, determine next action
4. Route to next sub-agent or report completion
```

`templates/.claude/agents/falsifier.md`:
```markdown
# Falsifier Agent (Popperian)

You are the adversary. Your job is to DESTROY results, not validate them.

## Mission
Find every possible way the results could be wrong, misleading, or invalid.

## Attack Vectors

### Data Leakage
- [ ] Is there train/test contamination?
- [ ] Are there features that encode the target?
- [ ] Is future information leaking into past predictions?

### Statistical Validity
- [ ] Are sample sizes sufficient?
- [ ] Are confidence intervals appropriate?
- [ ] Is there p-hacking or multiple comparisons issue?
- [ ] Are effect sizes meaningful, not just significant?

### Code Correctness
- [ ] Edge cases handled?
- [ ] Boundary conditions tested?
- [ ] Error handling appropriate?
- [ ] Random seeds set for reproducibility?

### Methodology
- [ ] Are baselines appropriate?
- [ ] Are comparisons fair?
- [ ] Are metrics appropriate for the task?
- [ ] Could confounders explain results?

### Reproducibility
- [ ] Can results be reproduced from scratch?
- [ ] Are all dependencies pinned?
- [ ] Is the environment fully specified?

## Output Format

```markdown
## Falsification Report

### Critical Issues (must fix)
1. [Issue]: [Explanation]
   - Severity: CRITICAL
   - Evidence: [What you found]
   - Fix: [Suggested fix]

### Warnings (should investigate)
...

### Passed Checks
...

### Overall Assessment
[PASS / FAIL / NEEDS_REVIEW]
```

## Attitude

Be ruthless but constructive. Your job is to help, but help by finding problems BEFORE they become embarrassing. Channel your inner Reviewer 2.
```

`templates/.claude/agents/coder.md`:
```markdown
# Coder Agent

You write and modify code.

## Constraints

1. **Always test before commit**
   - Run on small data first
   - Verify output makes sense
   - Check for errors/warnings

2. **Code quality**
   - Type hints always
   - Docstrings (Google style)
   - Vectorize over loops
   - No magic numbers
   - Meaningful variable names

3. **Structure**
   - Functions < 50 lines
   - Single responsibility
   - Clear input/output types

4. **Before writing code**
   - Check if similar code exists in workspace/
   - Check reference/ for reusable snippets
   - Search web for existing solutions

## Output

Always provide:
1. The code
2. How to run it
3. Expected output
4. What to check to verify correctness
```

`templates/.claude/agents/researcher.md`:
```markdown
# Researcher Agent

You find and synthesize scientific literature.

## Tools
- paper-search-mcp (arXiv, PubMed, bioRxiv, Semantic Scholar)
- semantic-scholar-mcp (citations, author search)
- web search (for recent work not yet indexed)

## Process

1. **Search broadly** - Multiple databases, various query formulations
2. **Filter ruthlessly** - Focus on highly cited, recent, or directly relevant
3. **Extract key info**:
   - Main contribution
   - Methods used
   - Key results
   - Limitations noted
   - How it relates to our work

4. **Synthesize** - Don't just list papers, identify themes and gaps

## Output Format

```markdown
## Literature Review: [Topic]

### Key Papers
1. [Author et al., Year] - [Title]
   - Main idea: ...
   - Relevance: ...
   - BibTeX key: ...

### Themes
- Theme 1: ...
- Theme 2: ...

### Gaps / Opportunities
- ...

### Recommended Next Steps
- ...
```

## Citation Management
- Always provide BibTeX entries
- Add to paper/references.bib
- Use consistent citation keys: [FirstAuthorYear]
```

Create similar files for: `reviewer.md`, `writer.md`, `cleaner.md`

**Directory: `templates/.claude/skills/`**

`templates/.claude/skills/paper-writing.md`:
```markdown
# Paper Writing Skill

## Structure (Nature-style)
1. Title (< 15 words, specific, no jargon)
2. Abstract (150-250 words, standalone)
3. Introduction (problem → gap → contribution)
4. Results (findings with figures)
5. Discussion (interpretation, limitations, implications)
6. Methods (reproducible detail)

## Style Rules
- Active voice preferred
- Past tense for methods/results
- Present tense for established facts and discussion
- Avoid: "very", "really", "it is interesting that"
- One idea per paragraph
- First sentence = topic sentence

## Figure References
- Every figure must be referenced in text
- Reference before the figure appears
- "Figure 1 shows..." not "As shown in Figure 1..."

## Citations
- Use [Author, Year] format in text
- All citations must have BibTeX entry
- Prefer primary sources over reviews
- Include DOI when available
```

`templates/.claude/skills/figure-making.md`:
```markdown
# Figure Making Skill

## Technical Requirements
- Format: PDF (vector where possible)
- DPI: 300 for raster elements
- Font: Arial or Helvetica, 8-10pt
- Line width: 0.5-1.5pt
- Colors: Colorblind-friendly palette

## rcParams Template
```python
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.figsize': (3.5, 2.5),  # Single column
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.format': 'pdf',
    'savefig.bbox': 'tight',
    'axes.linewidth': 0.8,
    'lines.linewidth': 1.0,
    'axes.spines.top': False,
    'axes.spines.right': False,
})
```

## Colorblind-Safe Palette
```python
COLORS = {
    'blue': '#0077BB',
    'orange': '#EE7733', 
    'green': '#009988',
    'red': '#CC3311',
    'purple': '#AA3377',
    'grey': '#BBBBBB',
}
```

## Sizing
- Single column: 3.5 inches wide
- Double column: 7 inches wide
- Aspect ratio: 4:3 or 16:9

## Export
```python
fig.savefig('figures/fig1.pdf', 
            bbox_inches='tight',
            pad_inches=0.02,
            dpi=300)
```
```

`templates/.claude/skills/code-style.md`:
```markdown
# Code Style Guide

## Python

### Formatting
- Black formatter (line length 88)
- isort for imports
- Type hints on all functions

### Imports Order
1. Standard library
2. Third-party
3. Local

### Naming
- snake_case for functions, variables
- PascalCase for classes
- UPPER_CASE for constants
- Descriptive names (no single letters except i,j,k for indices)

### Functions
```python
def process_data(
    input_path: Path,
    output_path: Path,
    *,
    batch_size: int = 32,
    verbose: bool = False,
) -> pd.DataFrame:
    """Process raw data and save results.
    
    Args:
        input_path: Path to input CSV file.
        output_path: Path to save processed data.
        batch_size: Number of samples per batch.
        verbose: Whether to print progress.
    
    Returns:
        DataFrame with processed results.
    
    Raises:
        FileNotFoundError: If input_path doesn't exist.
    """
    ...
```

### Patterns
- Prefer composition over inheritance
- Use dataclasses for data containers
- Use pathlib.Path over os.path
- Use f-strings over .format()
- Vectorize with numpy/pandas, avoid loops

### Don'ts
- No global mutable state
- No wildcard imports
- No bare except clauses
- No print() in library code (use logging)
```

**Directory: `templates/.claude/hooks/`**

`templates/.claude/hooks/pre-task.sh`:
```bash
#!/bin/bash
# Runs before each task

echo "$(date -Iseconds) | TASK_START | $TASK_NAME" >> state/sessions/current.log

# Check disk space
DISK_FREE=$(df -h /workspace | tail -1 | awk '{print $4}')
echo "Disk free: $DISK_FREE"

# Load relevant knowledge
if [ -f "knowledge/ENCYCLOPEDIA.md" ]; then
    echo "Encyclopedia loaded ($(wc -l < knowledge/ENCYCLOPEDIA.md) lines)"
fi
```

`templates/.claude/hooks/post-task.sh`:
```bash
#!/bin/bash
# Runs after each task

echo "$(date -Iseconds) | TASK_END | $TASK_NAME | $TASK_STATUS" >> state/sessions/current.log

# Auto-commit if changes
if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "Auto-commit after: $TASK_NAME"
fi

# Update progress
echo "- [x] $TASK_NAME ($(date +%H:%M))" >> state/PROGRESS.md
```

`templates/.claude/hooks/on-error.sh`:
```bash
#!/bin/bash
# Runs on task error

echo "$(date -Iseconds) | ERROR | $TASK_NAME | $ERROR_MSG" >> state/sessions/current.log

# Save state for debugging
cp -r state/ state/backup_$(date +%Y%m%d_%H%M%S)/

# Notify if configured
if [ -n "$NOTIFICATION_WEBHOOK" ]; then
    curl -X POST "$NOTIFICATION_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"Error in $PROJECT_NAME: $ERROR_MSG\"}"
fi
```

**Directory: `templates/knowledge/`**

`templates/knowledge/ENCYCLOPEDIA.md`:
```markdown
# Project Encyclopedia

This file is auto-updated with learnings. Do not edit manually.

## Environment
- Conda environment: (set during init)
- Python version: (set during init)
- Key packages: (set during init)

## Machines
- Local: (set during init)
- Remote: (user provides)

## Tricks
<!-- Learnings get appended here -->

## Decisions
<!-- Design decisions get logged here -->

## What Works
<!-- Successful approaches -->

## What Doesn't Work
<!-- Failed approaches (to avoid repeating) -->
```

`templates/knowledge/GOAL.md`:
```markdown
# Project Goal

## One-Liner
<!-- User provides during init -->

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Constraints
- Timeline: 
- Compute budget:
- Must use:
- Must NOT:

## First Task
<!-- What to work on first -->
```

**Directory: `templates/paper/`**

`templates/paper/main.tex`:
```latex
\documentclass[11pt,a4paper]{article}

% Packages
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue]{hyperref}
\usepackage{natbib}
\usepackage{booktabs}
\usepackage{microtype}

% Title
\title{[Title]}
\author{[Authors]}
\date{\today}

\begin{document}

\maketitle

\begin{abstract}
[Abstract goes here - 150-250 words]
\end{abstract}

\section{Introduction}
\label{sec:intro}

\section{Methods}
\label{sec:methods}

\section{Results}
\label{sec:results}

\section{Discussion}
\label{sec:discussion}

\section{Conclusion}
\label{sec:conclusion}

\bibliographystyle{plainnat}
\bibliography{references}

\end{document}
```

`templates/paper/Makefile`:
```makefile
MAIN = main
LATEX = pdflatex
BIBTEX = biber

.PHONY: all clean watch

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex references.bib
	$(LATEX) $(MAIN)
	$(BIBTEX) $(MAIN)
	$(LATEX) $(MAIN)
	$(LATEX) $(MAIN)

clean:
	rm -f *.aux *.bbl *.bcf *.blg *.log *.out *.run.xml *.toc

watch:
	while true; do \
		inotifywait -e modify $(MAIN).tex references.bib figures/*.pdf; \
		make all; \
	done
```

`templates/paper/references.bib`:
```bibtex
% Bibliography file
% Add entries in format:
% @article{AuthorYear,
%   author = {},
%   title = {},
%   journal = {},
%   year = {},
%   doi = {},
% }
```

**Commit**: `Phase 2: Repository templates (agents, skills, hooks, paper)`

---

### Phase 3: MCP Infrastructure

**File: `templates/config/mcp-nucleus.json`**

```json
{
  "tier1_essential": {
    "description": "Always loaded at project init",
    "mcps": {
      "paper-search-mcp": {
        "source": "openags/paper-search-mcp",
        "purpose": "arXiv, PubMed, bioRxiv, Semantic Scholar search"
      },
      "arxiv-mcp-server": {
        "source": "blazickjp/arxiv-mcp-server", 
        "purpose": "Deep arXiv integration"
      },
      "git": {
        "source": "modelcontextprotocol/servers",
        "purpose": "Git operations"
      },
      "github": {
        "source": "modelcontextprotocol/servers",
        "purpose": "GitHub PRs, issues, Actions"
      },
      "filesystem": {
        "source": "modelcontextprotocol/servers",
        "purpose": "File operations"
      },
      "memory": {
        "source": "modelcontextprotocol/servers",
        "purpose": "Knowledge persistence"
      },
      "sequential-thinking": {
        "source": "modelcontextprotocol/servers",
        "purpose": "Chain-of-thought reasoning"
      },
      "fetch": {
        "source": "modelcontextprotocol/servers",
        "purpose": "Web content retrieval"
      }
    }
  },
  "tier2_data": {
    "description": "Loaded when data tasks detected",
    "trigger_keywords": ["database", "sql", "query", "data", "table"],
    "mcps": {
      "postgres": {"source": "modelcontextprotocol/servers-archived"},
      "sqlite": {"source": "modelcontextprotocol/servers-archived"},
      "duckdb-mcp": {"source": "community"},
      "chroma-mcp": {"source": "chroma-core/chroma-mcp"}
    }
  },
  "tier3_ml": {
    "description": "Loaded for ML/DL tasks",
    "trigger_keywords": ["model", "training", "neural", "deep learning", "huggingface"],
    "mcps": {
      "jupyter-mcp-server": {"source": "datalayer/jupyter-mcp-server"},
      "huggingface-mcp": {"source": "shreyaskarnik/huggingface-mcp"},
      "mlflow-mcp": {"source": "mlflow/mlflow"},
      "wandb-mcp": {"source": "community"}
    }
  },
  "tier4_math": {
    "description": "Loaded for math/computation tasks",
    "trigger_keywords": ["math", "equation", "derivative", "integral", "symbolic"],
    "mcps": {
      "wolfram-mcp": {"source": "paraporoco/wolfram-mcp"},
      "sympy-mcp": {"source": "community"}
    }
  },
  "tier5_paper": {
    "description": "Loaded for paper writing",
    "trigger_keywords": ["paper", "latex", "write", "manuscript", "publication"],
    "mcps": {
      "latex-mcp-server": {"source": "Yeok-c/latex-mcp-server"},
      "overleaf-mcp": {"source": "mjyoo2/overleaf-mcp"}
    }
  },
  "tier6_communication": {
    "description": "Loaded for notifications/comms",
    "trigger_keywords": ["notify", "email", "slack", "message"],
    "mcps": {
      "slack-mcp": {"source": "modelcontextprotocol/servers-archived"},
      "gmail-mcp": {"source": "community"},
      "sendgrid-mcp": {"source": "community"}
    }
  },
  "tier7_cloud": {
    "description": "Loaded for cloud/infra tasks",
    "trigger_keywords": ["deploy", "aws", "cloud", "server", "docker"],
    "mcps": {
      "aws-mcp": {"source": "awslabs/mcp"},
      "docker-mcp": {"source": "community"},
      "terraform-mcp-server": {"source": "hashicorp/terraform-mcp-server"}
    }
  },
  "tier8_startup": {
    "description": "Loaded for outreach/website tasks",
    "trigger_keywords": ["website", "slides", "presentation", "marketing"],
    "mcps": {
      "vercel-mcp": {"source": "community"},
      "gamma-mcp": {"source": "community"},
      "stripe-mcp": {"source": "community"},
      "notion-mcp": {"source": "notion-community/notion-mcp"}
    }
  }
}
```

**File: `core/mcps.py`**

```python
"""MCP auto-discovery and loading based on task classification."""

import json
import re
from pathlib import Path
from typing import Set

MCP_CONFIG = Path(__file__).parent.parent / "templates/config/mcp-nucleus.json"


def load_mcp_config() -> dict:
    """Load MCP configuration."""
    with open(MCP_CONFIG) as f:
        return json.load(f)


def classify_task(task_description: str) -> Set[str]:
    """Determine which MCP tiers to load based on task keywords."""
    config = load_mcp_config()
    task_lower = task_description.lower()
    
    tiers_to_load = {"tier1_essential"}  # Always load tier 1
    
    for tier_name, tier_config in config.items():
        if tier_name == "tier1_essential":
            continue
        keywords = tier_config.get("trigger_keywords", [])
        if any(kw in task_lower for kw in keywords):
            tiers_to_load.add(tier_name)
    
    return tiers_to_load


def get_mcps_for_task(task_description: str) -> dict:
    """Get all MCPs needed for a task."""
    config = load_mcp_config()
    tiers = classify_task(task_description)
    
    mcps = {}
    for tier in tiers:
        tier_mcps = config.get(tier, {}).get("mcps", {})
        mcps.update(tier_mcps)
    
    return mcps


def install_mcp(mcp_name: str, source: str) -> bool:
    """Install an MCP from source."""
    # Implementation depends on MCP type
    # Most are npm packages or Python packages
    import subprocess
    
    if "github.com" in source or "/" in source:
        # GitHub source
        cmd = f"npx -y @anthropic-ai/mcp-installer install {source}"
    else:
        # npm package
        cmd = f"npm install -g {source}"
    
    try:
        subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False
```

**Commit**: `Phase 3: MCP infrastructure with auto-discovery`

---

### Phase 4: CLI and Session Management

**File: `cli/main.py`**

```python
#!/usr/bin/env python3
"""Research automation CLI."""

import typer
from pathlib import Path
from rich.console import Console
from datetime import datetime
import json
import shutil

app = typer.Typer(help="Scientific Research Automation")
console = Console()

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
CONFIG_DIR = Path.home() / ".research-automation"


@app.command()
def init(
    project_name: str,
    path: Path = typer.Option(Path.cwd(), help="Where to create project"),
):
    """Initialize a new research project."""
    project_path = path / project_name
    
    if project_path.exists():
        console.print(f"[red]Error: {project_path} already exists[/red]")
        raise typer.Exit(1)
    
    console.print(f"[bold]Creating project: {project_name}[/bold]")
    
    # Interactive onboarding
    console.print("\n[bold cyan]Project Setup[/bold cyan]")
    
    goal = typer.prompt("What is the main goal of this project?")
    
    project_type = typer.prompt(
        "Project type",
        type=typer.Choice(["ml-research", "data-analysis", "paper-writing", "general"]),
        default="ml-research"
    )
    
    # Copy templates
    shutil.copytree(TEMPLATE_DIR, project_path)
    
    # Customize GOAL.md
    goal_file = project_path / "knowledge" / "GOAL.md"
    goal_content = goal_file.read_text()
    goal_content = goal_content.replace("<!-- User provides during init -->", goal)
    goal_file.write_text(goal_content)
    
    # Initialize git
    import subprocess
    subprocess.run(["git", "init"], cwd=project_path)
    subprocess.run(["git", "add", "-A"], cwd=project_path)
    subprocess.run(["git", "commit", "-m", "Initial project setup"], cwd=project_path)
    
    console.print(f"\n[green]✓ Project created at {project_path}[/green]")
    console.print("\nNext steps:")
    console.print(f"  cd {project_path}")
    console.print("  research start")


@app.command()
def start(
    session_name: str = typer.Option(None, help="Name for this session"),
):
    """Start an interactive research session."""
    if session_name is None:
        session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    session_dir = Path("state/sessions")
    session_dir.mkdir(parents=True, exist_ok=True)
    
    session_file = session_dir / f"{session_name}.json"
    session_data = {
        "name": session_name,
        "started": datetime.now().isoformat(),
        "status": "active",
        "token_estimate": 0,
    }
    session_file.write_text(json.dumps(session_data, indent=2))
    
    console.print(f"[green]Session started: {session_name}[/green]")
    
    # Launch Claude Code
    import subprocess
    subprocess.run(["claude", "--session-id", session_name])


@app.command()
def overnight(
    task_file: Path = typer.Option(Path("state/TODO.md"), help="Task file to execute"),
    iterations: int = typer.Option(20, help="Max iterations"),
):
    """Run overnight autonomous mode."""
    console.print(f"[bold yellow]Starting overnight mode[/bold yellow]")
    console.print(f"Task file: {task_file}")
    console.print(f"Max iterations: {iterations}")
    
    if not task_file.exists():
        console.print(f"[red]Error: {task_file} not found[/red]")
        raise typer.Exit(1)
    
    import subprocess
    
    for i in range(iterations):
        console.print(f"\n[cyan]Iteration {i+1}/{iterations}[/cyan]")
        
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", f"$(cat {task_file})"],
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            console.print(f"[red]Error in iteration {i+1}[/red]")
            console.print(result.stderr)
            # Could add auto-debug loop here
        
        # Check for completion signal
        if Path("state/DONE").exists():
            console.print("[green]Task completed![/green]")
            break
    
    console.print("[bold]Overnight mode finished[/bold]")


@app.command()
def status():
    """Show current project status."""
    # Read TODO.md
    if Path("state/TODO.md").exists():
        console.print("[bold]TODO:[/bold]")
        console.print(Path("state/TODO.md").read_text()[:500])
    
    # Read PROGRESS.md
    if Path("state/PROGRESS.md").exists():
        console.print("\n[bold]Progress:[/bold]")
        console.print(Path("state/PROGRESS.md").read_text()[-500:])


@app.command()
def list_sessions():
    """List all sessions."""
    session_dir = Path("state/sessions")
    if not session_dir.exists():
        console.print("No sessions found")
        return
    
    for f in sorted(session_dir.glob("*.json")):
        data = json.loads(f.read_text())
        console.print(f"  {data['name']} - {data['status']} ({data['started'][:10]})")


if __name__ == "__main__":
    app()
```

**File: `core/tokens.py`**

```python
"""Token estimation and budget tracking."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenBudget:
    session_limit: int = 100_000  # Tokens per session
    daily_limit: int = 500_000    # Tokens per day
    current_session: int = 0
    current_daily: int = 0


def estimate_tokens(text: str) -> int:
    """Estimate token count (~4 chars per token)."""
    return len(text) // 4


def check_budget(budget: TokenBudget, estimated_cost: int) -> dict:
    """Check if operation is within budget."""
    session_remaining = budget.session_limit - budget.current_session
    daily_remaining = budget.daily_limit - budget.current_daily
    
    return {
        "can_proceed": estimated_cost < min(session_remaining, daily_remaining),
        "session_used_pct": (budget.current_session / budget.session_limit) * 100,
        "daily_used_pct": (budget.current_daily / budget.daily_limit) * 100,
        "warning": budget.current_session > budget.session_limit * 0.75,
    }


def select_thinking_mode(task_description: str) -> str:
    """Auto-select thinking mode based on task complexity."""
    task_lower = task_description.lower()
    
    # CRITICAL tasks
    critical_keywords = ["validate", "prove", "paper", "publish", "final", "submit"]
    if any(kw in task_lower for kw in critical_keywords):
        return "ultrathink"  # Max budget
    
    # COMPLEX tasks
    complex_keywords = ["debug", "design", "architecture", "research", "why", "investigate"]
    if any(kw in task_lower for kw in complex_keywords):
        return "extended"  # 3% budget
    
    # SIMPLE tasks
    simple_keywords = ["format", "list", "show", "what is", "lookup", "find"]
    if any(kw in task_lower for kw in simple_keywords):
        return "none"  # No extended thinking
    
    # Default to MEDIUM
    return "standard"
```

**Commit**: `Phase 4: CLI and session management`

---

### Phase 5-13: Continue Implementation

For brevity, I'll outline remaining phases. Execute each with similar detail:

**Phase 5: Knowledge System**
- `core/knowledge.py` - ENCYCLOPEDIA auto-update
- Chroma integration for RAG on prompts/skills
- Cross-project sync mechanism

**Phase 6: Hooks & Lifecycle**  
- Shell scripts in `scripts/`
- Progress tracking with rich/tqdm
- State snapshots for recovery

**Phase 7: Agent Orchestration**
- `core/agents.py` - Task routing
- Supervisor pattern (agent-as-user)
- Common observation space

**Phase 8: Overnight Mode**
- Enhanced `overnight.sh` with auto-debug
- Resource monitoring
- Recovery mechanisms

**Phase 9: Interactive Mode**
- TUI dashboard (textual/rich)
- Voice input (whisper-cpp integration)
- Browser preview

**Phase 10: Paper Pipeline**
- Figure generation with rcParams
- Citation management
- Code cleaning with test validation

**Phase 11: Notifications**
- Email/Slack/desktop
- Throttling logic
- Templates

**Phase 12: Testing**
- pytest suite
- Integration tests
- Safety tests

**Phase 13: Polish**
- Documentation
- Onboarding wizard improvements
- Performance optimization

---

## PHILOSOPHY (Baked Into Tool)

Read `defaults/PHILOSOPHY.md` for the complete philosophy that guides all agents.

---

## BEGIN

Start with Phase 1. Create the Docker files first. 

After each phase:
1. Test that it works
2. Commit with message `Phase N: <description>`
3. Move to next phase

Ask only if you hit a blocker you cannot resolve.
