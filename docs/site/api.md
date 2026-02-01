# API Reference

Module-level documentation for all core packages. Each section covers public classes, functions, and constants.

---

## `cli.main` -- CLI Entry Point

The main Typer application providing the `research` command.

### Commands

| Command | Description |
|---------|-------------|
| `research init <name>` | Initialize a new research project with interactive onboarding |
| `research start` | Start an interactive research session |
| `research overnight` | Run autonomous overnight mode |
| `research status` | Show current TODO and progress |
| `research paper build` | Compile the LaTeX paper |
| `research dashboard` | Launch the TUI dashboard |
| `research agents` | List agent types and their status |
| `research memory search <query>` | Search the knowledge base |
| `research metrics` | Display token and cost metrics |
| `research --version` | Print version and exit |

### Options

```
research init <name> [--path PATH]
research start [--session-name NAME]
research overnight [--task-file PATH] [--iterations N]
```

---

## `cli.dashboard` -- TUI Dashboard

Rich-based terminal dashboard for monitoring active sessions.

### Panels

- **Agents** -- Active agent types, current tasks, and budget usage.
- **Resources** -- CPU, RAM, GPU, and disk utilization.
- **Memory** -- Recent knowledge entries and vector memory stats.
- **Progress** -- Task completion log.

---

## `cli.gallery` -- Figure Gallery

Terminal-based figure preview for generated plots.

---

## `core.agents` -- Agent Orchestration

Task routing, budget management, DAG execution, and supervision.

### `AgentType`

```python
class AgentType(str, Enum):
    MASTER = "master"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    FALSIFIER = "falsifier"
    WRITER = "writer"
    CLEANER = "cleaner"
```

### Constants

```python
DEFAULT_BUDGET_SPLIT: dict[AgentType, int]
# {RESEARCHER: 15, CODER: 35, REVIEWER: 10, FALSIFIER: 20, WRITER: 15, CLEANER: 5}

ROUTING_KEYWORDS: dict[AgentType, list[str]]
# Keyword lists used for automatic task routing.
```

### Functions

#### `route_task(description: str) -> AgentType`

Classify a task description and return the most appropriate agent type based on keyword matching.

#### `execute_task(task: Task) -> TaskResult`

Execute a single task. Delegates to claude-flow `spawn_agent` when available, otherwise calls Claude CLI as a subprocess.

#### `execute_dag(tasks: list[Task]) -> list[TaskResult]`

Execute a DAG of tasks, resolving dependencies and running independent tasks in parallel via `ThreadPoolExecutor`. Falls back from claude-flow `run_swarm` when unavailable.

---

## `core.session` -- Session Management

Tracking, snapshots, and recovery for research sessions.

### `Session`

```python
@dataclass
class Session:
    name: str
    started: str                    # ISO timestamp
    status: str = "active"          # "active" | "completed"
    token_estimate: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    checkpoints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> Session: ...
```

### Functions

#### `create_session(name: Optional[str] = None) -> Session`

Create and persist a new session. Also starts a claude-flow session when available.

#### `end_session(name: str) -> Session`

Mark a session as completed and update the JSON file.

#### `get_session(name: str) -> Optional[Session]`

Load a session by name.

#### `list_sessions() -> list[Session]`

Return all persisted sessions.

#### `create_snapshot(session: Session) -> Path`

Save a copy of the current state directory for recovery.

---

## `core.tokens` -- Token Budget Tracking

Token estimation and budget management with claude-flow metrics integration.

### `TokenBudget`

```python
@dataclass
class TokenBudget:
    session_limit: int = 100_000
    daily_limit: int = 500_000
    current_session: int = 0
    current_daily: int = 0
```

### Functions

#### `estimate_tokens(text: str) -> int`

Estimate token count. Uses claude-flow metrics for actual counts when available, otherwise approximates at ~4 characters per token.

#### `check_budget(budget: TokenBudget, estimated_cost: int) -> dict`

Check whether an operation fits within budget. Returns:

```python
{
    "can_proceed": bool,
    "session_used_pct": float,
    "daily_used_pct": float,
    "warning": bool,       # True when session usage > 75%
}
```

#### `select_thinking_mode(task_description: str) -> str`

Auto-select thinking mode based on task complexity. Returns one of: `"none"`, `"standard"`, `"extended"`, `"ultrathink"`.

---

## `core.knowledge` -- Knowledge Management

Encyclopedia auto-update and semantic search.

### Constants

```python
ENCYCLOPEDIA_PATH = Path("knowledge/ENCYCLOPEDIA.md")
SHARED_KNOWLEDGE_PATH = Path("/shared/knowledge")
```

### Functions

#### `append_learning(section: str, entry: str, encyclopedia_path: Path = ENCYCLOPEDIA_PATH) -> None`

Append a timestamped entry to the encyclopedia under the given section. Valid sections: `"Tricks"`, `"Decisions"`, `"What Works"`, `"What Doesn't Work"`.

When claude-flow is available, the entry is also written to the HNSW vector index.

#### `search_knowledge(query: str, top_k: int = 5) -> list[str]`

Search the knowledge base. Uses HNSW semantic search via claude-flow when available, otherwise performs keyword grep over the markdown file.

#### `sync_shared_knowledge(project_path: Path) -> None`

Sync knowledge entries to the shared volume for cross-project access.

---

## `core.mcps` -- MCP Auto-Discovery

Task-based MCP tier loading.

### Constants

```python
MCP_CONFIG = Path("templates/config/mcp-nucleus.json")
```

### Functions

#### `load_mcp_config() -> dict`

Load the full MCP tier configuration from JSON.

#### `classify_task(task_description: str) -> set[str]`

Determine which MCP tiers to load based on keyword matching. Always includes `"tier1_essential"`.

#### `get_mcps_for_task(task_description: str) -> dict`

Return all MCPs needed for a task by merging the relevant tiers.

#### `get_claude_flow_mcp_config() -> dict`

Return claude-flow as a tier-0 MCP entry when available, or an empty dict.

#### `install_mcp(mcp_name: str, source: str) -> bool`

Install an MCP from its source (GitHub or npm).

---

## `core.model_router` -- Model Routing

Task complexity classification and model selection.

### `TaskComplexity`

```python
class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CRITICAL = "critical"
```

### `ModelConfig`

```python
@dataclass
class ModelConfig:
    name: str
    provider: str                  # "anthropic", "openai", "local"
    max_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    supports_thinking: bool = False
    strengths: list[str] = field(default_factory=list)
```

### Functions

#### `classify_complexity(description: str) -> TaskComplexity`

Classify task complexity using keyword sets. Delegates to claude-flow 3-tier router when available.

#### `select_model(complexity: TaskComplexity, budget: Optional[TokenBudget] = None) -> ModelConfig`

Select the appropriate model for a given complexity level. When budget is below 20%, always returns Haiku.

---

## `core.paper` -- Paper Pipeline

Figure generation, citation management, and LaTeX compilation.

### Constants

```python
PAPER_DIR = Path("paper")
FIGURES_DIR = Path("figures")
BIB_FILE = PAPER_DIR / "references.bib"

COLORS: dict[str, str]   # Colorblind-safe hex palette
RC_PARAMS: dict           # matplotlib rcParams for publication quality
```

### Functions

#### `apply_rcparams() -> None`

Apply publication-quality matplotlib rcParams globally.

#### `add_citation(key: str, entry_type: str = "article", *, author: str, title: str, year: str, **kwargs) -> None`

Add a BibTeX entry to `references.bib`. Supports all standard BibTeX fields (`journal`, `doi`, `volume`, `pages`, etc.).

#### `compile_paper(paper_dir: Path = PAPER_DIR) -> bool`

Run the full LaTeX build: `pdflatex` -> `biber` -> `pdflatex` -> `pdflatex`.

#### `list_figures(figures_dir: Path = FIGURES_DIR) -> list[Path]`

List all generated figures.

---

## `core.reproducibility` -- Reproducibility

Run logging, artifact registry, and dataset hashing.

### `RunLog`

```python
@dataclass
class RunLog:
    run_id: str
    command: str
    started: str                    # ISO timestamp
    ended: Optional[str] = None
    status: str = "running"
    git_hash: str = ""
    parameters: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    notes: str = ""
```

### Functions

#### `log_run(run: RunLog) -> Path`

Persist a run log to `state/runs/<run_id>.json`.

#### `load_run(run_id: str) -> Optional[RunLog]`

Load a run log by ID.

#### `register_artifact(name: str, path: str, run_id: str, metadata: dict = {}) -> None`

Register an artifact with SHA-256 checksum in `state/artifact_registry.json`.

#### `verify_artifact(name: str) -> bool`

Verify an artifact's integrity by recomputing its checksum.

#### `hash_dataset(path: Path) -> str`

Compute a SHA-256 hash of a dataset file for integrity tracking.

---

## `core.security` -- Security

Secret scanning, immutable file protection, and repo root enforcement.

### Constants

```python
SECRET_PATTERNS: list[re.Pattern]   # Regex patterns for secret detection
DEFAULT_IMMUTABLE: list[str]        # Glob patterns for immutable files
```

### Functions

#### `enforce_repo_root() -> Path`

Ensure the current directory is inside a git repository. Returns the repo root path. Raises `RuntimeError` if not in a repo.

#### `scan_for_secrets(path: Path, *, extra_patterns: list[re.Pattern] | None = None) -> list[dict]`

Scan files for secrets. Merges claude-flow scan results with local regex matches when available. Returns a list of findings with file path, line number, and matched pattern.

#### `protect_immutable_files(files: list[str]) -> list[str]`

Filter out immutable files from a list of paths. Returns only the files that are safe to modify.

---

## `core.notifications` -- Notifications

Multi-channel notifications with throttling.

### `NotificationConfig`

```python
@dataclass
class NotificationConfig:
    slack_webhook: str = ""
    email_to: str = ""
    email_from: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    desktop_enabled: bool = True
    throttle_seconds: int = 300
```

### Functions

#### `send_notification(message: str, *, title: str = "", level: str = "info") -> None`

Send a notification to all configured channels. Respects throttle settings.

#### `send_slack(message: str, webhook_url: str) -> bool`

Send a Slack message via webhook.

#### `send_email(subject: str, body: str, config: NotificationConfig) -> bool`

Send an email via SMTP.

#### `send_desktop(title: str, message: str) -> bool`

Send a desktop notification via `notify-send`.

---

## `core.environment` -- Environment Management

System discovery and conda environment management.

### `SystemInfo`

```python
@dataclass
class SystemInfo:
    os: str = ""
    os_version: str = ""
    python_version: str = ""
    cpu: str = ""
    gpu: str = ""
    ram_gb: float = 0.0
    conda_available: bool = False
    docker_available: bool = False
```

### Functions

#### `discover_system() -> SystemInfo`

Detect the current system's hardware and software capabilities.

#### `create_conda_env(name: str, python_version: str = "3.11") -> bool`

Create a new conda environment.

#### `install_packages(packages: list[str], env_name: Optional[str] = None) -> bool`

Install packages into a conda environment or the current Python environment.

---

## `core.resources` -- Resource Monitoring

Resource snapshots, checkpoint policies, and cleanup.

### `ResourceSnapshot`

```python
@dataclass
class ResourceSnapshot:
    timestamp: float = 0.0
    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_free_gb: float = 0.0
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0
```

### `CheckpointPolicy`

```python
@dataclass
class CheckpointPolicy:
    interval_minutes: int = 30
    max_checkpoints: int = 5
    min_disk_free_gb: float = 5.0
    checkpoint_dir: Path = CHECKPOINTS_DIR
```

### Functions

#### `monitor_resources() -> ResourceSnapshot`

Take a snapshot of current system resource usage. Merges claude-flow GPU metrics when available.

#### `should_checkpoint(policy: CheckpointPolicy, last_checkpoint_time: float) -> bool`

Determine whether a new checkpoint should be created based on the policy.

#### `create_checkpoint(name: str, policy: CheckpointPolicy) -> Path`

Create a checkpoint of the current state, respecting retention limits.

#### `cleanup_old_checkpoints(policy: CheckpointPolicy) -> int`

Remove checkpoints exceeding the maximum count. Returns the number removed.

---

## `core.onboarding` -- Project Initialization

Interactive onboarding questionnaire and workspace setup.

### `OnboardingAnswers`

Dataclass holding all user responses from the init wizard: project goal, type, timeline, constraints, and credentials.

### Functions

#### `collect_answers() -> OnboardingAnswers`

Run the interactive questionnaire and return structured answers.

#### `setup_workspace(project_path: Path, answers: OnboardingAnswers) -> None`

Create the project directory structure from templates.

#### `write_goal_file(path: Path, answers: OnboardingAnswers) -> None`

Write the customized GOAL.md.

#### `write_settings(path: Path, answers: OnboardingAnswers) -> None`

Write `config/settings.yml` from onboarding answers.

---

## `core.autonomous` -- Autonomous Routines

Scheduled tasks, monitoring, and confirmation gates.

### `ScheduledRoutine`

```python
@dataclass
class ScheduledRoutine:
    name: str
    description: str
    schedule: str                  # "daily", "hourly", "weekly", or cron
    command: str
    enabled: bool = True
    last_run: str = ""
    requires_confirmation: bool = False
```

### Functions

#### `add_routine(routine: ScheduledRoutine) -> None`

Register a new scheduled routine.

#### `remove_routine(name: str) -> bool`

Remove a routine by name.

#### `list_routines() -> list[ScheduledRoutine]`

List all registered routines.

#### `run_due_routines() -> list[str]`

Execute all routines that are due. Returns names of executed routines. Routines requiring confirmation are skipped in autonomous mode.

#### `audit_log(action: str, details: str = "") -> None`

Append an entry to `state/audit.log`.

---

## `core.cross_repo` -- Cross-Repository Coordination

Linking repos, coordinated commits, and permission management.

### `LinkedRepo`

```python
@dataclass
class LinkedRepo:
    name: str
    path: str
    remote_url: str = ""
    permissions: list[str] = field(default_factory=lambda: ["read"])
    linked_at: str                 # ISO timestamp
```

### Functions

#### `link_repo(name: str, path: str, permissions: list[str] = ["read"]) -> LinkedRepo`

Link an external repository with specified permissions.

#### `unlink_repo(name: str) -> bool`

Remove a linked repository.

#### `list_linked_repos() -> list[LinkedRepo]`

List all linked repositories.

#### `coordinated_commit(message: str, repos: list[str]) -> dict[str, bool]`

Commit to multiple linked repos with the same message. Delegates to claude-flow `multi_repo_sync` when available. Returns a dict mapping repo names to success status.

---

## `core.claude_flow` -- Claude-Flow Bridge

Bridge to claude-flow v3 CLI for enhanced orchestration.

### `ClaudeFlowUnavailable`

Exception raised when claude-flow is not installed or a command fails.

### `ClaudeFlowBridge`

Singleton wrapper around the `npx claude-flow@v3alpha` CLI.

| Method | Description | Fallback |
|--------|-------------|----------|
| `spawn_agent(type, task)` | Execute single agent task | Claude CLI subprocess |
| `run_swarm(tasks, topology)` | Multi-agent swarm execution | ThreadPoolExecutor |
| `route_model(description)` | 3-tier model routing | Keyword classification |
| `query_memory(query)` | HNSW semantic search | Keyword grep |
| `store_memory(text)` | Index in vector memory | Markdown append |
| `scan_security(path)` | Security scan | Local regex patterns |
| `get_metrics()` | Token/cost metrics | Char-based estimation |
| `start_session(name)` | Start tracked session | Local JSON file |
| `end_session(name)` | End tracked session | Local JSON update |
| `multi_repo_sync(msg, repos)` | Cross-repo commit | Sequential git commands |

### Functions

#### `_get_bridge() -> ClaudeFlowBridge`

Get or create the singleton bridge instance. Raises `ClaudeFlowUnavailable` if claude-flow is not installed.

---

## `core.style_transfer` -- Style Transfer

Paper style analysis and plagiarism checking.

### Functions

#### `analyze_style(text: str) -> dict`

Analyze the writing style of a text passage (sentence length, vocabulary complexity, passive voice ratio, etc.).

#### `transfer_style(source_style: dict, text: str) -> str`

Rewrite text to match the analyzed style profile.

#### `check_plagiarism(text: str, reference: str) -> float`

Compute a similarity score between two texts. Returns a float between 0.0 and 1.0.

---

## `core.voice` -- Voice Input

Audio transcription and prompt structuring.

### Functions

#### `transcribe_audio(audio_path: Path) -> str`

Transcribe an audio file to text using whisper-cpp or a similar backend.

#### `structure_prompt(raw_text: str) -> str`

Convert raw transcribed text into a structured research prompt.

---

## `core.meta_rules` -- Meta-Rule Capture

Operational rule detection from conversation patterns.

### Functions

#### `detect_rules(conversation: str) -> list[str]`

Analyze a conversation transcript and extract implicit operational rules.

#### `suggest_rules(detected: list[str]) -> list[str]`

Filter and rank detected rules by relevance.

---

## `core.automation_utils` -- Automation Utilities

Data handling and experiment running helpers.

### Functions

#### `downsample(data, fraction: float = 0.1)`

Take a random subsample for quick testing.

#### `run_experiment(command: str, params: dict) -> RunLog`

Execute an experiment command with parameter tracking.
