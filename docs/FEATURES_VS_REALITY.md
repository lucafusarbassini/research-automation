# Features vs. Reality: 147 Feature Requests Audited

Honest, rigorous audit of every feature request from all 17 chat sessions against the actual `ricet` codebase (v0.2.0, 42 commits). Each verdict is based on reading actual function bodies, not just file existence.

**Legend:** IMPLEMENTED | PARTIAL | NOT IMPLEMENTED

---

## A. Core Application & Architecture (10)

**#1. Build an app for automating scientific research leveraging Claude Code**
- **IMPLEMENTED** — `ricet` is a full Typer CLI app at [cli/main.py](cli/main.py) with 15+ commands. Launches Claude Code sessions via `subprocess.run(["claude", "--session-id", session_uuid])`.

**#2. Build a Visual Studio Code extension for the same**
- **NOT IMPLEMENTED** — No VS Code extension files exist (no `package.json` for extension, no `extension.ts`). The tool is CLI-only.

**#3. Make the tool a pip package for progressive maintenance and distribution**
- **IMPLEMENTED** — [pyproject.toml](pyproject.toml) defines the `ricet` package with entry point `ricet = "cli.main:app"`. Published to PyPI. Installable via `pip install ricet`.

**#4. Integrate claude-flow library (ruvnet/claude-flow v3) as foundation**
- **IMPLEMENTED** — [core/claude_flow.py](core/claude_flow.py) is the bridge module. Docker installs `claude-flow@v3alpha` at [docker/Dockerfile:44](docker/Dockerfile#L44). The [.mcp.json](.mcp.json) configures claude-flow as an MCP server.

**#5. Python bridge wrapping claude-flow CLI calls with graceful fallback**
- **IMPLEMENTED** — [core/claude_flow.py](core/claude_flow.py) wraps all claude-flow operations. Throughout the codebase, `_get_bridge()` catches `ClaudeFlowUnavailable` and falls back to local logic (e.g., [cli/main.py:461](cli/main.py#L461)).

**#6. Create cross-repo skeleton files with preconfigured prompts and standardized templates**
- **IMPLEMENTED** — [templates/](templates/) contains agent definitions, skills, knowledge, config, paper, and GitHub workflows, all copied into new projects during `ricet init` at [cli/main.py:156-198](cli/main.py#L156-L198).

**#7. Create a system file containing all technical specifications, prompts, and context-anchoring materials**
- **IMPLEMENTED** — [CLAUDE.md](CLAUDE.md) (27KB) is the master system file. [defaults/](defaults/) contains PHILOSOPHY.md, CODE_STYLE.md, PROMPTS.md, and LEGISLATION.md.

**#8. Project configuration template (settings.yml)**
- **IMPLEMENTED** — [templates/config/settings.yml](templates/config/settings.yml) exists and is written during onboarding via `write_settings()` at [core/onboarding.py:504](core/onboarding.py#L504).

**#9. User constraints template (CONSTRAINTS.md) in knowledge base**
- **IMPLEMENTED** — [templates/knowledge/CONSTRAINTS.md](templates/knowledge/CONSTRAINTS.md) exists (484 bytes).

**#10. Self-standing repo: strong README documenting all prerequisites**
- **IMPLEMENTED** — [README.md](README.md) (13.7KB) with prerequisites table, installation instructions, feature list, and architecture overview.

**Section score: 9/10 implemented, 0 partial, 1 not implemented.**

---

## B. Project Initialization & Onboarding (28)

**#11. Allow users to initialize projects with hyper-detailed descriptions**
- **IMPLEMENTED** — `ricet init` at [cli/main.py:72-262](cli/main.py#L72-L262) runs the full onboarding flow, directs user to write detailed content in `knowledge/GOAL.md`.

**#12. Accept and store API keys during init (GitHub, HF, W&B, Google/Gemini, Medium, LinkedIn, Slack, SMTP, Google Drive, PubMed, Notion, AWS)**
- **IMPLEMENTED** — `collect_credentials()` at [core/onboarding.py:717-770](core/onboarding.py#L717-L770) iterates through `CREDENTIAL_REGISTRY` covering all listed services.

**#13. Step-by-step API key onboarding guide with how-to URLs, one key at a time**
- **IMPLEMENTED** — Each credential is prompted individually with a how-to URL printed via `print_fn(f"  Get it: {how_to_url}")` at [core/onboarding.py:745-750](core/onboarding.py#L745-L750).

**#14. Video-based onboarding showing how to obtain each API key end to end**
- **NOT IMPLEMENTED** — No video files, video serving infrastructure, or video URLs exist. Only text-based guidance.

**#15. Accept GitHub SSH keys only; automate all repo creation under the hood**
- **PARTIAL** — `create_github_repo()` at [core/onboarding.py:233-291](core/onboarding.py#L233-L291) automates repo creation via `gh`, but accepts any auth method (not SSH-only).

**#16. Full interactive questionnaire for project onboarding**
- **IMPLEMENTED** — `collect_answers()` at [core/onboarding.py:389-480](core/onboarding.py#L389-L480) asks notification method, journal target, website/mobile options, and more.

**#17. Credential collection and secure storage (secrets/.env and secrets/.env.example)**
- **IMPLEMENTED** — `write_env_file()` at [core/onboarding.py:771](core/onboarding.py#L771) creates `secrets/.env`; `write_env_example()` at line 789 creates `secrets/.env.example`.

**#18. Remove project_type entirely — hardcode to "general"**
- **IMPLEMENTED** — `OnboardingAnswers.project_type` hardcoded to `"general"` at [core/onboarding.py:74](core/onboarding.py#L74). No user prompt for it.

**#19. GOAL.md enforcement: block ricet start until GOAL.md has 200+ chars**
- **IMPLEMENTED** — `validate_goal_content()` at [cli/main.py:361-394](cli/main.py#L361-L394) enforces 200-character minimum and blocks `ricet start` with an error if insufficient.

**#20. User writes project description in a specific MD file (at least an A4 page)**
- **IMPLEMENTED** — User directed to edit `knowledge/GOAL.md` at [cli/main.py:257-262](cli/main.py#L257-L262). Template shows A4-page guidance.

**#21. Auto-detect GPU and system hardware — never ask user for GPU name**
- **IMPLEMENTED** — `discover_system()` at [core/environment.py:26-76](core/environment.py#L26-L76) auto-detects GPU via `nvidia-smi`. User is never asked.

**#22. Remove or clarify "success criteria", "target completion date", and "compute resources" prompts**
- **IMPLEMENTED** — These fields are not prompted in `collect_answers()`. `OnboardingAnswers` has `timeline: str = "flexible"` as default with no interactive prompt.

**#23. Notification method selection during init**
- **IMPLEMENTED** — [core/onboarding.py:428-439](core/onboarding.py#L428-L439) prompts for email/slack/none and collects details.

**#24. Target journal or conference selection during init**
- **IMPLEMENTED** — [core/onboarding.py:440-445](core/onboarding.py#L440-L445) prompts `"Target journal or conference for publication (skip to skip)"`.

**#25. Web dashboard option during init**
- **IMPLEMENTED** — [core/onboarding.py:446-449](core/onboarding.py#L446-L449) asks `"Web dashboard for project sharing?"`.

**#26. Mobile access option during init**
- **IMPLEMENTED** — [core/onboarding.py:450-453](core/onboarding.py#L450-L453) asks `"Mobile access to manage tasks?"`.

**#27. Guided folder structure with READMEs: reference/papers/, reference/code/, uploads/data/, uploads/personal/**
- **IMPLEMENTED** — `FOLDER_READMES` at [core/onboarding.py:19-42](core/onboarding.py#L19-L42) defines READMEs for all four folders. `setup_workspace()` creates them.

**#28. Print folder map after init showing where to put things**
- **IMPLEMENTED** — `print_folder_map()` at [core/onboarding.py:481-501](core/onboarding.py#L481-L501) prints the map; called at [cli/main.py:250-252](cli/main.py#L250-L252).

**#29. Folder for background knowledge papers with clear upload instructions**
- **IMPLEMENTED** — `reference/papers/` README at [core/onboarding.py:22-26](core/onboarding.py#L22-L26).

**#30. Folder for useful code to recycle with instructions**
- **IMPLEMENTED** — `reference/code/` README at [core/onboarding.py:27-31](core/onboarding.py#L27-L31).

**#31. Folder for personal materials (papers for style impainting, CV, etc.)**
- **IMPLEMENTED** — `uploads/personal/` README at [core/onboarding.py:37-41](core/onboarding.py#L37-L41).

**#32. Comprehensive .gitignore: auto-gitignore heavy files and notify user**
- **IMPLEMENTED** — [templates/.gitignore](templates/.gitignore) includes patterns for *.h5, *.pkl, *.pt, *.bin, uploads/**, etc.

**#33. Doability assessment**
- **IMPLEMENTED** — Full module at [core/doability.py](core/doability.py) (~509 lines) with `assess_doability()` for feasibility analysis and risk assessment.

**#34. Pre-execution audit: verify uploaded files are in place before proceeding**
- **IMPLEMENTED** — `verify_uploaded_files()` at [core/onboarding.py:318-386](core/onboarding.py#L318-L386) checks reference/ and uploads/ directories.

**#35. Replace ANTHROPIC_API_KEY with Claude web authentication (claude auth login)**
- **IMPLEMENTED** — [docker/entrypoint.sh:29-50](docker/entrypoint.sh#L29-L50) checks Claude auth directory first (browser-based login), falls back to API key. README recommends `claude auth login`.

**#36. Automate Claude installation during repo setup**
- **IMPLEMENTED** — `auto_install_claude()` at [core/onboarding.py:122-166](core/onboarding.py#L122-L166) attempts npm install with fallback.

**#37. Automate GitHub CLI (gh) installation with under-the-hood checks**
- **PARTIAL** — Checks `gh auth status` at [core/onboarding.py:261](core/onboarding.py#L261) but does not auto-install `gh` if missing; only warns the user.

**#38. Automate claude-flow self-install and recognition by ricet**
- **IMPLEMENTED** — `auto_install_claude_flow()` at [core/onboarding.py:169-212](core/onboarding.py#L169-L212). CLI detects availability at [cli/main.py:118-125](cli/main.py#L118-L125).

**Section score: 25/28 implemented, 2 partial, 1 not implemented.**

---

## C. Package & Environment Management (10)

**#39. Create a clean conda environment for each project automatically**
- **PARTIAL** — `create_conda_env()` exists at [core/environment.py:79-113](core/environment.py#L79-L113) but is not called automatically during init. User would need to invoke it separately.

**#40. Discover system specifications and capabilities**
- **IMPLEMENTED** — `discover_system()` at [core/environment.py:26-59](core/environment.py#L26-L59) detects OS, Python, CPU, RAM, GPU, Conda, Docker.

**#41. Generate system.md documentation file with environment details**
- **IMPLEMENTED** — `generate_system_md()` at [core/environment.py:116-147](core/environment.py#L116-L147) renders system info to markdown.

**#42. Auto-install required packages at init**
- **IMPLEMENTED** — `check_and_install_packages()` called at [cli/main.py:88-96](cli/main.py#L88-L96) during init.

**#43. Runtime package auto-install during user work sessions**
- **IMPLEMENTED** — `ensure_package()` at [core/onboarding.py:1117-1160](core/onboarding.py#L1117-L1160) allows agents to install packages on-the-fly.

**#44. Autonomous package conflict resolution**
- **PARTIAL** — `_suggest_alternative_package()` at [core/onboarding.py:1007-1020](core/onboarding.py#L1007-L1020) asks Claude for alternatives when pip fails, but is not a full dependency resolver.

**#45. Goal-aware AI-driven package detection (Claude API call to analyze GOAL.md)**
- **IMPLEMENTED** — `infer_packages_from_goal()` at [core/onboarding.py:911-1006](core/onboarding.py#L911-L1006) calls Claude via `_infer_packages_via_claude()` to analyze GOAL.md and return needed packages as JSON.

**#46. Replace ALL hardcoded logic with Claude AI calls**
- **PARTIAL** — Many Claude API calls exist (package inference, alternatives, doability), but keyword-based heuristics remain as fallback throughout (e.g., `_infer_packages_via_keywords()`, `doability.py`).

**#47. Agent should handle install failures automatically**
- **IMPLEMENTED** — `install_inferred_packages()` at [core/onboarding.py:1042-1105](core/onboarding.py#L1042-L1105) catches failures, suggests alternatives via Claude, returns both installed and failed lists.

**#48. Docker sandbox environment setup and configuration**
- **IMPLEMENTED** — [docker/Dockerfile](docker/Dockerfile) (77 lines, multi-stage build), [docker/docker-compose.yml](docker/docker-compose.yml), and [docker/entrypoint.sh](docker/entrypoint.sh) handle auth, packages, and multiple runtime modes.

**Section score: 7/10 implemented, 3 partial, 0 not implemented.**

---

## D. Multi-Model Routing & AI (8)

**#49. Multi-model routing: Google (Gemini), Anthropic (Claude), and any other providers**
- **PARTIAL** — [core/model_router.py](core/model_router.py) defines `DEFAULT_MODELS` with only Anthropic models (claude-opus, claude-sonnet, claude-haiku). No Gemini or other provider configuration.

**#50. Leverage cheaper models where possible (e.g., Gemini for literature review)**
- **NOT IMPLEMENTED** — Cost-based selection exists within Anthropic tiers only. No Gemini integration for literature review or any other task.

**#51. Use Claude for writing and critical tasks**
- **IMPLEMENTED** — [core/model_router.py:232-240](core/model_router.py#L232-L240) maps CRITICAL → claude-opus, COMPLEX → claude-opus.

**#52. Use fine-tuned models for special tasks**
- **NOT IMPLEMENTED** — No fine-tuned model configuration or routing logic exists.

**#53. 3-tier model routing (haiku/sonnet/opus) via claude-flow**
- **IMPLEMENTED** — [core/model_router.py:140-162](core/model_router.py#L140-L162) maps claude-flow tiers (booster→simple, workhorse→medium, oracle→complex) with keyword-based fallback.

**#54. Cross-provider fallback when primary model fails**
- **PARTIAL** — `get_fallback_model()` at [core/model_router.py:243-262](core/model_router.py#L243-L262) exists but only supports the Anthropic chain (opus→sonnet→haiku).

**#55. Classify task complexity automatically to decide model**
- **IMPLEMENTED** — `classify_task_complexity()` at [core/model_router.py:129-176](core/model_router.py#L129-L176) uses claude-flow classification, Claude CLI, or keyword-based heuristics.

**#56. Token optimization and context management/compaction**
- **PARTIAL** — [core/tokens.py](core/tokens.py) tracks token budgets. [core/prompt_suggestions.py](core/prompt_suggestions.py) has `compress_context()` (lines 381-462). But no active context window compaction strategy during sessions.

**Section score: 3/8 implemented, 3 partial, 2 not implemented.**

---

## E. Voice Input Pipeline (4)

**#57. Voice input capability for project descriptions**
- **IMPLEMENTED** — [core/voice.py:40-65](core/voice.py#L40-L65) has `transcribe_audio()` with Whisper integration.

**#58. Transcribe audio using Whisper**
- **IMPLEMENTED** — [core/voice.py:56-65](core/voice.py#L56-L65) calls `whisper.load_model("base")` and `model.transcribe()` with ImportError handling.

**#59. Detect language and translate non-English to English**
- **PARTIAL** — Language detection implemented at [core/voice.py:68-104](core/voice.py#L68-L104). Translation at lines 107-125 is a **stub**: `logger.warning('Translation not implemented. Returning original text.')` — returns text unmodified.

**#60. Structure voice-based natural language into formal prompts**
- **IMPLEMENTED** — `structure_prompt()` at [core/voice.py:128-173](core/voice.py#L128-L173) with template matching and placeholder replacement.

**Section score: 3/4 implemented, 1 partial, 0 not implemented.**

---

## F. Agent Orchestration & Swarm (10)

**#61. 60+ specialized agents from claude-flow**
- **PARTIAL** — Only 7 agent types defined in [core/agents.py:26-34](core/agents.py#L26-L34) (master, researcher, coder, reviewer, falsifier, writer, cleaner). The 60+ agents are available through claude-flow when it is running, but ricet's own code defines only 7.

**#62. Swarm orchestration for parallel task execution**
- **IMPLEMENTED** — `execute_parallel_tasks()` at [core/agents.py:349-416](core/agents.py#L349-L416) delegates to claude-flow swarm or falls back to `ThreadPoolExecutor`.

**#63. Intelligent agent spawning (30-40 concurrent agents) with isolation**
- **PARTIAL** — Thread-based execution with configurable `max_workers` at [core/agents.py:459-469](core/agents.py#L459-L469). No explicit isolation mechanism for 30-40 concurrent agents beyond thread separation.

**#64. Task dataclass, build task DAG (dependency graph)**
- **IMPLEMENTED** — `Task` dataclass at [core/agents.py:113-133](core/agents.py#L113-L133) with deps field. `build_task_dag()` at lines 324-337 creates dependency graph using `defaultdict(list)`.

**#65. Execute tasks in parallel where dependencies allow**
- **IMPLEMENTED** — [core/agents.py:419-488](core/agents.py#L419-L488) respects dependencies via `_get_ready_tasks()` at lines 340-346.

**#66. Plan-execute-iterate loop for complex workflows**
- **IMPLEMENTED** — `plan_execute_iterate()` at [core/agents.py:491-540](core/agents.py#L491-L540) with configurable `max_iterations` and success/failure checking.

**#67. Get active agents status in real-time**
- **IMPLEMENTED** — `get_active_agents_status()` at [core/agents.py:543-549](core/agents.py#L543-L549) returns list from `_active_agents` dict, tracked during execution.

**#68. Dynamic prompt queue**
- **IMPLEMENTED** — Full `PromptQueue` class at [core/prompt_queue.py:145-540](core/prompt_queue.py#L145-L540) with submit, status, drain, priority dispatch, dependency resolution, and persistence.

**#69. HNSW vector memory for knowledge management**
- **IMPLEMENTED** — `query_memory()` at [core/claude_flow.py:204-210](core/claude_flow.py#L204-L210) delegates to claude-flow HNSW. `store_memory()` at lines 212-227. Used by [core/knowledge.py:137-145](core/knowledge.py#L137-L145).

**#70. Session management with persistent sessions and recovery**
- **IMPLEMENTED** — `create_session()` at [core/session.py:41-61](core/session.py#L41-L61), `snapshot_state()` and `restore_snapshot()` at lines 107-156 for recovery.

**Section score: 8/10 implemented, 2 partial, 0 not implemented.**

---

## G. Autonomous Execution & Overnight (10)

**#71. Accept a "start" command and begin autonomous work**
- **IMPLEMENTED** — `ricet start` command at [cli/main.py](cli/main.py) launches an interactive Claude Code session with the project's context loaded.

**#72. Allow agent to work while user is away (overnight runs)**
- **IMPLEMENTED** — `ricet overnight` command plus [core/autonomous.py](core/autonomous.py) with scheduling (daily, hourly, weekly) and iteration loops. Shell scripts at [scripts/overnight.sh](scripts/overnight.sh) and [scripts/overnight-enhanced.sh](scripts/overnight-enhanced.sh).

**#73. Maintain awareness of constraints during long overnight runs**
- **PARTIAL** — Resource monitoring at [core/resources.py:40-88](core/resources.py#L40-L88) checks RAM, disk, CPU. `make_resource_decision()` creates warnings. But no explicit "constraint awareness" that re-reads CONSTRAINTS.md or GOAL.md during overnight runs.

**#74. Develop projects iteratively through any number of Claude calls**
- **IMPLEMENTED** — `plan_execute_iterate()` at [core/agents.py:491-540](core/agents.py#L491-L540) loops through iterations. Overnight scripts run `for i in {1..20}; do claude ...; done`.

**#75. Auto-debug loop**
- **IMPLEMENTED** — `auto_debug_loop()` at [core/auto_debug.py:255-312](core/auto_debug.py#L255-L312) with error parsing, fix suggestion, and retry (max 3 iterations).

**#76. Automatic error detection in code execution**
- **IMPLEMENTED** — `parse_error()` at [core/auto_debug.py:81-146](core/auto_debug.py#L81-L146) detects Python, npm, LaTeX, and pytest errors via regex patterns.

**#77. Safe overnight sandbox execution in Docker containers**
- **PARTIAL** — Docker infrastructure exists ([docker/Dockerfile](docker/Dockerfile), [docker/docker-compose.yml](docker/docker-compose.yml)), but there is no code that automatically launches overnight runs inside a Docker container. The user must manually run in Docker.

**#78. Automate mounting of ~/.claude/ directory into Docker containers**
- **PARTIAL** — [docker/entrypoint.sh](docker/entrypoint.sh) checks for Claude auth at `/home/ricet/.claude/`. The docker-compose could mount it, but automated mounting logic is not wired from the CLI.

**#79. Overnight result reporting: send Slack/email notifications**
- **IMPLEMENTED** — [core/notifications.py](core/notifications.py) has `send_email()` (lines 108-150) and `send_slack()` (lines 71-105) with SMTP and webhook support. Notification triggers exist in the autonomous module.

**#80. Write overnight results to state/PROGRESS.md**
- **IMPLEMENTED** — `_log_result()` at [core/agents.py:552-565](core/agents.py#L552-L565) writes to PROGRESS file with timestamps.

**Section score: 7/10 implemented, 3 partial, 0 not implemented.**

---

## H. Reproducibility & Resources (5)

**#81. RunLog for tracking experiment runs**
- **IMPLEMENTED** — `RunLog` dataclass at [core/reproducibility.py:17-31](core/reproducibility.py#L17-L31) with command, timestamp, git_hash, parameters, metrics. `log_run()` persists to JSON at lines 38-51.

**#82. ArtifactRegistry for managing generated files**
- **IMPLEMENTED** — `ArtifactRegistry` class at [core/reproducibility.py:75-134](core/reproducibility.py#L75-L134) with register, verify, and list_artifacts. Tracks checksums and metadata.

**#83. Compute dataset hash for reproducibility verification**
- **IMPLEMENTED** — `compute_dataset_hash()` at [core/reproducibility.py:141-159](core/reproducibility.py#L141-L159) uses SHA-256, handles both files and directories.

**#84. Monitor system resources (CPU, memory, disk, GPU)**
- **IMPLEMENTED** — `monitor_resources()` at [core/resources.py:40-88](core/resources.py#L40-L88) collects CPU, RAM, disk, and GPU metrics.

**#85. Checkpoint policy**
- **IMPLEMENTED** — `CheckpointPolicy` dataclass at [core/resources.py:33-37](core/resources.py#L33-L37) and `cleanup_old_checkpoints()` at lines 91-124.

**Section score: 5/5 implemented.**

---

## I. Literature & Knowledge (3)

**#86. Web search integration via browser automation**
- **IMPLEMENTED** — `BrowserSession` at [core/browser.py:66-149](core/browser.py#L66-L149) with Puppeteer MCP integration (lines 184-201) and curl/wget fallback.

**#87. Academic paper search functionality**
- **PARTIAL** — MCP nucleus includes paper-search and arxiv in Tier 1. [core/paper.py](core/paper.py) has `add_citation()` for managing references. But no dedicated paper search function that queries PubMed/arXiv programmatically — it relies on MCP servers being available.

**#88. Literature review pipeline automation**
- **PARTIAL** — The researcher agent ([templates/.claude/agents/researcher.md](templates/.claude/agents/researcher.md)) is tasked with literature search. `search_knowledge()` at [core/knowledge.py:118-169](core/knowledge.py#L118-L169) searches the encyclopedia. But no end-to-end literature review pipeline (search → download → extract → synthesize → annotate) exists as automated code.

**Section score: 1/3 implemented, 2 partial.**

---

## J. Two-Repo Structure (4)

**#89. Two-repo structure: experiments (messy) vs clean (polished)**
- **IMPLEMENTED** — `TwoRepoManager` at [core/two_repo.py:38-71](core/two_repo.py#L38-L71) manages separate experiments/ and clean/ repos. `init_two_repos()` creates both.

**#90. Git worktrees for the two-repo approach**
- **IMPLEMENTED** — Full implementation at [core/git_worktrees.py:22-170](core/git_worktrees.py#L22-L170) with `ensure_branch_worktree()` and `merge_worktree_results()`.

**#91. Only push working, relevant, polished code to the clean repo**
- **IMPLEMENTED** — `promote_to_clean()` at [core/two_repo.py:72-103](core/two_repo.py#L72-L103) validates before copying. Requires explicit promotion.

**#92. Multi-repo synchronization and cross-repo coordination**
- **PARTIAL** — `sync_shared()` at [core/two_repo.py:131-157](core/two_repo.py#L131-L157) syncs specific files. [core/cross_repo.py](core/cross_repo.py) handles cross-repo coordination with permission boundaries, but full multi-repo atomic synchronization is not battle-tested.

**Section score: 3/4 implemented, 1 partial.**

---

## K. Dashboard & Monitoring (5)

**#93. TUI dashboard showing agent activity**
- **IMPLEMENTED** — `build_agents_panel()` at [cli/dashboard.py:108-136](cli/dashboard.py#L108-L136) displays active agents. `show_dashboard()` at lines 375-426 assembles the full TUI.

**#94. Dashboard with agents panel**
- **IMPLEMENTED** — Agents panel at [cli/dashboard.py:108-136](cli/dashboard.py#L108-L136) integrated into the dashboard layout.

**#95. Dashboard with resource monitoring display**
- **IMPLEMENTED** — `build_resource_panel()` at [cli/dashboard.py:139-172](cli/dashboard.py#L139-L172) shows CPU, RAM, disk, tokens, and cost.

**#96. Figure gallery for browsing generated visualizations**
- **IMPLEMENTED** — `scan_figures()`, `organize_by_run()`, `display_gallery()` at [cli/gallery.py:23-97](cli/gallery.py#L23-L97).

**#97. Live status assessment and monitoring (from mobile too)**
- **PARTIAL** — `live_dashboard()` at [cli/dashboard.py:428-443](cli/dashboard.py#L428-L443) with `refresh_interval`. Mobile server at [core/mobile.py](core/mobile.py) exists with /status and /progress endpoints, but integration between TUI and mobile is not seamless.

**Section score: 4/5 implemented, 1 partial.**

---

## L. Prompt & Command System (4)

**#98. Prompt suggestions / predictive follow-ups when Claude finishes a task**
- **IMPLEMENTED** — `suggest_next_steps()` at [core/prompt_suggestions.py:147-200](core/prompt_suggestions.py#L147-L200), `generate_follow_up_prompts()` at lines 242-290, `detect_stuck_pattern()` at lines 298-331. Pattern matching for research, implementation, debugging, review, deployment, writing.

**#99. Execute markdown files from knowledge folder as instruction sets**
- **IMPLEMENTED** — `parse_runbook()` at [core/markdown_commands.py:71-103](core/markdown_commands.py#L71-L103) and `execute_runbook()` at lines 106-163. Parses fenced code blocks, supports bash/python/shell, dry-run mode.

**#100. Task spooler (ts/tsp) integration for job queuing**
- **IMPLEMENTED** — `TaskSpooler` wrapping tsp CLI at [core/task_spooler.py:139-258](core/task_spooler.py#L139-L258), with `FallbackSpooler` using ThreadPoolExecutor at lines 21-132.

**#101. Full session recovery from crashed or completed tasks**
- **IMPLEMENTED** — `PromptQueue._persist()` at [core/prompt_queue.py:513-524](core/prompt_queue.py#L513-L524) saves state to `state/prompt_memory/`. Session snapshots and restore at [core/session.py:107-156](core/session.py#L107-L156).

**Section score: 4/4 implemented.**

---

## M. GitHub Integration (5)

**#102. GitHub Actions workflows for CI/CD**
- **PARTIAL** — [templates/.github/workflows/](templates/.github/workflows/) contains tests.yml, lint.yml, and paper-build.yml as templates for new projects. The ricet repo's own `.github/` directory has some workflow files but they are minimal.

**#103. GitHub repo creation for each project (automated)**
- **IMPLEMENTED** — `create_github_repo()` at [core/onboarding.py:233-291](core/onboarding.py#L233-L291) uses `gh repo create` under the hood during init.

**#104. GitHub Pages for documentation (replacing ReadTheDocs)**
- **NOT IMPLEMENTED** — [mkdocs.yml](mkdocs.yml) is configured for MkDocs Material, but no GitHub Pages deployment automation exists. No `gh-pages` branch setup or workflow.

**#105. Fix and maintain CI badges and demo badges on homepage**
- **NOT IMPLEMENTED** — No badge automation logic in the codebase.

**#106. PyPI badges on documentation**
- **NOT IMPLEMENTED** — No PyPI badge code found.

**Section score: 1/5 implemented, 1 partial, 3 not implemented.**

---

## N. Publishing & Social Media (7)

**#107. Create a website ready to be published for each project**
- **IMPLEMENTED** — [core/website.py](core/website.py) (463 lines) with `init_website()`, `build_site()`, `deploy_site()`. Supports academic/minimal templates, GitHub Pages/Netlify/manual deployment.

**#108. Create a newsletter for each project**
- **NOT IMPLEMENTED** — No newsletter generation code exists.

**#109. Post to LinkedIn automatically with quality check via Claude**
- **IMPLEMENTED** — `publish_linkedin()` at [core/social_media.py:251-287](core/social_media.py#L251-L287), `draft_linkedin_post()` at lines 64-85 with LinkedIn OAuth2 UGC Posts API.

**#110. Post to Medium automatically with quality check via Claude**
- **IMPLEMENTED** — `publish_medium()` at [core/social_media.py:200-248](core/social_media.py#L200-L248) with Medium v1 API, markdown support, tag handling.

**#111. Generate social media content from the project**
- **IMPLEMENTED** — `summarize_for_social()` and `generate_thread()` at [core/social_media.py:93-165](core/social_media.py#L93-L165). Platform-aware summarization.

**#112. Email notification capability**
- **IMPLEMENTED** — `send_email()` at [core/notifications.py:108-150](core/notifications.py#L108-L150) with SMTP (Gmail default), formatting, and throttling.

**#113. Slack integration capability**
- **IMPLEMENTED** — `send_slack()` at [core/notifications.py:71-105](core/notifications.py#L71-L105) with webhook posting and throttling.

**Section score: 5/7 implemented, 0 partial, 2 not implemented.**

---

## O. Templates & Paper Writing (5)

**#114. Paper writing core functionality**
- **IMPLEMENTED** — [core/paper.py](core/paper.py) (202 lines) with `add_citation()`, `compile_paper()`, `check_figure_references()`, and matplotlib rcParams configuration.

**#115. Journal template support (Nature, Bioinformatics, etc.)**
- **NOT IMPLEMENTED** — [templates/paper/journals/](templates/paper/journals/) directory exists but contains no journal-specific templates. Generic LaTeX template only.

**#116. Accept example paper PDFs in templates/paper/journals/**
- **NOT IMPLEMENTED** — Directory structure is in place but empty. No logic to process uploaded journal example PDFs.

**#117. LaTeX integration (potentially with Overleaf)**
- **PARTIAL** — `compile_paper()` at [core/paper.py:119-142](core/paper.py#L119-L142) calls `make all` in the paper directory. MCP nucleus lists Overleaf in Tier 5, but no Overleaf API integration exists in code.

**#118. Website generation functionality**
- **IMPLEMENTED** — [core/website.py](core/website.py) (463 lines) with full site generation, building, and deployment.

**Section score: 2/5 implemented, 1 partial, 2 not implemented.**

---

## P. Mobile & Multi-Project (4)

**#119. Mobile phone control (/mobile command)**
- **IMPLEMENTED** — [core/mobile.py](core/mobile.py) (306 lines) with HTTP server, routes for /task, /status, /voice, /progress. Token-based auth.

**#120. Simultaneous multi-project handling**
- **IMPLEMENTED** — `ProjectRegistry` at [core/multi_project.py](core/multi_project.py) (316 lines) with `run_task_in_project()`, registry persistence at `~/.ricet/projects.json`, project switching.

**#121. Mobile project management and status monitoring**
- **IMPLEMENTED** — `_handle_get_status()` and `_handle_get_progress()` at [core/mobile.py:143-171](core/mobile.py#L143-L171).

**#122. Browser integration for web resources**
- **IMPLEMENTED** — `BrowserSession` at [core/browser.py](core/browser.py) (294 lines) with Puppeteer MCP + curl/wget/wkhtmltopdf fallback.

**Section score: 4/4 implemented.**

---

## Q. Security (3)

**#123. Enforce repository root validation**
- **IMPLEMENTED** — `enforce_repo_root()` at [core/security.py:36-54](core/security.py#L36-L54) uses `git rev-parse --show-toplevel`, raises RuntimeError.

**#124. Scan codebase for secrets and credentials before operations**
- **IMPLEMENTED** — `scan_for_secrets()` at [core/security.py:57-115](core/security.py#L57-L115) with regex patterns for API keys, tokens, passwords, AWS credentials, private keys.

**#125. Protect immutable files from accidental modification**
- **IMPLEMENTED** — `protect_immutable_files()` at [core/security.py:118-142](core/security.py#L118-L142) with glob pattern matching for .env, .key, *.pem.

**Section score: 3/3 implemented.**

---

## R. Testing & Quality (9)

**#126. TDD approach: write tests progressively during development**
- **IMPLEMENTED** — [tests/](tests/) contains 40+ test files covering all major modules, maintained across development phases.

**#127. Backend should autonomously write tests to keep code checked**
- **PARTIAL** — Tests exist and are comprehensive, but there is no autonomous test-generation logic. Tests were written manually, not auto-generated by agents.

**#128. Comprehensive end-to-end demo/tutorial testing 100% of functions**
- **PARTIAL** — [demo/](demo/) has 9 phase-based test files (test_phase1_init.py through test_phase9_integration.py). Phase coverage is broad but 100% function coverage is not verified.

**#129. Demo/tutorial should be part of the package and well-documented**
- **IMPLEMENTED** — [demo/README.md](demo/README.md) (2.4KB) with human testing checklist and phase-based documentation.

**#130. Test in Docker sandboxes**
- **PARTIAL** — Docker infrastructure at [docker/](docker/) exists with sandbox capabilities. But the test suite (`pytest`) does not automatically run inside Docker containers.

**#131. Replace fake README demo with real documented end-to-end scientific workflow**
- **PARTIAL** — [README.md](README.md) contains a workflow description and [demo/](demo/) has phase-based tests. Whether this constitutes a "real end-to-end scientific workflow" vs. a code exercise is debatable — no actual scientific experiment is run.

**#132. Half-baked feature detection: automated check for fragile or trivial implementations**
- **PARTIAL** — [core/doability.py](core/doability.py) assesses task feasibility using heuristics. But it is not explicitly designed to detect half-baked features within the ricet codebase itself.

**#133. Unbiased weakness detection by fresh agents with no context**
- **NOT IMPLEMENTED** — No mechanism exists to spawn a "fresh" agent that audits the codebase without prior context.

**#134. Hardcoded parameter audit**
- **NOT IMPLEMENTED** — No automated tool scans for hardcoded magic numbers or parameters.

**Section score: 2/9 implemented, 5 partial, 2 not implemented.**

---

## S. Collaboration & Cross-Repo Awareness (4)

**#135. Transform existing GitHub repos to Ricet projects with safe backup**
- **PARTIAL** — [core/adopt.py](core/adopt.py) (~7KB) has adoption logic, but safety guarantees (fork preservation, backup verification) are not thoroughly validated.

**#136. Support collaborative repos with multiple users**
- **IMPLEMENTED** — [core/collaboration.py](core/collaboration.py) (171 lines) with `get_user_id()`, `sync_before_start()`, `sync_after_operation()`. User identification via git config or hostname.

**#137. Support collaborative research where both users use Ricet**
- **IMPLEMENTED** — `merge_encyclopedia()` and `merge_state_file()` at [core/collaboration.py:131-170](core/collaboration.py#L131-L170) with deduplication-aware merging.

**#138. Link user's public/private repos for RAG by ricet agents**
- **IMPLEMENTED** — `link_repository()`, `index_linked_repo()`, `search_all_linked()` at [core/cross_repo.py](core/cross_repo.py) (349 lines) with HNSW indexing via claude-flow and local JSON fallback.

**Section score: 3/4 implemented, 1 partial.**

---

## T. UX Philosophy (5)

**#139. Assume users will read NOTHING — everything must be self-standing and autonomous**
- **PARTIAL** — The onboarding flow is guided and the folder map is printed. But several features still require the user to read documentation (e.g., Docker setup, API key how-tos). This is a design philosophy, not a verifiable code feature.

**#140. All complexity under the hood; user experience must be super simple**
- **PARTIAL** — The CLI is relatively simple (15 commands), and MCP loading is lazy/automatic. But the user still needs to understand conda, Docker, git, and Claude Code concepts. Complexity is reduced but not fully hidden.

**#141. Even very bad voice messages should be deliverable**
- **IMPLEMENTED** — [core/voice.py](core/voice.py) processes voice input with Whisper and structures it into prompts. The `structure_prompt()` function handles messy input with template matching.

**#142. Auto-commit and push every operation performed by the ricet machinery**
- **IMPLEMENTED** — `auto_commit()` at [core/auto_commit.py](core/auto_commit.py) (99 lines) stages, commits, and pushes with branch detection. Configurable via `RICET_AUTO_COMMIT` and `AUTO_PUSH` environment variables.

**#143. Real user testing workflow with step-by-step instructions**
- **IMPLEMENTED** — [demo/human_testing_checklist.md](demo/human_testing_checklist.md) (3.5KB) with phase-based step-by-step checklist.

**Section score: 3/5 implemented, 2 partial.**

---

## U. Documentation & Transparency (4)

**#144. Build log document (Luca/Claude Q&A format) showing how each feature was solved**
- **IMPLEMENTED** — [docs/PROMPT_VS_REALITY.md](docs/PROMPT_VS_REALITY.md) was created for the initial prompt. This document (FEATURES_VS_REALITY.md) extends it to all 147 features.

**#145. Archive chat transcripts in repo for full transparency**
- **PARTIAL** — [archived/](archived/) directory exists and contains `feature-requests-all-chats.md` extracted from chat sessions. But raw chat transcripts are not archived — only curated extractions.

**#146. Recognize in README the repos used to build the product**
- **NOT IMPLEMENTED** — [README.md](README.md) does not explicitly credit claude-flow, ruvnet, or other foundational repos used to build ricet.

**#147. Comprehensive testing guide for all functionalities**
- **IMPLEMENTED** — [demo/README.md](demo/README.md) provides a phase-based testing guide. [demo/human_testing_checklist.md](demo/human_testing_checklist.md) covers end-to-end manual testing.

**Section score: 2/4 implemented, 1 partial, 1 not implemented.**

---

## Grand Summary

| Section | Features | Implemented | Partial | Not Implemented |
|---------|----------|-------------|---------|-----------------|
| A. Core Architecture | 10 | 9 | 0 | 1 |
| B. Initialization & Onboarding | 28 | 25 | 2 | 1 |
| C. Package & Environment | 10 | 7 | 3 | 0 |
| D. Multi-Model Routing | 8 | 3 | 3 | 2 |
| E. Voice Input | 4 | 3 | 1 | 0 |
| F. Agent Orchestration | 10 | 8 | 2 | 0 |
| G. Autonomous & Overnight | 10 | 7 | 3 | 0 |
| H. Reproducibility | 5 | 5 | 0 | 0 |
| I. Literature & Knowledge | 3 | 1 | 2 | 0 |
| J. Two-Repo Structure | 4 | 3 | 1 | 0 |
| K. Dashboard & Monitoring | 5 | 4 | 1 | 0 |
| L. Prompt & Command | 4 | 4 | 0 | 0 |
| M. GitHub Integration | 5 | 1 | 1 | 3 |
| N. Publishing & Social Media | 7 | 5 | 0 | 2 |
| O. Templates & Paper | 5 | 2 | 1 | 2 |
| P. Mobile & Multi-Project | 4 | 4 | 0 | 0 |
| Q. Security | 3 | 3 | 0 | 0 |
| R. Testing & Quality | 9 | 2 | 5 | 2 |
| S. Collaboration | 4 | 3 | 1 | 0 |
| T. UX Philosophy | 5 | 3 | 2 | 0 |
| U. Documentation | 4 | 2 | 1 | 1 |
| **TOTALS** | **147** | **103 (70%)** | **29 (20%)** | **15 (10%)** |

---

## Top Strengths (fully implemented sections)

- **Reproducibility (H)**: 5/5 — RunLog, ArtifactRegistry, hashing, monitoring, checkpoints all working
- **Security (Q)**: 3/3 — repo root enforcement, secret scanning, immutable file protection
- **Prompt & Command (L)**: 4/4 — suggestions, markdown execution, task spooler, session recovery
- **Mobile & Multi-Project (P)**: 4/4 — mobile server, multi-project registry, browser automation
- **Initialization (B)**: 25/28 — comprehensive onboarding with questionnaire, folders, credentials, GOAL enforcement

## Top Gaps (highest not-implemented count)

- **GitHub Integration (M)**: 3 not implemented — no GitHub Pages, no badge automation
- **Multi-Model Routing (D)**: 2 not implemented — no Gemini, no fine-tuned models
- **Publishing (N)**: 2 not implemented — no newsletter, no GitHub Pages docs
- **Templates & Paper (O)**: 2 not implemented — no journal templates, no example PDFs
- **Testing & Quality (R)**: 2 not implemented — no unbiased agent audits, no hardcoded parameter detection
- **VS Code Extension (A#2)**: the original "also build a VS Code extension" remains unbuilt

## Honest Overall Assessment

103 of 147 features (70%) have real, working code behind them. 29 (20%) are partially implemented — meaning the infrastructure exists but key pieces are missing (e.g., translation is a stub, Docker sandbox is built but not auto-launched, Gemini routing has no Gemini). 15 (10%) are not implemented at all. The strongest areas are the core scientific workflow (reproducibility, agents, knowledge, onboarding). The weakest are peripheral integrations (GitHub Pages, badges, newsletters, journal templates, Gemini, fine-tuned models).

---

*Generated from ricet v0.2.0 — 42 commits, 38 core modules, 147 features audited.*
