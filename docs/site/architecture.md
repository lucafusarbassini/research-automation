# Architecture

This page describes the system architecture, module relationships, and data flow within Research Automation.

---

## High-Level Architecture

```mermaid
graph TB
    User["User / Terminal"]
    CLI["cli/main.py<br/>Typer CLI"]
    Dashboard["cli/dashboard.py<br/>TUI Dashboard"]

    subgraph Core["Core Modules"]
        Agents["agents.py<br/>Orchestration"]
        Session["session.py<br/>Session Mgmt"]
        Tokens["tokens.py<br/>Budget Tracking"]
        Knowledge["knowledge.py<br/>Encyclopedia"]
        MCPs["mcps.py<br/>MCP Discovery"]
        Router["model_router.py<br/>Model Selection"]
        Security["security.py<br/>Secret Scanning"]
        Paper["paper.py<br/>LaTeX Pipeline"]
        Repro["reproducibility.py<br/>Run Logging"]
        Resources["resources.py<br/>Monitoring"]
        Notify["notifications.py<br/>Alerts"]
        Env["environment.py<br/>System Discovery"]
        Onboard["onboarding.py<br/>Project Init"]
        CrossRepo["cross_repo.py<br/>Multi-Repo"]
        Auto["autonomous.py<br/>Scheduled Tasks"]
    end

    Bridge["claude_flow.py<br/>Claude-Flow Bridge"]
    ClaudeFlow["claude-flow v3<br/>(optional)"]
    ClaudeCLI["Claude Code CLI"]
    Templates["templates/<br/>Project Scaffolding"]

    User --> CLI
    User --> Dashboard
    CLI --> Agents
    CLI --> Session
    CLI --> Onboard
    CLI --> Paper
    Agents --> Router
    Agents --> Tokens
    Agents --> Bridge
    Session --> Bridge
    Knowledge --> Bridge
    MCPs --> Bridge
    Security --> Bridge
    Resources --> Bridge
    CrossRepo --> Bridge
    Bridge --> ClaudeFlow
    Bridge -.->|fallback| ClaudeCLI
    Onboard --> Templates
    Agents --> ClaudeCLI
    Auto --> Agents
    Notify --> User
```

---

## Module Dependency Map

The following diagram shows which core modules depend on which:

```mermaid
graph LR
    CF["claude_flow.py"]

    agents --> CF
    session --> CF
    tokens --> CF
    knowledge --> CF
    mcps --> CF
    security --> CF
    resources --> CF
    cross_repo --> CF
    model_router --> CF

    agents --> tokens
    agents --> model_router

    paper -.-> knowledge
    reproducibility -.-> security

    autonomous --> agents
    onboarding -.-> environment
```

**Solid arrows** indicate direct imports. **Dashed arrows** indicate indirect or optional relationships.

### Key Observations

1. **`claude_flow.py` is the central integration point.** Nine modules import from it. Every module follows the same fallback pattern: try the bridge, catch `ClaudeFlowUnavailable`, fall back to a local implementation.

2. **`agents.py` is the primary orchestrator.** It uses `tokens.py` for budget checks and `model_router.py` for model selection before dispatching tasks.

3. **Domain-specific modules are isolated.** `paper.py`, `reproducibility.py`, `voice.py`, `style_transfer.py`, `meta_rules.py`, and `automation_utils.py` do not depend on the claude-flow bridge and operate independently.

4. **`onboarding.py` is entry-only.** It is called during `research init` and does not participate in ongoing session execution.

---

## Directory Structure

```
research-automation/
├── cli/                          # User-facing CLI
│   ├── main.py                   # Typer CLI: init, start, overnight, status, etc.
│   ├── dashboard.py              # Rich TUI dashboard
│   └── gallery.py                # Figure gallery viewer
│
├── core/                         # Business logic (20+ modules)
│   ├── agents.py                 # Agent types, routing, DAG execution
│   ├── session.py                # Session CRUD, snapshots
│   ├── tokens.py                 # Token estimation, budget checks
│   ├── knowledge.py              # Encyclopedia CRUD, vector search
│   ├── mcps.py                   # MCP tier loading, classification
│   ├── model_router.py           # Complexity classification, model selection
│   ├── security.py               # Secret scanning, immutable files
│   ├── paper.py                  # Figures, citations, LaTeX build
│   ├── reproducibility.py        # Run logs, artifact registry, hashing
│   ├── resources.py              # CPU/RAM/GPU monitoring, checkpoints
│   ├── notifications.py          # Slack, email, desktop alerts
│   ├── environment.py            # System discovery, conda management
│   ├── onboarding.py             # Interactive init questionnaire
│   ├── cross_repo.py             # Multi-repo linking, coordinated commits
│   ├── autonomous.py             # Scheduled routines, audit logging
│   ├── claude_flow.py            # Bridge to claude-flow v3
│   ├── style_transfer.py         # Writing style analysis, plagiarism check
│   ├── voice.py                  # Audio transcription
│   ├── meta_rules.py             # Rule extraction from conversations
│   ├── automation_utils.py       # Data helpers, experiment runners
│   ├── auto_debug.py             # Automatic error diagnosis
│   ├── browser.py                # Browser preview
│   ├── task_spooler.py           # Task queue management
│   └── verification.py           # Result verification
│
├── templates/                    # Copied into new projects
│   ├── config/                   # MCP config, settings template
│   │   └── mcp-nucleus.json      # 70+ MCPs in 8 tiers
│   ├── knowledge/                # GOAL.md, ENCYCLOPEDIA.md, CONSTRAINTS.md
│   └── paper/                    # main.tex, references.bib, Makefile
│
├── defaults/                     # Shared defaults (not copied into projects)
│   ├── PHILOSOPHY.md             # Core research principles
│   ├── LEGISLATION.md            # Non-negotiable rules
│   ├── CODE_STYLE.md             # Code style guide
│   ├── PROMPTS.md                # Default prompt collection
│   ├── MCP_NUCLEUS.json          # Master MCP catalog
│   └── ONBOARDING.md             # Onboarding question bank
│
├── docker/                       # Container setup
│   ├── Dockerfile                # Ubuntu 24.04 + full toolchain
│   ├── docker-compose.yml        # Volume mounts, resource limits
│   └── permissions.md            # Permission level documentation
│
├── scripts/                      # Shell scripts
│   ├── setup.sh                  # Initial setup
│   ├── setup_claude_flow.sh      # claude-flow installation
│   ├── overnight.sh              # Basic overnight runner
│   ├── overnight-enhanced.sh     # Enhanced overnight with recovery
│   └── interactive.sh            # Interactive session launcher
│
├── tests/                        # Test suite
├── docs/                         # Documentation
└── pyproject.toml                # Package metadata and dependencies
```

---

## Data Flow: Project Initialization

```mermaid
sequenceDiagram
    participant U as User
    participant CLI as cli/main.py
    participant OB as core/onboarding.py
    participant T as templates/
    participant G as Git

    U->>CLI: research init my-project
    CLI->>OB: collect_answers()
    OB->>U: Interactive questionnaire
    U->>OB: Goal, type, constraints
    OB->>CLI: OnboardingAnswers
    CLI->>T: Copy templates to my-project/
    CLI->>OB: write_goal_file()
    CLI->>OB: write_settings()
    CLI->>OB: setup_workspace()
    CLI->>G: git init && git add -A && git commit
    CLI->>U: Project created
```

---

## Data Flow: Task Execution

```mermaid
sequenceDiagram
    participant U as User
    participant M as Master Agent
    participant R as Model Router
    participant T as Token Budget
    participant S as Sub-Agent
    participant K as Knowledge
    participant P as Progress

    U->>M: "Implement a data loader"
    M->>R: classify_complexity()
    R-->>M: MEDIUM -> claude-sonnet
    M->>T: check_budget()
    T-->>M: can_proceed: true
    M->>S: Route to Coder agent
    S->>S: Execute task
    S->>K: append_learning("What Works", ...)
    S->>P: Update state/PROGRESS.md
    S-->>M: TaskResult
    M->>T: Update usage
    M-->>U: Result summary
```

---

## Data Flow: Overnight Mode

```mermaid
sequenceDiagram
    participant CLI as cli/main.py
    participant TODO as state/TODO.md
    participant CC as Claude Code CLI
    participant H as Hooks
    participant N as Notifications
    participant DONE as state/DONE

    CLI->>TODO: Read task list
    loop Each iteration
        CLI->>CC: Execute next task
        CC->>H: pre-task.sh
        CC->>CC: Process task
        CC->>H: post-task.sh (auto-commit)
        alt Error
            CC->>H: on-error.sh (snapshot + notify)
            H->>N: Send error notification
        end
        CLI->>DONE: Check for completion signal
    end
    CLI->>N: Send completion notification
```

---

## Claude-Flow Integration Pattern

Every module that integrates with claude-flow follows the same pattern:

```python
from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

def some_function(args):
    # Try claude-flow first
    try:
        bridge = _get_bridge()
        result = bridge.some_method(args)
        return adapt_result(result)
    except ClaudeFlowUnavailable:
        pass

    # Fall back to local implementation
    return local_implementation(args)
```

This ensures the system works identically with or without claude-flow installed. The bridge is a singleton (`_get_bridge()`) that checks for `npx` and `claude-flow@v3alpha` availability on first call.

### Agent Type Mapping

| Research Automation | claude-flow Equivalent |
|--------------------|-----------------------|
| MASTER | hierarchical-coordinator (queen) |
| RESEARCHER | researcher |
| CODER | coder |
| REVIEWER | code-reviewer |
| FALSIFIER | security-auditor |
| WRITER | api-docs |
| CLEANER | refactorer |

---

## Security Architecture

```mermaid
graph TB
    subgraph Permissions
        Safe["SAFE<br/>Read, write workspace,<br/>run Python, git ops"]
        Moderate["MODERATE<br/>Network requests,<br/>create directories"]
        Elevated["ELEVATED<br/>Delete files, modify config,<br/>push to remote"]
        Dangerous["DANGEROUS<br/>Sudo, modify secrets,<br/>spend money"]
    end

    subgraph Guards
        SecretScan["Secret Scanning<br/>(regex + claude-flow)"]
        Immutable["Immutable File<br/>Protection"]
        Audit["Audit Logging<br/>(state/audit.log)"]
        Confirm["Confirmation<br/>Gates"]
    end

    Safe --> SecretScan
    Moderate --> Audit
    Elevated --> Confirm
    Dangerous --> Confirm
    Immutable --> Safe
```

---

## MCP Tier Architecture

```mermaid
graph TB
    Task["Task Description"]
    Classify["classify_task()"]

    T0["Tier 0: claude-flow<br/>(if available)"]
    T1["Tier 1: Essential<br/>paper-search, arxiv, git,<br/>github, filesystem, memory"]
    T2["Tier 2: Data<br/>postgres, sqlite, duckdb, chroma"]
    T3["Tier 3: ML/DL<br/>jupyter, huggingface, mlflow"]
    T4["Tier 4: Math<br/>wolfram, sympy"]
    T5["Tier 5: Paper<br/>latex, overleaf"]
    T6["Tier 6: Comms<br/>slack, gmail, sendgrid"]
    T7["Tier 7: Cloud<br/>aws, docker, terraform"]
    T8["Tier 8: Startup<br/>vercel, gamma, stripe, notion"]

    Task --> Classify
    Classify --> T0
    Classify --> T1
    Classify -->|"database, sql"| T2
    Classify -->|"model, training"| T3
    Classify -->|"math, equation"| T4
    Classify -->|"paper, latex"| T5
    Classify -->|"notify, email"| T6
    Classify -->|"deploy, aws"| T7
    Classify -->|"website, slides"| T8
```

Tier 1 is always loaded. Other tiers activate when task keywords match their trigger words.
