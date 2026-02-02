# API Reference

Module-level documentation for all core packages. Each section covers public classes, functions, and constants.

---

## `cli.main` -- CLI Entry Point

The main Typer application providing the `ricet` command.

### Commands

| Command | Description |
|---------|-------------|
| `ricet init <name>` | Initialize a new research project with interactive onboarding |
| `ricet start` | Start an interactive research session |
| `ricet overnight` | Run autonomous overnight mode |
| `ricet status` | Show current TODO and progress |
| `ricet config [section]` | View or reconfigure project settings |
| `ricet paper <action>` | Paper pipeline (build, update, modernize, check, adapt-style) |
| `ricet dashboard` | Launch the TUI dashboard |
| `ricet agents` | List agent types and their status |
| `ricet memory <action>` | Knowledge base (search, log-decision, export, import, stats) |
| `ricet metrics` | Display token and cost metrics |
| `ricet mobile <action>` | Mobile server (serve, stop, pair, connect-info, tokens, cert-regen, status) |
| `ricet voice` | Record and transcribe voice commands |
| `ricet publish <platform>` | Publish to social media (medium, linkedin) |
| `ricet cite <query>` | Search and cite papers from Semantic Scholar and arXiv |
| `ricet discover <query>` | Broad literature search with ranked results |
| `ricet fidelity` | Check GOAL.md alignment score |
| `ricet maintain` | Run daily maintenance pass |
| `ricet verify <text>` | Verify factual claims |
| `ricet debug <command>` | Auto-debug loop for a command |
| `ricet adopt <source>` | Adopt an existing repository |
| `ricet link <path>` | Link a repository for cross-repo RAG |
| `ricet unlink <name>` | Remove a linked repository |
| `ricet reindex` | Re-index all linked repositories |
| `ricet docs` | Auto-update project documentation |
| `ricet browse <url>` | Fetch and extract text from a URL |
| `ricet infra <action>` | Infrastructure management (check, docker-build, cicd, secrets) |
| `ricet runbook <file>` | Execute code blocks from a markdown runbook |
| `ricet projects <action>` | Multi-project management (list, switch, register) |
| `ricet worktree <action>` | Git worktree management (add, list, remove, prune) |
| `ricet queue <action>` | Task queue (submit, status, drain, cancel-all) |
| `ricet package <action>` | Python package management (init, build, publish) |
| `ricet repro <action>` | Reproducibility tracking (log, list, show, hash) |
| `ricet auto <action>` | Automation routines (add-routine, list-routines, monitor) |
| `ricet website <action>` | Website builder (init, build, deploy, preview) |
| `ricet audit` | Audit project code for stubs and incomplete features |
| `ricet list-sessions` | List all sessions |
| `ricet resume <name>` | Resume a previous session |
| `ricet --version` | Print version and exit |

### Selected Options

```
ricet init <name> [--path PATH] [--skip-repo] [--no-env]
ricet start [--session-name NAME]
ricet overnight [--task-file PATH] [--iterations N] [--docker]
ricet mobile serve|stop|pair|connect-info|tokens|cert-regen|status
ricet paper build|update|modernize|check|adapt-style
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

Full onboarding workflow: system detection, questionnaire, credential collection, workspace setup, and goal-aware scaffolding.

### `OnboardingAnswers`

```python
@dataclass
class OnboardingAnswers:
    project_name: str = ""
    goal: str = ""
    project_type: str = "general"
    github_repo: str = ""
    success_criteria: list[str] = field(default_factory=list)
    timeline: str = "flexible"
    compute_type: str = "local-cpu"    # Auto-detected
    gpu_name: str = ""                 # Auto-detected
    notification_method: str = "none"
    notification_email: str = ""
    slack_webhook: str = ""
    credentials: dict[str, str] = field(default_factory=dict)
    journal_target: str = ""
    needs_website: bool = False
    needs_mobile: bool = False
```

### Functions

#### `detect_system_for_init() -> dict`

Auto-detect system capabilities (OS, Python, CPU, GPU, RAM, Docker, Conda). Returns a summary dict used to pre-fill compute settings.

#### `auto_install_claude_flow(*, run_cmd=None) -> bool`

Install claude-flow via npm if not already available. Returns True if available after the call.

#### `collect_answers(project_name: str, *, prompt_fn=None, system_info: dict = None) -> OnboardingAnswers`

Run the streamlined questionnaire. GPU and compute type are auto-detected from `system_info`. Asks for: notification method, journal target, website needs, mobile access.

#### `collect_credentials(answers: OnboardingAnswers, *, prompt_fn=None, print_fn=None) -> dict[str, str]`

Walk through 20+ API credentials grouped by category (core, ML, publishing, cloud, integrations, Slack, email). Each shows where to get the key and pricing info. Enter to skip any.

#### `setup_workspace(project_path: Path) -> None`

Create workspace directories (`reference/`, `uploads/`, `secrets/`, `local/`) with guided README files.

#### `write_settings(project_path: Path, answers: OnboardingAnswers) -> Path`

Write `config/settings.yml` from onboarding answers.

#### `write_goal_file(project_path: Path, answers: OnboardingAnswers) -> None`

Write the customized GOAL.md.

#### `write_env_file(project_path: Path, credentials: dict[str, str]) -> Path`

Write credentials to `secrets/.env`.

#### `write_env_example(project_path: Path) -> Path`

Write `secrets/.env.example` template showing all possible variables with how-to-get URLs.

#### `infer_packages_from_goal(goal_content: str, *, use_claude: bool = True) -> list[str]`

Infer Python packages from GOAL.md content. Tries Claude CLI for domain-specific inference, falls back to keyword matching.

#### `install_inferred_packages(packages: list[str]) -> tuple[list[str], list[str]]`

Install a list of pip packages, returning `(installed, failed)`. Asks Claude for alternatives when installation fails.

#### `generate_goal_todos(goal_content: str) -> str`

Generate 8-12 goal-specific TODO items as a markdown checklist using Claude CLI.

#### `generate_goal_folders(goal_content: str) -> list[str]`

Suggest 3-6 project-specific directory names based on the research goal.

#### `validate_goal_content(content: str, min_chars: int = 200) -> bool`

Check that GOAL.md has real user content (strips boilerplate, comments, placeholders).

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

## `core.auto_commit` -- Auto-Commit & Push

Automatic git commit and push after state-modifying operations.

### Functions

#### `auto_commit(message: str, *, push: bool | None = None, cwd: Path | None = None, run_cmd=None) -> bool`

Commit all changes and optionally push. Controlled by environment variables:

- `RICET_AUTO_COMMIT` (default `"true"`) -- master switch
- `AUTO_PUSH` (default `"true"`) -- push after commit

Returns `True` if a commit was made, `False` otherwise (no changes, not a git repo, or disabled).

---

## `core.claude_helper` -- Claude CLI Helper

Shared helper for calling the Claude CLI from core modules.

### Functions

#### `call_claude(prompt: str, *, timeout: int = 30, run_cmd=None) -> str | None`

Call `claude -p <prompt> --output-format json` and return the response text. Returns `None` on failure, timeout, or when disabled.

#### `call_claude_json(prompt: str, **kwargs) -> dict | list | None`

Call Claude and parse the response as JSON. Strips markdown code fences before parsing. Returns `None` if parsing fails.

### Configuration

- `RICET_NO_CLAUDE=true` -- Disable all Claude CLI calls
- Auto-disabled during pytest (`PYTEST_CURRENT_TEST` detection)

---

## `core.adopt` -- Repository Adoption

Transform existing repositories into ricet projects.

### Functions

#### `adopt_repo(source: str, *, project_name: str | None = None, target_path: Path | None = None, fork: bool = True, run_cmd=None) -> Path`

Adopt a repository from a GitHub URL or local path:

1. URL + fork: `gh repo fork --clone` (falls back to `git clone`)
2. URL + no fork: `git clone`
3. Local path: work in place

Overlays ricet structure, pre-fills GOAL.md from README, registers in `~/.ricet/projects.json`, and auto-commits.

---

## `core.collaboration` -- Collaborative Research

Multi-user synchronization and merge helpers.

### Functions

#### `sync_before_start(*, cwd: Path | None = None, run_cmd=None) -> bool`

Run `git pull --rebase` to sync with remote before starting a session. Returns `True` on success.

#### `get_user_id(*, run_cmd=None) -> str`

Get current user identity from `git config user.email`, falling back to hostname.

#### `merge_encyclopedia(ours_path: Path, theirs_text: str) -> str`

Merge encyclopedia content by deduplicating lines.

#### `merge_state_file(ours_path: Path, theirs_text: str) -> str`

Merge state files by appending non-duplicate non-empty lines.

---

## `core.cross_repo` -- Cross-Repository Coordination & RAG

Linking repos, coordinated commits, permission management, and cross-repo RAG indexing.

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

#### `link_repository(name: str, path: str, permissions: list[str] = ["read"]) -> LinkedRepo`

Link an external repository with specified permissions.

#### `coordinated_commit(message: str, repo_names: list[str]) -> dict[str, bool]`

Commit to multiple linked repos with the same message. Delegates to claude-flow `multi_repo_sync` when available. Returns a dict mapping repo names to success status.

#### `index_linked_repo(repo: LinkedRepo) -> int`

Walk a linked repo and index text files (.py, .md, .txt, .tex, .rst, .yml, .yaml, .json) into HNSW vector memory or local JSON. Returns the number of files indexed.

#### `search_all_linked(query: str, top_k: int = 10) -> list[dict]`

Search across all linked repo indexes. Uses HNSW semantic search when available, otherwise keyword search on local JSON. Returns dicts with `text`, `path`, `source` keys.

#### `reindex_all() -> dict[str, int]`

Re-index all linked repositories. Returns a dict mapping repo name to file count.

#### `enforce_permission_boundaries(repo_name: str, action: str) -> bool`

Check if an action (`read`, `write`, `commit`) is permitted on a linked repo.

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

---

## `core.auto_debug` -- Auto-Debug Loop

Automatic error detection, diagnosis, and fix application.

### Functions

#### `capture_error(output: str) -> dict | None`

Parse command output for errors. Returns a dict with `error_type`, `message`, and `traceback` if an error is found.

#### `suggest_fix(error_info: dict) -> str`

Generate a one-sentence fix suggestion using Claude CLI (falls back to pattern matching).

#### `apply_fix(fix: str, file_path: Path) -> bool`

Apply a suggested fix to the specified file.

#### `debug_loop(command: str, max_retries: int = 3) -> bool`

Run a command, detect errors, suggest fixes, apply them, and retry. Returns `True` if the command eventually succeeds.

---

## `core.browser` -- Browser Automation

Headless browser sessions for web interaction.

### Functions

#### `browse_url(url: str) -> str`

Fetch and extract readable text from a URL. Uses Puppeteer MCP when available, falls back to HTTP fetch.

#### `take_screenshot(url: str, output_path: Path) -> Path`

Capture a screenshot of a URL.

#### `generate_pdf(url: str, output_path: Path) -> Path`

Generate a PDF from a web page.

---

## `core.voice` -- Voice Input

Audio transcription and prompt structuring.

### Functions

#### `transcribe_audio(audio_path: Path) -> str`

Transcribe an audio file to text using whisper-cpp or a compatible backend.

#### `detect_language(audio_path: Path) -> str`

Detect the language of an audio file.

#### `structure_prompt(raw_text: str) -> str`

Convert raw transcribed text into a structured research prompt.

---

## `core.mobile` -- Mobile Access

HTTPS API server for phone-based control of research projects. Uses only standard library modules (`http.server`, `ssl`, `hashlib`, `threading`).

### `TLSManager`

```python
class TLSManager:
    def __init__(self, certs_dir: Optional[Path] = None) -> None: ...
    def ensure_certs(self) -> None: ...
    def generate_certs(self) -> None: ...
    def fingerprint(self) -> str: ...
    def create_ssl_context(self) -> ssl.SSLContext: ...
```

Manages self-signed TLS certificates via the `openssl` CLI. Certificates are stored in `~/.ricet/certs/`. Key file permissions are restricted to `0600`.

### `MobileAuth`

```python
class MobileAuth:
    def __init__(self, tokens_file: Optional[Path] = None) -> None: ...
    def generate_token(self, label: str = "") -> str: ...
    def validate(self, token: str, client_ip: str = "") -> bool: ...
    def revoke(self, hash_prefix: str) -> bool: ...
    def list_tokens(self) -> list[dict]: ...
```

Bearer token authentication with persistent SHA-256 hash storage (`~/.ricet/mobile_tokens.json`). Includes per-IP rate limiting: 10 failures triggers a 15-minute lockout.

### `ProjectRegistry`

```python
class ProjectRegistry:
    def __init__(self, projects_file: Optional[Path] = None) -> None: ...
    def list_projects(self) -> list[dict]: ...
    def get_project(self, name: str) -> Optional[dict]: ...
    def get_project_status(self, name: str) -> dict: ...
```

Reads the global project list from `~/.ricet/projects.json` and returns project status including `PROGRESS.md` content and recent sessions.

### `MobileServer`

```python
class MobileServer:
    def __init__(self, auth=None, registry=None, tls_manager=None) -> None: ...
    def dispatch(self, method, path, body=None, *, headers=None, query_params=None, client_ip="") -> dict: ...
```

Route-based HTTP dispatch with 9 default endpoints. Authentication is enforced for all routes except PWA asset routes (`/`, `/manifest.json`, `/sw.js`, `/icon.svg`). All responses are JSON formatted for mobile display (strings truncated to 280 characters).

### Module-Level Functions

#### `start_server(host="0.0.0.0", port=8777, auth=None, tls=True, tls_manager=None) -> threading.Thread`

Start the mobile API server in a daemon thread. Returns the thread handle.

#### `stop_server() -> None`

Shut down the running mobile API server.

#### `is_server_running() -> bool`

Return True if the mobile server thread is alive.

#### `generate_mobile_url(host="0.0.0.0", port=8777, auth=None, tls=True) -> str`

Generate a URL for mobile access, embedding a fresh auth token.

#### `generate_qr_terminal(url: str) -> str`

Generate a QR code for the terminal using `qrencode` if available. Falls back to plain URL text.

### CLI Adapter

```python
from core.mobile import mobile_server

mobile_server.serve(host, port, tls)  # Start HTTPS server
mobile_server.stop()                   # Stop server
mobile_server.pair(label)              # Generate token + QR code
mobile_server.connect_info()           # Print connection methods
mobile_server.tokens()                 # List active tokens
mobile_server.cert_regen()             # Regenerate TLS certs
mobile_server.status()                 # Server status dict
```

---

## `core.mobile_pwa` -- PWA Assets

Static HTML/CSS/JS constants served by the mobile server. No imports, no logic.

### Constants

- `PWA_HTML` -- Full single-page application with Dashboard, Tasks, Voice, and Settings tabs.
- `MANIFEST_JSON` -- PWA manifest for standalone display mode.
- `SERVICE_WORKER_JS` -- Cache-first for app shell, network-first for API routes.
- `ICON_SVG` -- Scalable app icon.

---

## `core.social_media` -- Social Media Publishing

Draft, validate, and publish to Medium, LinkedIn, and Twitter/X.

### `PostDraft`

```python
@dataclass
class PostDraft:
    platform: str           # "medium", "linkedin", "twitter"
    body: str
    title: str = ""
    tags: list[str] = field(default_factory=list)
    link: str = ""
    char_count: int = 0
    ready: bool = False
```

### Constants

```python
CHAR_LIMITS = {"twitter": 280, "linkedin": 3000, "medium": 100_000}
MEDIUM_MAX_TAGS = 5
```

### Functions

#### `draft_medium_post(title: str, content: str, tags: list[str]) -> dict`

Prepare a Medium article draft in markdown format. Tags trimmed to 5 maximum.

#### `draft_linkedin_post(content: str, link: str = "") -> dict`

Prepare a LinkedIn post with optional link attachment.

#### `draft_twitter_post(content: str) -> dict`

Prepare a tweet, truncated to 280 characters.

#### `validate_post(draft: PostDraft) -> list[str]`

Validate a draft against platform constraints. Returns a list of issues (empty = valid).

#### `publish_medium(draft: PostDraft, token: str) -> dict`

Publish to Medium via their API. Requires a Medium integration token.

#### `publish_linkedin(draft: PostDraft, access_token: str) -> dict`

Publish to LinkedIn via their API. Requires an OAuth2 access token.

---

## `core.doability` -- Task Feasibility

Assess whether a task is feasible before committing resources.

### Functions

#### `assess_doability(task: str) -> dict`

Analyze a task description and return a feasibility assessment with score (0-100), risk factors, and recommendations. Uses Claude CLI when available.

---

## `core.prompt_suggestions` -- Prompt Suggestions

AI-powered next-step recommendations.

### Functions

#### `suggest_next_steps(context: str) -> list[str]`

Analyze current project context and suggest the next 3-5 research steps. Uses Claude CLI when available, falls back to template suggestions.

---

## `core.rag_mcp` -- RAG MCP Index

Searchable index of MCP servers for discovery and suggestion.

### `MCPEntry`

```python
@dataclass
class MCPEntry:
    name: str
    description: str
    category: str
    keywords: list[str]
    install_command: str
    config_template: dict[str, Any]
    url: str
```

### `MCPIndex`

```python
class MCPIndex:
    def build_index(self, entries: list[MCPEntry]) -> None: ...
    def search(self, query: str, top_k: int = 5) -> list[MCPEntry]: ...
    def suggest_mcps(self, task_description: str) -> list[MCPEntry]: ...
    def save_to_json(self, path: Path) -> None: ...
    def load_from_json(self, path: Path) -> None: ...
    def install_suggested(self, entries: list[MCPEntry]) -> dict[str, bool]: ...
```

---

## `core.devops` -- Infrastructure Management

Docker builds, CI/CD setup, and secrets management.

### Functions

#### `check_infrastructure() -> dict`

Verify Docker, CI, and dependency status.

#### `build_docker_image(tag: str = "ricet:latest") -> bool`

Build the project Docker image.

#### `manage_secrets(action: str) -> dict`

Manage project secrets (list, add, remove).

#### `setup_ci(provider: str = "github") -> bool`

Generate or update CI workflow files.

---

## `core.website` -- Website Builder

GitHub Pages site generation and deployment.

### Functions

#### `init_website(project_path: Path) -> bool`

Scaffold a MkDocs site with Material theme.

#### `build_website(project_path: Path) -> bool`

Build the static site.

#### `deploy_website(project_path: Path) -> bool`

Deploy to GitHub Pages.

---

## `core.git_worktrees` -- Git Worktree Management

Parallel branch management using git worktrees.

### Functions

#### `add_worktree(branch: str, path: Path | None = None) -> Path`

Create a new git worktree for a branch.

#### `list_worktrees() -> list[dict]`

List all active worktrees.

#### `remove_worktree(branch: str) -> bool`

Remove a worktree.

---

## `core.two_repo` -- Dual-Repository Structure

Manage experiments/ vs clean/ separation.

### Functions

#### `init_two_repo(project_path: Path) -> bool`

Set up the dual-repo directory structure.

#### `promote(source: str, target: str = "clean") -> bool`

Promote validated code from experiments/ to clean/.

#### `status() -> dict`

Show what is in each side of the dual-repo.

---

## `core.prompt_queue` -- Task Queue

Queue management for batch task execution.

### Functions

#### `add_task(description: str) -> str`

Add a task to the queue. Returns task ID.

#### `list_tasks() -> list[dict]`

List all queued tasks.

#### `run_queue() -> list[dict]`

Execute all queued tasks sequentially.

#### `clear_queue() -> int`

Clear all tasks from the queue.

---

## `core.task_spooler` -- Background Task Execution

Background execution of spooled tasks.

### Functions

#### `spool_task(command: str) -> str`

Add a task to the background spooler.

#### `get_task_status(task_id: str) -> dict`

Check the status of a spooled task.

#### `list_spooled() -> list[dict]`

List all spooled tasks with their status.

---

## `core.lazy_mcp` -- Lazy MCP Loading

Deferred loading of MCP servers to reduce startup time.

### Functions

#### `lazy_load(tier: str) -> dict`

Load an MCP tier on demand (only when first needed).

#### `is_loaded(tier: str) -> bool`

Check if a tier has been loaded.

---

## `core.multi_project` -- Project Workspace

Multi-project management from a single workspace.

### Functions

#### `register_project(name: str, path: Path) -> dict`

Register a project in the global workspace.

#### `list_projects() -> list[dict]`

List all registered ricet projects.

#### `switch_project(name: str) -> Path`

Switch the active project context.

---

## `core.markdown_commands` -- Markdown Command Parsing

Parse and execute code blocks from markdown files.

### Functions

#### `parse_commands(md_path: Path) -> list[dict]`

Extract fenced code blocks from a markdown file.

#### `execute_commands(commands: list[dict]) -> list[dict]`

Execute extracted commands sequentially, reporting pass/fail for each.
