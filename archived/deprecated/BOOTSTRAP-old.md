# BOOTSTRAP: Scientific Research Automation System

## CONTEXT

This project was designed in a conversation with Claude (webchat). The full design is below.
Your job is to implement it, phase by phase, starting with Phase 1 (Safe Foundation).

## WHAT YOU ARE BUILDING

A comprehensive system for automating scientific research using Claude Code, featuring:
- Docker containerization for safety
- 70+ MCP integrations (+ auto-discovery of more MCPs based on task)
- Multi-agent orchestration (master + specialized sub-agents)
- Overnight autonomous mode + interactive mode
- Knowledge accumulation (encyclopedia that grows)
- Paper writing pipeline with LaTeX
- Voice input, notifications, startup/outreach tools

## IMPLEMENTATION PHASES

Execute these in order. After each phase, commit and briefly report completion.

### Phase 1: Safe Foundation
- Create Dockerfile (Ubuntu 24.04, Python 3.11+, Node 20+, LaTeX, Claude Code CLI)
- Create docker-compose.yml with volume mounts:
  - /workspace (rw), /reference (ro), /outputs (w), /secrets (ro), /shared (rw)
- Create permission system (SAFE/MODERATE/ELEVATED/DANGEROUS levels)
- Create .secrets.example template
- Network isolation with allowlist

### Phase 2: Repository Skeleton
Create the full directory structure:
```
.claude/
  CLAUDE.md              # Master instructions (progressive instruction protocol)
  agents/                # master.md, researcher.md, coder.md, reviewer.md, falsifier.md, writer.md, cleaner.md
  skills/                # paper-writing.md, figure-making.md, code-style.md
  prompts/               # Prompt collection for RAG
  hooks/                 # pre-task.sh, post-task.sh, pre-commit.sh, on-error.sh
knowledge/
  ENCYCLOPEDIA.md        # Accumulated learnings (auto-updated)
  TRICKS.md, ENV.md, MACHINES.md, DECISIONS.md
state/
  GOAL.md, TODO.md, PROGRESS.md, BLOCKERS.md
  sessions/              # Session logs
reference/               # papers/, code/, examples/ (read-only)
workspace/               # experiments/, clean/
paper/                   # main.tex, references.bib, figures/, Makefile
outputs/                 # figures/, tables/, reports/
scripts/                 # setup.sh, run.sh, overnight.sh, interactive.sh
config/                  # mcp.json, conda.yml, docker-compose.yml, settings.yml
.github/workflows/       # ci.yml, auto-clean.yml, paper-build.yml
```

### Phase 3: MCP Infrastructure
- Create comprehensive config/mcp.json with all 70+ MCPs organized by tier
- Create scripts/install-mcps.sh
- Tier 1 (always): paper-search, arxiv, git, github, filesystem, memory, sequential-thinking
- Tier 2-7: loaded on demand based on task classification

### Phase 4: Session & Execution Management
- Create `research` CLI wrapper (init, start, resume, list, status, overnight, stop)
- Implement thinking mode auto-selection (SIMPLE→no thinking, COMPLEX→extended, CRITICAL→ultrathink)
- Implement background execution with job management
- Token estimation and budget tracking

### Phase 5: Knowledge System
- Define ENCYCLOPEDIA.md schema with auto-update protocol
- Create prompt collection RAG system using Chroma
- Create skill/cheat sheet auto-loading

### Phase 6: Hooks & Lifecycle
- Implement all hooks with proper logging
- Progress tracking with tqdm-style output

### Phase 7: Agent Orchestration
- Implement master agent task routing
- Implement supervisor (agent-as-user) pattern with goal-checker
- Implement falsifier agent with data leakage detection, statistical validity checks

### Phase 8: Overnight Mode
- Create overnight.sh loop
- Auto-debug loop (max iterations before escalate)
- Resource monitoring and cleanup triggers

### Phase 9: Interactive Mode
- Terminal dashboard (TUI) with panels
- Voice input pipeline (Whisper)
- Browser integration for visual preview

### Phase 10: Paper Pipeline
- LaTeX structure with Makefile
- Figure generation with rcParams
- Citation management with PubMed MCP
- Code cleaning pipeline (test before/after)

### Phase 11: Notifications
- Email, Slack, desktop notifications
- Throttling (max 2 emails/hour)
- Startup/outreach MCP configuration

### Phase 12-13: Testing & Polish
- Unit, integration, safety tests
- Documentation
- UX improvements

## KEY DESIGN PRINCIPLES

1. **Progressive instructions**: Don't load everything at once. Orient → Explore → Plan → Execute → Validate
2. **Safety first**: Docker isolation, permission levels, no system modifications without approval
3. **Learn continuously**: Every task should potentially update ENCYCLOPEDIA.md
4. **Test small first**: Always run code on downsampled data before scaling
5. **Frequent commits**: Aggressive git commits with meaningful messages
6. **Token awareness**: Estimate and track token usage, warn before limits
7. **Human out of loop**: Once safe foundation is set, minimize human intervention
8. **Falsification**: Actively try to break results (Popperian approach)

## SPECIAL INSTRUCTIONS

- Use `--dangerously-skip-permissions` only for overnight mode after safety review
- When uncertain, search the web rather than guess
- Be extremely verbose in logs (helps both self-diagnosis and user visibility)
- After completing each phase, update PROGRESS.md and commit

## BEGIN

Start with Phase 1. Create the Dockerfile first. Ask me if you need any credentials or clarifications, otherwise proceed autonomously.




## COMPREHENSIVE IMPLEMENTATION PLAN
Scientific Research Automation System

PHASE 0: HUMAN INPUT COLLECTION
Goal: Gather everything Claude needs to build autonomously. You provide, Claude organizes.
0.1 Core Identity & Rules (You Provide)
ItemDescriptionFormatProject philosophyYour vision for how agents should behaveFree-form text"Don't please me" rulesSpecific instructions for objective, grounded responsesBullet listScientific rigor standardsWhat constitutes valid results, acceptable shortcutsStructured docPopperian falsification rulesHow agents should attack their own resultsChecklistCode style preferencesVectorization, comments, naming, structureStyle guideFigure/plot standardsrcParams, rasterization rules, PDF export, color schemesExamples + rulesPaper writing rulesStructure, tone, citation style, LaTeX conventionsDetailed guidePersonal workflow preferencesWhen to interrupt you, notification preferences, work hoursConfig
0.2 Reference Materials (You Upload)
ItemPurposeReference papersStyle inpainting, methodology templatesExisting code to recycleFunctions, patterns agent can reuseLaTeX templateYour preferred paper structurePrompt collectionPrompts that work well (for RAG)Example good figuresVisual standardsExample good codeWhat clean looks likeWriting samplesYour voice/style for papers
0.3 Credentials & Access (You Provide Securely)
CredentialPurposeAnthropic API keyClaude API (if needed beyond Pro)GitHub tokenRepo management, ActionsHuggingFace tokenModel/dataset accessSemantic Scholar API keyEnhanced paper searchGoogle Cloud credentialsDrive, Calendar, BigQuerySlack tokenNotificationsEmail credentialsSendGrid/Gmail for notificationsSSH keysRemote machine accessConda/mamba pathEnvironment managementHetzner API keyServer provisioning (optional)Namecheap API keyDomain purchase (optional)Stripe keysPayments (optional)W&B / MLflow credentialsExperiment tracking
0.4 Infrastructure Info (You Provide)
ItemDescriptionRemote machinesSSH addresses, usernames, pathsData locationsWhere large datasets liveGPU resourcesAvailable computeStorage limitsDisk quotasNetwork restrictionsFirewall, proxy info

PHASE 1: SAFE FOUNDATION
Goal: Establish safety boundaries before any autonomous work.
1.1 Docker Container Architecture
Tasks:
├── Create base Dockerfile with:
│   ├── Ubuntu 24.04 LTS
│   ├── Python 3.11+ with uv
│   ├── Node.js 20+ with npm
│   ├── LaTeX full distribution
│   ├── Git, rsync, curl, jq
│   ├── Whisper.cpp (voice)
│   ├── Claude Code CLI
│   └── MCP runtime dependencies
├── Define volume mounts:
│   ├── /workspace (read-write, project files)
│   ├── /reference (read-only, papers & code)
│   ├── /outputs (write-only, deliverables)
│   ├── /secrets (read-only, mounted at runtime)
│   └── /shared (read-write, cross-project knowledge)
├── Network isolation:
│   ├── Allowlist: GitHub, PyPI, npm, HuggingFace, Anthropic
│   ├── Block: everything else by default
│   └── User-configurable additions
├── Resource limits:
│   ├── Memory cap (configurable)
│   ├── CPU cap (configurable)
│   ├── Disk quota
│   └── Process limits
└── Create docker-compose.yml for orchestration
1.2 Permission System
Tasks:
├── Define permission levels:
│   ├── SAFE: read files, run tests, generate code
│   ├── MODERATE: write files, install packages, git commit
│   ├── ELEVATED: git push, run long jobs, network access
│   └── DANGEROUS: system changes, purchases, external APIs
├── Create approval workflow:
│   ├── SAFE: auto-approve
│   ├── MODERATE: auto-approve with logging
│   ├── ELEVATED: require explicit --dangerously-skip-permissions OR user approval
│   └── DANGEROUS: always require human approval
├── Implement guardrails:
│   ├── No rm -rf outside workspace
│   ├── No sudo commands
│   ├── No modification of system configs
│   ├── No access to other projects
│   └── Rate limits on API calls
└── Create audit log system
1.3 Secret Management
Tasks:
├── Create encrypted secrets store:
│   ├── Use `pass` or `age` for encryption
│   ├── Secrets injected as env vars at container start
│   └── Never written to disk unencrypted
├── Create secrets template:
│   ├── .secrets.example (structure, no values)
│   └── .secrets (gitignored, user fills in)
├── Implement key rotation reminders
└── Create secure cleanup on container exit

PHASE 2: REPOSITORY SKELETON
Goal: Create the cross-repo template that all projects inherit.
2.1 Directory Structure
project-root/
├── .claude/
│   ├── CLAUDE.md                    # Main instructions for Claude
│   ├── agents/
│   │   ├── master.md               # Master agent definition
│   │   ├── researcher.md           # Literature review agent
│   │   ├── coder.md                # Implementation agent
│   │   ├── reviewer.md             # Code review agent
│   │   ├── falsifier.md            # Popperian falsification agent
│   │   ├── writer.md               # Paper writing agent
│   │   └── cleaner.md              # Code cleanup agent
│   ├── skills/
│   │   ├── paper-writing.md        # How to write papers
│   │   ├── figure-making.md        # Plot standards
│   │   ├── code-style.md           # Code conventions
│   │   ├── debugging.md            # Debug strategies
│   │   └── deployment.md           # How to deploy
│   ├── prompts/
│   │   ├── index.md                # Prompt collection index
│   │   └── *.md                    # Individual prompts (RAGgable)
│   └── hooks/
│       ├── pre-task.sh             # Before any task
│       ├── post-task.sh            # After any task
│       ├── pre-commit.sh           # Before git commit
│       ├── post-commit.sh          # After git commit
│       └── on-error.sh             # On task failure
├── knowledge/
│   ├── ENCYCLOPEDIA.md             # Accumulated learnings
│   ├── TRICKS.md                   # Project-specific tricks
│   ├── ENV.md                      # Environment info (conda, paths)
│   ├── MACHINES.md                 # Remote machine details
│   └── DECISIONS.md                # Design decisions log
├── state/
│   ├── GOAL.md                     # Current high-level goal
│   ├── TODO.md                     # Current task list
│   ├── PROGRESS.md                 # What's been achieved
│   ├── BLOCKERS.md                 # Current blockers
│   └── sessions/
│       └── *.md                    # Session logs (auto-generated)
├── reference/
│   ├── papers/                     # Reference papers (read-only)
│   ├── code/                       # Reference code (read-only)
│   └── examples/                   # Example outputs (read-only)
├── workspace/
│   ├── experiments/                # Messy experimentation
│   └── clean/                      # Production-ready code
├── paper/
│   ├── main.tex                    # Paper source
│   ├── references.bib              # Bibliography
│   ├── figures/                    # PDF figures
│   ├── Makefile                    # Build paper
│   └── template/                   # LaTeX template files
├── outputs/
│   ├── figures/                    # Generated plots
│   ├── tables/                     # Generated tables
│   ├── reports/                    # Generated reports
│   └── artifacts/                  # Other outputs
├── scripts/
│   ├── setup.sh                    # Initial setup
│   ├── run.sh                      # Main entry point
│   ├── overnight.sh                # Overnight mode
│   ├── interactive.sh              # Interactive mode
│   └── utils/                      # Utility scripts
├── config/
│   ├── mcp.json                    # MCP server configuration
│   ├── conda.yml                   # Environment specification
│   ├── docker-compose.yml          # Container orchestration
│   └── settings.yml                # Project settings
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  # Continuous integration
│   │   ├── auto-clean.yml          # Automated cleanup
│   │   └── paper-build.yml         # Paper compilation
│   └── CODEOWNERS                  # Review requirements
├── .gitignore                      # Comprehensive ignore rules
├── README.md                       # Project overview
└── Makefile                        # Top-level commands
2.2 CLAUDE.md Master Instructions
Tasks:
├── Write comprehensive CLAUDE.md including:
│   ├── Project overview and goals
│   ├── Directory structure explanation
│   ├── How to read/update knowledge files
│   ├── When to use which agent
│   ├── Code style requirements
│   ├── Testing requirements (always test small first)
│   ├── Git workflow (frequent commits, meaningful messages)
│   ├── Resource awareness (check disk, memory before big ops)
│   ├── Error handling (debug loop, when to escalate)
│   ├── Progress reporting format
│   ├── How to update ENCYCLOPEDIA.md
│   ├── When to ask for human input
│   └── Safety boundaries
├── Include progressive instruction protocol:
│   ├── Phase 1: Orient (read GOAL.md, understand context)
│   ├── Phase 2: Explore (examine relevant files)
│   ├── Phase 3: Plan (propose approach, get approval)
│   ├── Phase 4: Execute (one subtask at a time)
│   └── Phase 5: Validate (run falsifier, update docs)
└── Include self-modification rules:
    ├── Can update ENCYCLOPEDIA.md, TRICKS.md
    ├── Can update TODO.md, PROGRESS.md
    ├── Cannot modify CLAUDE.md without approval
    └── Cannot modify skills/ without approval
2.3 Agent Definitions
Tasks:
├── master.md:
│   ├── Role: Orchestrate sub-agents, route tasks
│   ├── Capabilities: Spawn agents, monitor progress, merge results
│   ├── Constraints: Never execute directly, only delegate
│   └── Token budget: Minimal (routing only)
├── researcher.md:
│   ├── Role: Literature review, find relevant papers
│   ├── Tools: paper-search MCP, semantic-scholar MCP
│   ├── Output: Summaries, citations, key findings
│   └── Token budget: Medium
├── coder.md:
│   ├── Role: Implement algorithms, write code
│   ├── Constraints: Test before committing, vectorize, document
│   ├── Output: Working, tested code
│   └── Token budget: High (thinking enabled)
├── reviewer.md:
│   ├── Role: Code review, suggest improvements
│   ├── Constraints: Be constructive but rigorous
│   ├── Output: Review comments, suggested fixes
│   └── Token budget: Medium
├── falsifier.md:
│   ├── Role: Attack results, find flaws
│   ├── Checks: Data leakage, statistical validity, edge cases
│   ├── Output: Vulnerability report, suggested fixes
│   └── Token budget: High (adversarial thinking)
├── writer.md:
│   ├── Role: Write paper sections, documentation
│   ├── Constraints: Follow style guide, cite properly
│   ├── Output: LaTeX content, markdown docs
│   └── Token budget: High
└── cleaner.md:
    ├── Role: Refactor, optimize, document code
    ├── Constraints: Verify behavior unchanged after cleaning
    ├── Output: Cleaner code with same functionality
    └── Token budget: Medium

PHASE 3: MCP INFRASTRUCTURE
Goal: Set up all MCP servers for auto-discovery and use.
3.1 MCP Configuration
Tasks:
├── Create comprehensive mcp.json with all 70+ MCPs:
│   ├── Tier 1 (Essential): Always loaded
│   │   ├── paper-search-mcp
│   │   ├── arxiv-mcp-server
│   │   ├── git
│   │   ├── github
│   │   ├── filesystem
│   │   ├── memory
│   │   └── sequential-thinking
│   ├── Tier 2 (Data): Loaded on demand
│   │   ├── postgres, sqlite, duckdb
│   │   ├── jupyter-mcp-server
│   │   ├── huggingface-mcp
│   │   └── mlflow-mcp
│   ├── Tier 3 (Scientific): Loaded for science tasks
│   │   ├── wolfram-mcp
│   │   ├── latex-mcp-server
│   │   └── chroma-mcp
│   ├── Tier 4 (Infrastructure): Loaded for deployment
│   │   ├── aws-mcp, terraform-mcp
│   │   ├── docker-mcp
│   │   └── cloudflare-mcp
│   ├── Tier 5 (Communication): Loaded for outreach
│   │   ├── notion-mcp, linear-mcp
│   │   ├── slack-mcp, gmail-mcp
│   │   └── todoist-mcp
│   ├── Tier 6 (Web): Loaded for web tasks
│   │   ├── fetch, puppeteer
│   │   ├── brave-search-mcp
│   │   └── browserbase-mcp
│   └── Tier 7 (Startup): Loaded for business tasks
│       ├── stripe-mcp, hubspot-mcp
│       ├── vercel-mcp, gamma-mcp
│       └── twitter-mcp, linkedin-mcp
├── Create MCP auto-discovery system:
│   ├── Task classifier detects needed MCPs
│   ├── Dynamic loading/unloading
│   └── Token-aware (don't load unused MCPs)
└── Create MCP health check system
3.2 MCP Installation Script
Tasks:
├── Create install-mcps.sh that:
│   ├── Installs all Tier 1 MCPs
│   ├── Pre-downloads Tier 2-7 for fast loading
│   ├── Verifies each MCP works
│   └── Logs versions for reproducibility
├── Create mcp-doctor.sh for troubleshooting
└── Create update-mcps.sh for updates

PHASE 4: SESSION & EXECUTION MANAGEMENT
Goal: Implement named sessions, background execution, thinking selection.
4.1 Session Wrapper
Tasks:
├── Create `research` CLI wrapper:
│   ├── research init <project-name>     # Create new project
│   ├── research start <session-name>    # Start named session
│   ├── research resume [session]        # Resume session
│   ├── research list                    # List sessions
│   ├── research status                  # Current status
│   ├── research log                     # View session logs
│   ├── research overnight <task-file>   # Start overnight mode
│   └── research stop                    # Graceful stop
├── Session metadata stored in state/sessions/:
│   ├── session-name.md
│   ├── Created timestamp
│   ├── Last active timestamp
│   ├── Token usage estimate
│   ├── Tasks completed
│   └── Current state
└── Auto-generate session names if not provided
4.2 Thinking Mode Auto-Selection
Tasks:
├── Create task classifier (cheap model or heuristics):
│   ├── SIMPLE: formatting, simple edits, lookups
│   │   └── → No thinking, cheapest model
│   ├── MEDIUM: code writing, analysis, summaries
│   │   └── → Standard thinking
│   ├── COMPLEX: architecture, debugging, research
│   │   └── → Extended thinking (3%)
│   └── CRITICAL: scientific validation, paper writing
│       └── → Ultrathink (max thinking budget)
├── Keywords/patterns for each level:
│   ├── SIMPLE: "format", "list", "show", "what is"
│   ├── MEDIUM: "write", "implement", "analyze"
│   ├── COMPLEX: "debug", "design", "why", "research"
│   └── CRITICAL: "validate", "prove", "paper", "publish"
└── User override: --think=ultra, --think=none
4.3 Background Execution
Tasks:
├── Implement & (background) support:
│   ├── research overnight <task> &
│   ├── Runs in detached container
│   ├── Logs to state/sessions/<session>.log
│   └── Email notification on completion/error
├── Implement job management:
│   ├── research jobs           # List running jobs
│   ├── research attach <job>   # Attach to job
│   ├── research kill <job>     # Stop job
│   └── research logs <job>     # View job logs
└── Integrate with task spooler (ts) for queue
4.4 Token Estimation & Budgeting
Tasks:
├── Implement token estimator:
│   ├── Count input tokens (~4 chars/token heuristic)
│   ├── Track cumulative session tokens
│   ├── Estimate remaining budget
│   └── Warn at 50%, 75%, 90% of daily limit
├── Create cost dashboard:
│   ├── Today's usage
│   ├── This week's usage
│   ├── Per-project breakdown
│   └── Per-task breakdown
└── Implement budget caps:
    ├── Per-session limit
    ├── Per-day limit
    └── Pause and ask when approaching limit

PHASE 5: KNOWLEDGE SYSTEM
Goal: Implement persistent learning and RAG.
5.1 Knowledge Files
Tasks:
├── Define ENCYCLOPEDIA.md schema:
│   ├── ## Environment
│   │   ├── Conda environment name
│   │   ├── Python version
│   │   ├── Key packages and versions
│   │   └── Path configurations
│   ├── ## Machines
│   │   ├── Local machine specs
│   │   ├── Remote machines (SSH, paths)
│   │   └── Data sync commands (rsync)
│   ├── ## Tricks
│   │   ├── Project-specific discoveries
│   │   ├── Workarounds found
│   │   └── Optimizations discovered
│   ├── ## Decisions
│   │   ├── Design decisions with rationale
│   │   └── Alternatives considered
│   └── ## Learnings
│       ├── What worked
│       ├── What didn't work
│       └── Recommendations for future
├── Create auto-update protocol:
│   ├── After each task, extract learnings
│   ├── Append to appropriate section
│   └── Deduplicate periodically
└── Create cross-project sync (optional):
    ├── /shared/global-encyclopedia.md
    └── Merge project learnings on request
5.2 Prompt Collection RAG
Tasks:
├── Create prompt indexing system:
│   ├── Each prompt in .claude/prompts/<name>.md
│   ├── Frontmatter with: tags, use-case, effectiveness-rating
│   └── Body with prompt template
├── Create prompt retrieval:
│   ├── On user voice/text input
│   ├── Classify intent
│   ├── Find matching prompts
│   └── Enhance user input with template
├── Create prompt learning:
│   ├── Track which prompts led to good results
│   ├── Adjust effectiveness ratings
│   └── Suggest new prompts based on patterns
└── Integrate with Chroma for vector search
5.3 Cheat Sheets
Tasks:
├── Create cheat sheet system:
│   ├── .claude/skills/paper-writing.md
│   │   ├── Structure guidelines
│   │   ├── Style rules
│   │   ├── Common mistakes to avoid
│   │   └── Examples
│   ├── .claude/skills/figure-making.md
│   │   ├── rcParams settings
│   │   ├── Color schemes
│   │   ├── Export formats
│   │   └── Accessibility rules
│   ├── .claude/skills/code-style.md
│   │   ├── Vectorization patterns
│   │   ├── Naming conventions
│   │   ├── Documentation format
│   │   └── Testing requirements
│   └── (more skills as needed)
├── Auto-loading based on task type
└── User can add custom skills

PHASE 6: HOOKS & LIFECYCLE
Goal: Implement pre/post hooks for all operations.
6.1 Hook System
Tasks:
├── Create hook execution framework:
│   ├── .claude/hooks/pre-task.sh
│   │   ├── Log task start
│   │   ├── Check resource availability
│   │   ├── Load relevant knowledge files
│   │   └── Set up monitoring
│   ├── .claude/hooks/post-task.sh
│   │   ├── Log task completion
│   │   ├── Extract learnings → ENCYCLOPEDIA.md
│   │   ├── Update PROGRESS.md
│   │   ├── Trigger cleanup if needed
│   │   └── Notify user if configured
│   ├── .claude/hooks/pre-commit.sh
│   │   ├── Run tests
│   │   ├── Check code style
│   │   ├── Verify no secrets committed
│   │   └── Update TODO.md
│   ├── .claude/hooks/post-commit.sh
│   │   ├── Update PROGRESS.md
│   │   └── Trigger CI if configured
│   └── .claude/hooks/on-error.sh
│       ├── Log error details
│       ├── Attempt auto-recovery
│       ├── Notify user if unrecoverable
│       └── Save state for debugging
├── Make hooks chainable and conditional
└── Allow per-project hook overrides
6.2 Progress Tracking
Tasks:
├── Implement tqdm-style progress:
│   ├── Task: [██████░░░░] 60% - Processing data
│   ├── Subtask breakdown
│   ├── ETA estimation
│   └── Token usage
├── Create live dashboard (terminal):
│   ├── Current task
│   ├── Active sub-agents
│   ├── Resource usage
│   ├── Recent logs
│   └── Token budget remaining
└── Save progress snapshots for recovery

PHASE 7: AGENT ORCHESTRATION
Goal: Implement master/sub-agent pattern and supervisor loop.
7.1 Master Agent
Tasks:
├── Implement task routing:
│   ├── Parse user input
│   ├── Classify task type
│   ├── Select appropriate sub-agent(s)
│   ├── Prepare context for sub-agent
│   └── Track sub-agent progress
├── Implement parallel execution:
│   ├── Independent tasks run in parallel
│   ├── Dependent tasks run sequentially
│   └── Merge results when all complete
├── Implement token budget distribution:
│   ├── Allocate budget per sub-agent
│   ├── Reallocate if one finishes early
│   └── Warn master if approaching limit
└── Implement common observation space:
    ├── Sub-agents can read each other's outputs
    ├── Sub-agents can signal each other
    └── Master mediates conflicts
7.2 Supervisor (Agent-as-User) Pattern
Tasks:
├── Implement goal-checker agent:
│   ├── After each worker output
│   ├── Compare to original goal
│   ├── Evaluate: SUCCESS / NEEDS_CORRECTION / STUCK
│   └── Generate corrective prompt if needed
├── Implement iteration loop:
│   while not goal_achieved and iterations < max:
│       result = worker.execute(task)
│       evaluation = supervisor.evaluate(goal, result)
│       if evaluation == SUCCESS: break
│       elif evaluation == NEEDS_CORRECTION:
│           task = evaluation.correction
│       elif evaluation == STUCK:
│           escalate_to_human()
├── Implement escalation rules:
│   ├── Max iterations before escalate
│   ├── Specific error types that escalate
│   └── User-defined escalation triggers
└── Implement "severe reviewer" mode:
    ├── Extra critical evaluation
    ├── Look for edge cases
    └── Challenge assumptions
7.3 Falsifier Agent
Tasks:
├── Implement falsification checks:
│   ├── Data leakage detection:
│   │   ├── Check train/test separation
│   │   ├── Check for future data in features
│   │   └── Check for target leakage
│   ├── Statistical validity:
│   │   ├── Check sample sizes
│   │   ├── Check for p-hacking
│   │   ├── Verify confidence intervals
│   │   └── Check for multiple comparisons
│   ├── Code correctness:
│   │   ├── Edge case testing
│   │   ├── Boundary conditions
│   │   └── Error handling
│   └── Reproducibility:
│       ├── Check random seeds
│       ├── Verify determinism
│       └── Test on different data
├── Implement attack strategies:
│   ├── Adversarial inputs
│   ├── Distribution shift
│   └── Confounding variables
└── Generate vulnerability report with severity

PHASE 8: OVERNIGHT MODE
Goal: Implement autonomous long-running execution.
8.1 Overnight Loop
Tasks:
├── Create overnight.sh:
│   ├── Load task from task.md (or argument)
│   ├── Initialize monitoring
│   ├── Start iteration loop:
│   │   for i in {1..N}; do
│   │       claude --session overnight-$DATE-$i \
│   │              --thinking-budget extended \
│   │              -p "$(cat .claude/overnight-prompt.md)"
│   │       # Check exit status
│   │       # Update progress
│   │       # Check if goal achieved
│   │   done
│   ├── Send completion notification
│   └── Generate summary report
├── Create overnight-prompt.md template:
│   ├── Read current state
│   ├── Continue from last checkpoint
│   ├── Work toward goal
│   ├── Update progress files
│   └── Checkpoint frequently
└── Create recovery mechanism:
    ├── On crash, read last checkpoint
    ├── Diagnose failure
    ├── Attempt fix
    └── Continue or escalate
8.2 Debug Loop
Tasks:
├── Implement auto-debug:
│   ├── On error, capture full context
│   ├── Analyze error message
│   ├── Generate fix hypothesis
│   ├── Apply fix
│   ├── Test fix
│   └── If still failing, try next hypothesis
├── Max debug iterations before escalate
├── Learn from successful fixes → ENCYCLOPEDIA.md
└── Learn from persistent failures → BLOCKERS.md
8.3 Resource Monitoring
Tasks:
├── Implement resource checks:
│   ├── Disk space (warn at 80%, stop at 95%)
│   ├── Memory (warn at 80%, stop at 95%)
│   ├── GPU memory (if applicable)
│   └── Network connectivity
├── Implement cleanup triggers:
│   ├── Delete old checkpoints when disk low
│   ├── Clear caches
│   └── Compress logs
└── Integrate with hooks (pre-task check)

PHASE 9: INTERACTIVE MODE
Goal: Implement dashboard and real-time interaction.
9.1 Terminal Dashboard
Tasks:
├── Create TUI (terminal UI) with:
│   ├── Current task panel
│   ├── Sub-agent status panel
│   ├── Log stream panel
│   ├── Resource usage panel
│   └── Input panel (for commands)
├── Implement commands:
│   ├── /status - Show current state
│   ├── /agents - List active agents
│   ├── /logs <agent> - Show agent logs
│   ├── /stop <agent> - Stop agent
│   ├── /approve <action> - Approve pending action
│   ├── /reject <action> - Reject pending action
│   ├── /budget - Show token budget
│   └── /help - Show commands
└── Use rich or textual library for TUI
9.2 Voice Input
Tasks:
├── Implement voice pipeline:
│   ├── Record audio (system mic or file)
│   ├── Transcribe with Whisper (local or API)
│   ├── Detect language
│   ├── Translate to English if needed
│   ├── Structure into clear prompt
│   └── Send to Claude
├── Integrate with macOS dictation as fallback
└── Create voice-to-session shortcut
9.3 Browser Integration
Tasks:
├── Implement visual preview:
│   ├── Auto-open generated plots
│   ├── Auto-open HTML reports
│   ├── Auto-open PDFs
│   └── Capture screenshots for review
├── Implement puppeteer for web tasks:
│   ├── Monitor websites
│   ├── Fill forms
│   └── Extract data
└── Create browser-based dashboard (future):
    ├── VS Code extension
    └── Web app

PHASE 10: PAPER & OUTPUT GENERATION
Goal: Implement paper writing and figure generation.
10.1 Paper Pipeline
Tasks:
├── Create paper/ structure:
│   ├── main.tex (master document)
│   ├── sections/ (individual sections)
│   ├── figures/ (PDF figures)
│   ├── tables/ (LaTeX tables)
│   ├── references.bib (bibliography)
│   └── Makefile (build commands)
├── Create Makefile:
│   ├── make paper - Full build
│   ├── make watch - Auto-rebuild on change
│   ├── make figures - Regenerate all figures
│   ├── make clean - Clean build artifacts
│   └── make submit - Prepare submission zip
├── Implement figure generation:
│   ├── Load data from outputs/
│   ├── Apply rcParams (from skills/figure-making.md)
│   ├── Generate plot
│   ├── Export as PDF
│   └── Save to paper/figures/
├── Implement citation management:
│   ├── Use PubMed MCP for lookups
│   ├── Auto-generate BibTeX entries
│   ├── Check for missing citations
│   └── Verify citation format
└── Implement style transfer (inpainting):
    ├── Load reference paper style
    ├── Analyze tone, structure, terminology
    ├── Apply style to generated content
    └── Verify no plagiarism
10.2 Code Cleaning Pipeline
Tasks:
├── Implement cleaner agent workflow:
│   ├── Read code file
│   ├── Run tests, save expected output
│   ├── Refactor code
│   ├── Run tests again
│   ├── Compare outputs (must match)
│   └── If match: commit. If not: revert.
├── Cleaning operations:
│   ├── Remove dead code
│   ├── Vectorize loops
│   ├── Improve variable names
│   ├── Add/improve docstrings
│   ├── Split large functions
│   └── Apply consistent formatting
└── Generate cleaning report

PHASE 11: NOTIFICATIONS & OUTREACH
Goal: Implement communication and startup features.
11.1 Notification System
Tasks:
├── Implement notification channels:
│   ├── Email (SendGrid/Gmail)
│   ├── Slack
│   ├── Desktop notification
│   └── (future: mobile push)
├── Notification triggers:
│   ├── Task complete
│   ├── Task failed
│   ├── Approval needed
│   ├── Budget warning
│   └── Overnight summary
├── Notification throttling:
│   ├── Max 2 emails per hour
│   ├── Batch non-urgent notifications
│   └── Respect do-not-disturb hours
└── Create notification templates
11.2 Startup/Outreach MCPs
Tasks:
├── Configure startup MCPs:
│   ├── Website: vercel-mcp, netlify-mcp
│   ├── Slides: gamma-mcp, canva-mcp
│   ├── Social: twitter-mcp, linkedin-mcp
│   ├── Analytics: posthog-mcp, plausible-mcp
│   ├── Email: mailchimp-mcp, convertkit-mcp
│   ├── CRM: hubspot-mcp
│   ├── Payments: stripe-mcp
│   └── Scheduling: calendly-mcp
├── Create outreach workflows:
│   ├── Generate social posts from paper
│   ├── Create presentation from results
│   ├── Update website with new project
│   └── Send newsletter update
└── Create monitoring:
    ├── Track social engagement
    ├── Monitor website traffic
    └── Track email opens

PHASE 12: TESTING & VALIDATION
Goal: Ensure everything works before autonomous operation.
12.1 Test Suite
Tasks:
├── Unit tests:
│   ├── Session management
│   ├── MCP loading
│   ├── Hook execution
│   ├── Token estimation
│   └── Knowledge updates
├── Integration tests:
│   ├── Full overnight loop (short task)
│   ├── Multi-agent orchestration
│   ├── Paper generation
│   └── Cross-project sync
├── Safety tests:
│   ├── Permission boundaries
│   ├── Resource limits
│   ├── Secret handling
│   └── Network isolation
└── Create test projects:
    ├── Simple: "Count to 10"
    ├── Medium: "Analyze sample data"
    └── Complex: "Write a short paper"
12.2 Documentation
Tasks:
├── Create comprehensive docs:
│   ├── README.md - Quick start
│   ├── docs/installation.md
│   ├── docs/configuration.md
│   ├── docs/usage.md
│   ├── docs/agents.md
│   ├── docs/mcps.md
│   ├── docs/troubleshooting.md
│   └── docs/contributing.md
├── Create video tutorials (future)
└── Create example projects

PHASE 13: POLISH & OPTIMIZATION
Goal: Improve UX and performance.
13.1 UX Improvements
Tasks:
├── Prompt suggestions:
│   ├── After each response, suggest follow-ups
│   ├── Based on context and common patterns
│   └── One-click execution
├── Auto-completion:
│   ├── Command completion
│   ├── File path completion
│   └── Agent name completion
├── Error messages:
│   ├── Clear, actionable messages
│   ├── Suggested fixes
│   └── Link to relevant docs
└── Onboarding wizard:
    ├── Guide through initial setup
    ├── Collect credentials
    └── Verify everything works
13.2 Performance
Tasks:
├── Optimize MCP loading:
│   ├── Lazy loading
│   ├── Connection pooling
│   └── Cache common queries
├── Optimize knowledge retrieval:
│   ├── Index ENCYCLOPEDIA.md
│   ├── Use embeddings for search
│   └── Cache frequent lookups
└── Optimize container startup:
    ├── Pre-warm containers
    ├── Shared layers
    └── Volume caching