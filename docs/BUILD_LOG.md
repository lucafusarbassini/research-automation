# Build Log: How Each Request Was Addressed

This document maps every sentence from Luca's initial prompt to what was actually built, what's partial, and what's not yet implemented.

---

**Luca:** I intend to create an app and/or a Visual Studio Code extension that allows the automation of scientific research by fully leveraging the potential of cloud code.

**Claude:** The project is built as a Python CLI tool (`research`) using Typer, not a VS Code extension. It automates research workflows via Claude Code subprocess calls (`cli/main.py`). No VS Code extension has been developed. The CLI is the sole interface.

---

**Luca:** In particular, I would like to build a system that allows a user to initialize and develop a project.

**Claude:** `research init <project-name>` creates a full project from templates. `research start` launches a Claude Code session. `research overnight` runs autonomous iterations. This is implemented in `cli/main.py`.

---

**Luca:** By initialization I mean that the user will provide a hyper-detailed description of a scientific project, together with specific requests for the agent and all the necessary keys.

**Claude:** `core/onboarding.py` implements a multi-step questionnaire: project goal, project type, GitHub repo URL, success criteria, timeline, compute resources, notification preferences. It does not yet collect API keys interactively — the plan stores credential references as `${ENV_VAR}` placeholders in `config/settings.yml`, expecting the user to populate a `.env` file manually.

---

**Luca:** We will discuss this in detail later. For example, the various API keys, GitHub access, and so on.

**Claude:** The `defaults/ONBOARDING.md` spec lists all credential categories (GitHub, HuggingFace, W&B, SendGrid, Slack, AWS, Semantic Scholar). The onboarding code (`core/onboarding.py`) has the structure for credential collection but does not actually prompt for each API key — it only asks for GitHub repo URL and notification credentials. The full credential collection per project type (ML → HuggingFace token, etc.) is specified but not yet wired up.

---

**Luca:** First and foremost, the agent will have to create a repository and organize it appropriately for the project, initialize it, and so on, on the local machine on which it is running.

**Claude:** `cli/main.py:init()` copies the `templates/` directory into a new folder, runs `git init`, `git add -A`, and `git commit -m "Initial project setup"`. The project gets a full directory structure: `.claude/agents/`, `knowledge/`, `paper/`, `config/`, `state/`, plus workspace dirs (`reference/`, `local/`, `secrets/`, `uploads/`).

---

**Luca:** To get started, the user may also upload material that must not be pushed, such as papers for inpainting or useful code to be recycled, specific instructions.

**Claude:** `core/onboarding.py:setup_workspace()` creates `reference/`, `local/`, `secrets/`, and `uploads/` directories with `.gitkeep` files. The `templates/.gitignore` excludes `secrets/`, `uploads/`, `local/`, heavy model files (`.pt`, `.h5`, `.safetensors`, etc.), and data directories. However, there is no interactive file-upload flow — the user must manually place files into these directories.

---

**Luca:** The initialization of the repository will also contain various materials: first of all a properly configured gitignore to avoid all heavy files, and so on.

**Claude:** `templates/.gitignore` is comprehensive: it excludes secrets (`.env`, `*.pem`, `credentials.json`), Python artifacts (`__pycache__`, `.egg-info`), heavy ML files (`.h5`, `.pkl`, `.pt`, `.ckpt`, `.safetensors`, `.parquet`), LaTeX build artifacts, IDE files, OS files, state snapshots, and local workspace directories.

---

**Luca:** As well as a series of useful files that we will now develop and that will be cross-repo, meaning they will essentially be the solid skeleton of this entire project, for example with preconfigured prompts and so on.

**Claude:** The `templates/` directory contains: 7 agent definition files (`.claude/agents/*.md`), 3 skill files (`.claude/skills/*.md`), a progressive instruction protocol (`.claude/CLAUDE.md`), knowledge templates (`GOAL.md`, `ENCYCLOPEDIA.md`, `CONSTRAINTS.md`), a LaTeX paper template (`paper/main.tex`, `Makefile`, `references.bib`), MCP configuration (`config/mcp-nucleus.json` with 70+ MCPs across 8 tiers), project settings (`config/settings.yml`), and GitHub CI workflows. The `defaults/` directory contains `PROMPTS.md` (a collection of structured prompts for literature review, code writing, data analysis, ML, paper writing, validation, maintenance), `PHILOSOPHY.md`, `CODE_STYLE.md`, `LEGISLATION.md`, and `ONBOARDING.md`. These are designed to be copied into every new project.

---

**Luca:** This is to give you the general idea; then I will give you the specific instructions and you will have to do everything strictly as I describe.

**Claude:** Acknowledged as context-setting. No implementation action.

---

**Luca:** So the system starts with the user initializing the project by providing everything necessary to get it started, and the agent simply builds the repository, prepares a detailed to-do list or at least an initial action plan to develop the project with a relatively high level of abstraction.

**Claude:** On `init`, the system writes `state/TODO.md` with initial tasks ("Review GOAL.md and refine success criteria", "Set up environment", "Begin first task"). This is a basic starter list, not a project-specific plan generated from the user's goal description. Generating a detailed, goal-aware action plan from the user's project description is not yet implemented — it would require an LLM call during init.

---

**Luca:** Which will then be developed step by step during the development of the project itself.

**Claude:** The `state/TODO.md` and `state/PROGRESS.md` files are designed to be iteratively updated during sessions. `core/agents.py:_log_result()` appends completed task results to `PROGRESS.md`. The plan-execute-iterate loop (`plan_execute_iterate()`) supports iterative refinement. But the TODO is not automatically refined by agents — it's manual or would require agent interaction.

---

**Luca:** Likewise, the agent will set up a conda environment, and in doing so it will update a file where all the information necessary for its use is kept.

**Claude:** `core/environment.py:create_conda_env()` can create a conda environment with a specified Python version and packages. `discover_system()` detects whether conda is available. `generate_system_md()` produces a markdown summary of the system (OS, Python, CPU, GPU, RAM, conda/docker availability). However, `create_conda_env()` is not automatically called during `init` — the user would need to trigger it. The system.md generation is available but not wired into the init flow.

---

**Luca:** In fact, the system must be able to consult each time a sort of project-specific encyclopedia, i.e. a set of information, for example how to do rsync between machines where the data are located and machines where the code is run, or the name of the conda environment, in short a series of project-specific tricks that the various agents will accumulate during the project.

**Claude:** `core/knowledge.py` implements the encyclopedia system. `templates/knowledge/ENCYCLOPEDIA.md` has sections: Environment, Machines, Tricks, Decisions, What Works, What Doesn't Work. Functions: `append_learning()`, `log_decision()`, `log_success()`, `log_failure()`, `log_trick()`. The agent instruction file (`templates/.claude/CLAUDE.md`) explicitly tells agents to "Update knowledge — every task should potentially update ENCYCLOPEDIA.md". `search_knowledge()` provides keyword-based lookup. Full semantic search (RAG via ChromaDB) is listed as an optional dependency but not implemented in code.

---

**Luca:** So it is knowledge that, during the interaction of the agents with the reality of the scientific project and with the code, is formed and grows, and persists, and the agents must always be aware that they can then essentially do RAG to read this encyclopedia to understand all the tricks of the trade that previous agents before them have learned.

**Claude:** The encyclopedia persists on disk and is available to all agents. `search_knowledge()` provides keyword search. The `.claude/CLAUDE.md` instructions tell agents to read and update the encyclopedia. RAG via ChromaDB/sentence-transformers is listed in `pyproject.toml` optional dependencies (`chromadb`, `sentence-transformers`) but no actual vector embedding or semantic search code is implemented. This is keyword-search only.

---

**Luca:** First of all, the machinery must be capable of using cheap models for cheap operations.

**Claude:** `core/model_router.py` implements this. `classify_task_complexity()` categorizes tasks as SIMPLE/MEDIUM/COMPLEX/CRITICAL based on keywords. `route_to_model()` maps: SIMPLE → claude-haiku, MEDIUM → claude-sonnet, COMPLEX/CRITICAL → claude-opus. When budget is below 20%, it routes everything to haiku. Each `ModelConfig` includes cost-per-1k-token rates. However, this routing is not yet wired into `execute_agent_task()` — all agent tasks currently invoke `claude` CLI without model selection.

---

**Luca:** I'll give you an example: the user prompts by voice in their natural language; we want to transform the prompt into English, the language used to talk with AIs, and structure it from a disorganized brainstorming of the user's words into an efficient prompt, using for example a collection of prompts that we will discuss later.

**Claude:** `core/voice.py` implements the pipeline: `transcribe_audio()` (Whisper integration, requires `openai-whisper`), `detect_language()` (heuristic character-range detection for English, Chinese, Russian, Arabic, Spanish), `translate_to_english()` (placeholder — returns original text with a warning, no actual translation API wired), `structure_prompt()` (matches user input keywords against loaded prompt templates from `defaults/PROMPTS.md` and fills placeholders). `load_prompt_templates()` parses the PROMPTS.md format. The voice-to-structured-prompt pipeline exists but audio transcription requires Whisper to be installed, and translation is a stub.

---

**Luca:** This translation prompting and intelligent prompting does not need to be done by an expensive agent. In fact, we want all agents to be 4.5 opus with thinking enabled for scientific operations, while this kind of basic and obvious operations must be done with the cheapest models possible, not necessarily Claude.

**Claude:** `core/model_router.py` defines the model hierarchy (opus for critical/complex, sonnet for medium, haiku for simple). `core/tokens.py:select_thinking_mode()` auto-selects thinking modes: "ultrathink" for CRITICAL tasks, "extended" for COMPLEX, "none" for SIMPLE. The model router supports non-Anthropic providers conceptually (`ModelConfig.provider` field) but no OpenAI/Gemini integration exists. All actual execution goes through the `claude` CLI.

---

**Luca:** I was just talking about voice. One of the first features we must develop is that in this dashboard, which will be available either via a mobile app or via a VS Code extension, the key feature is that the user can directly prompt by voice in their language, whatever it is, and the machinery translates into English and transforms the user's brainstorming into a structured prompt that goes to the agent.

**Claude:** The voice pipeline exists in `core/voice.py` as described above. There is no mobile app, no VS Code extension, and no web dashboard. The dashboard is a terminal TUI built with Rich (`cli/dashboard.py`). Voice input would need to be captured externally and passed as an audio file to `transcribe_audio()`. There is no microphone capture or real-time voice integration.

---

**Luca:** Moreover, in this idea of mine, which we will then refine together by reasoning about the current capabilities of agents, I would like the dashboard to be a place where the user interacts with a master agent, which in turn distributes tasks among different sub-agents in an extremely structured way, always keeping for the user a list of currently active sub-agents, their operations, and their token consumption.

**Claude:** The master-agent routing is implemented: `core/agents.py:route_task()` distributes tasks to 6 sub-agents (RESEARCHER, CODER, REVIEWER, FALSIFIER, WRITER, CLEANER) based on keyword matching. `get_active_agents_status()` returns currently running agents. `cli/dashboard.py:build_agents_panel()` displays active agents in the TUI. Token tracking exists at the session level (`core/tokens.py:TokenBudget`), and `DEFAULT_BUDGET_SPLIT` allocates percentages per agent type. However, there is no interactive master-agent conversation loop — the user must explicitly run commands. The dashboard shows status but doesn't accept input.

---

**Luca:** After voice prompting, I would also like us to build a series of cheat sheets.

**Claude:** Multiple cheat sheet types exist: (1) `knowledge/ENCYCLOPEDIA.md` — agent-accumulated project knowledge; (2) `defaults/PROMPTS.md` — structured prompt collection; (3) `knowledge/CONSTRAINTS.md` — user rules; (4) `core/meta_rules.py` writes to `knowledge/CHEATSHEET.md` — operational rules; (5) `.claude/skills/` — code-style, figure-making, paper-writing guides.

---

**Luca:** I mentioned one before, which is the one that agents update with all the tricks of the trade learned on the scientific project, and also basic things like, okay, I need this conda environment, etc., so that there do not have to be repetitions by the user.

**Claude:** `core/knowledge.py:log_trick()`, `log_decision()`, `log_success()`, `log_failure()` all append timestamped entries to the encyclopedia. The ENCYCLOPEDIA.md template includes an Environment section for conda info and a Machines section. Agents are instructed to update it via `.claude/CLAUDE.md`.

---

**Luca:** Other cheat sheets include a cheat sheet that is a collection of prompts that I will provide later, which work, and when we transform the user's voice from their natural language into English, we will also do a RAG or otherwise use this prompt collection to find an appropriate prompt and thus build an efficient prompt for the sub-agents to run.

**Claude:** `defaults/PROMPTS.md` contains 15 structured prompts organized by category (Literature Review, Code Writing, Data Analysis, ML, Paper Writing, Validation, Maintenance). `core/voice.py:load_prompt_templates()` parses them and `structure_prompt()` matches user input against template tags to find the best fit. This is keyword matching, not RAG — no vector embeddings are used.

---

**Luca:** Among other features, we will need to store securely and appropriately all the user's API keys, which will therefore be provided at the moment of initialization of the new project.

**Claude:** `config/settings.yml` stores credential references as `${ENV_VAR}` placeholders. The `.gitignore` excludes `.env`, `.env.*`, `secrets/`, `*.pem`, `*.key`, `credentials.json`. `core/security.py:scan_for_secrets()` detects hardcoded secrets in code. `core/security.py:protect_immutable_files()` prevents modification of `.env` and `secrets/*`. However, there is no secure vault or encrypted storage — credentials live in plain `.env` files, which is standard but not encrypted.

---

**Luca:** Then there is the issue of reproducibility: I would like it to always be mentioned and somehow enforced in all the different rules of the game that everything must be traceable backwards and reproducible.

**Claude:** `core/reproducibility.py` implements: `RunLog` dataclass (run_id, command, git_hash, parameters, metrics, artifacts), `log_run()` persists to JSON, `ArtifactRegistry` tracks artifacts with SHA-256 checksums and verifies integrity. `compute_dataset_hash()` hashes files/directories. The `.claude/CLAUDE.md` instructions include reproducibility in the VALIDATE phase. The falsifier agent (`templates/.claude/agents/falsifier.md`) checks reproducibility. Random seeds, logging, and checkpoint saving are mentioned in prompt templates.

---

**Luca:** Another feature: one of the main characteristics I have noticed in dense interaction with cloud tools in recent times is the lack of memory, i.e. when chat compaction happens, memory tends to crumble and many important pieces of information are lost. One of the mitigation mechanisms I was thinking of is creating these cheat sheets.

**Claude:** The cheat sheet / encyclopedia system is the primary mitigation. Knowledge is written to disk files (ENCYCLOPEDIA.md, CHEATSHEET.md, CONSTRAINTS.md) that persist across sessions and survive context compaction. Agents are instructed to read these files at the start of every session (ORIENT phase in `.claude/CLAUDE.md`). The session system (`core/session.py`) tracks state across sessions. Snapshots (`snapshot_state()`) create backups. However, there is no automatic injection of encyclopedia content into agent prompts — agents must read the files themselves.

---

**Luca:** Another cheat sheet I will create later includes, for example, information on how to write a good paper, another on how figures should be made, and so on.

**Claude:** `templates/.claude/skills/paper-writing.md` and `templates/.claude/skills/figure-making.md` and `templates/.claude/skills/code-style.md` exist as skill files. The writer agent (`templates/.claude/agents/writer.md`) has section-specific guidance. `core/paper.py` has publication-quality figure settings (`RC_PARAMS`, colorblind-safe `COLORS` palette). `defaults/PROMPTS.md` includes paper-writing and figure-generation prompts.

---

**Luca:** So there will be various ones that machine learning must retrieve, but in very long conversations, where perhaps one agent prompts another agent and there is back-and-forth between agents, I fear that this issue of certain elements already discussed being lost from the long context will arise again. So this is an issue we absolutely have to address.

**Claude:** The design relies on persistent files as external memory. Each agent is instructed to read relevant files before acting (ORIENT phase). The encyclopedia, progress logs, and cheat sheets serve as the persistent memory layer. However, there is no mechanism that automatically injects relevant knowledge into agent prompts based on the current task — agents must actively read files. The multi-agent back-and-forth (`plan_execute_iterate`, `execute_parallel_tasks`) passes task descriptions but not accumulated context between agents.

---

**Luca:** I was saying: a dashboard jointly accessible either from VS Code or from mobile, which allows monitoring multiple actions simultaneously.

**Claude:** `cli/dashboard.py` provides a Rich TUI with 6 panels: Goal, Sessions, Active Agents, Resources (RAM/CPU/Disk), Figures, TODO, Progress. `live_dashboard()` refreshes periodically. This is terminal-only — no VS Code extension, no mobile app, no web interface.

---

**Luca:** For example, I am in a complex project, I am giving instructions to the agent on how to behave for different matters, maybe one related to writing a paragraph of the paper, another to a deep learning algorithm, and so on, and I would like this to be distributed by the master agent.

**Claude:** `core/agents.py:route_task()` routes based on keywords to specialized agents. `execute_parallel_tasks()` can run multiple tasks concurrently with a thread pool, respecting dependency DAGs. The master agent concept is defined in `templates/.claude/agents/master.md` as an orchestrator that routes to sub-agents. However, there is no interactive master agent that receives a stream of voice messages and autonomously distributes them — the routing is programmatic and task-by-task.

---

**Luca:** I send all the voice messages in a single channel, the master agent understands to whom to forward them, always minimizing the cost in terms of tokens.

**Claude:** Not implemented as described. The routing (`route_task`) and model selection (`route_to_model`) exist separately, but there is no unified voice channel → master agent → sub-agent dispatch pipeline. The voice transcription, prompt structuring, task routing, and model routing modules exist independently but are not connected into a single flow.

---

**Luca:** And also suggest where you think I might be thinking in overkill and could easily burn tokens; I have the 200-franc-per-month Claude plan and we want to exploit it as much as possible, but we also do not want to go into overkill, I do not know how easy that is.

**Claude:** `core/tokens.py` has budget tracking with session (100k) and daily (500k) limits, percentage warnings at 50%/75%/90%, and `check_budget()` that returns whether to proceed. `core/model_router.py` routes to cheaper models when budget < 20%. The `.claude/CLAUDE.md` instructions include "Token Awareness" rules. However, actual token counting from Claude CLI output is not implemented — `estimate_tokens()` uses a ~4 chars/token heuristic, not real usage data.

---

**Luca:** Among other features there must be a "don't please me" feature, i.e. we must ensure that agents always respond in a grounded, objective way and not try to please the user, without necessarily tearing them down, but there is a tendency to please the user that we must avoid.

**Claude:** The `.claude/CLAUDE.md` instructions state: "Don't please — Be objective, challenge assumptions, report flaws." The falsifier agent (`templates/.claude/agents/falsifier.md`) is specifically designed to "DESTROY results, not validate" and lists attack vectors. The reviewer agent checks quality critically. This is enforced through system prompts, not code.

---

**Luca:** Moreover, we must allow Claude agents to use Gemini when Claude agents cannot access certain websites where Gemini excels.

**Claude:** Not implemented. `core/model_router.py` has a `provider` field in `ModelConfig` and `FALLBACK_CHAINS` structure that could support cross-provider fallback, but only Anthropic models are defined. No Gemini/Google API integration exists.

---

**Luca:** Then there are many other features. We want connections with various personal objects. For example, a user might want to link their website and the agent should be able, if the user provides the repository that builds the website, etc., to integrate, for example, a feature in the website related to the project. So also a sort of repo-to-repo interaction.

**Claude:** `core/cross_repo.py` implements: `LinkedRepo` dataclass, `link_repository()` to register external repos, `coordinated_commit()` to commit to multiple repos with the same message. Repos are stored in `state/linked_repos.json`. However, this is a coordination framework — it can link and commit across repos, but there is no automated website integration logic.

---

**Luca:** Let's hypothesize that my agent works on a branch of my project-specific repository and then I also want it to be constantly updating my main repository that builds my website.

**Claude:** `coordinated_commit()` can commit to multiple linked repos. `enforce_permission_boundaries()` checks whether an action (read/write/commit) is allowed on a linked repo. Branch management and automatic cross-repo synchronization are not implemented — commits are manual triggers.

---

**Luca:** Obviously everything must be done securely, using Docker containerization to prevent the agent from modifying system configurations without my authorization, which could be potentially dangerous, or especially from deleting my files or doing other stupid things.

**Claude:** A `docker/` directory exists in the project structure but no Dockerfile or Docker-based execution is implemented. `core/security.py:protect_immutable_files()` blocks modifications to protected files. `core/security.py:scan_for_secrets()` detects leaked credentials. The autonomous module (`core/autonomous.py:audit_log()`) logs all actions. But there is no Docker containerization or sandboxing of agent execution.

---

**Luca:** So we also need guardrails so that the agent behaves properly.

**Claude:** Guardrails are enforced through: (1) immutable file protection (`core/security.py`); (2) permission boundaries on linked repos (`core/cross_repo.py`); (3) confirmation gates on purchases (`core/autonomous.py:suggest_purchase()` always returns `pending_confirmation`); (4) audit logging; (5) agent system prompts with explicit constraints; (6) `.claude/CLAUDE.md` core rules. No runtime code execution sandboxing exists.

---

**Luca:** Other fundamental rules: agents must always, as soon as possible, use code, i.e. not do things "by hand," which would cost a huge amount of tokens for many operations, but instead write code, as agents already tend to do well, to automate things deterministically.

**Claude:** The coder agent (`templates/.claude/agents/coder.md`) is instructed to write code with tests. `defaults/CODE_STYLE.md` provides coding standards. The `.claude/CLAUDE.md` EXECUTE phase says to execute one subtask at a time and checkpoint. This is enforced through system prompts, not code-level constraints.

---

**Luca:** Then there is an issue of cleanliness: often agents go into crazy mode and start generating a huge amount of code and data, which is obviously risky and problematic in many ways.

**Claude:** The cleaner agent (`templates/.claude/agents/cleaner.md`) handles refactoring, optimization, and documentation. `core/resources.py:make_resource_decision()` checks disk space and RAM to detect resource problems. `cleanup_old_checkpoints()` removes old checkpoints. `.claude/CLAUDE.md` instructs agents to "commit aggressively" after each subtask.

---

**Luca:** We must ensure that every so often, when a task is complete, without losing things, we maintain very frequent git pushes, and this too must be incorporated into the structure of the app/VS Code extension, i.e. agents must push aggressively, being careful not to step on each other.

**Claude:** The `.claude/CLAUDE.md` core rules state "Commit aggressively — Meaningful commits after each subtask." The `coordinated_commit()` function in `core/cross_repo.py` handles multi-repo commits. However, there is no automatic git-push mechanism built into the agent execution pipeline — agents are instructed via prompts to commit frequently, but it's not enforced programmatically.

---

**Luca:** This is something I believe Claude has solved and we must ensure it works, i.e. that there are no merging problems. So constant pushing so that everything is tracked, but also constant cleaning, so that the repository remains usable, clear, and functional.

**Claude:** Not specifically implemented. The cleaner agent handles code cleanup, and `.claude/CLAUDE.md` instructions address this, but there is no automated merge conflict detection or resolution system.

---

**Luca:** In fact, I would like to propose a dual structure, i.e. for each project two sub-repositories are built, or rather two repositories altogether perhaps, I don't know how you prefer: one for experiments and general messiness, where we put everything we do, and it does not need to be hyper-clean; and another super-clean one that could potentially go into the hands of users.

**Claude:** Not implemented. The system creates a single repository per project. The `cross_repo.py` module could link a second repo, but there is no automatic dual-repo structure or code promotion pipeline from experiment repo to clean repo.

---

**Luca:** In fact, the code must always be minimal, concise, straight to the point, without fluff, it must be optimized, and this must be clear to the agents.

**Claude:** `defaults/CODE_STYLE.md` provides coding standards. The coder agent instructions include constraints like "functions < 50 lines", type hints, docstrings. The cleaner agent handles optimization. The `.claude/CLAUDE.md` instructions emphasize conciseness.

---

**Luca:** For example, everything must be vectorized as soon as possible, and commented not in an excessive and tiring way, but in a way that the user can always know what is going on.

**Claude:** `templates/knowledge/CONSTRAINTS.md` includes "Prefer vectorized operations over loops" as a soft preference. This is specified in agent prompts. No automated vectorization checker exists.

---

**Luca:** So we should also automate code-cleaning passes, and every code-cleaning pass must ensure that the effect does not change, i.e. when the agent that cleans the code is called, the agent must then rerun the code and ensure that the results are exactly the same as before the cleaning.

**Claude:** The `defaults/PROMPTS.md` "clean-code" prompt explicitly states: "Run tests, save expected output → Clean → Run tests, verify same output → Commit. CRITICAL: Behavior must not change." The cleaner agent is instructed to verify before/after. This is prompt-enforced, not programmatically automated.

---

**Luca:** Then I would like to develop a paper-making feature, i.e. in every repository there is also the possibility of extracting a paper.

**Claude:** `core/paper.py` implements: `add_citation()` (BibTeX management), `list_citations()`, `compile_paper()` (via Make), `clean_paper()`, `check_figure_references()` (validates LaTeX \includegraphics references), `save_figure()` (publication-quality matplotlib output), `apply_rcparams()`. `cli/main.py` has a `paper` command with subactions: `build`, `check`, `update`, `modernize`. `templates/paper/` includes `main.tex`, `Makefile`, `references.bib`.

---

**Luca:** According to the user's directions, using a predefined LaTeX template inside the repository that I will provide later. For now you can put a very basic one, then we will improve it, and structure it already.

**Claude:** `templates/paper/main.tex` is a basic article-class template with sections: Abstract, Introduction, Methods, Results, Discussion, Conclusion. It uses `natbib` with `plainnat` style. `templates/paper/Makefile` has compilation rules. `templates/paper/references.bib` starts empty. The template is basic as requested, ready for customization.

---

**Luca:** So when the project repository is created, the subpart of the repository that constitutes a baseline for a paper is also created, with all the rules that we will put into the paper-making rules.

**Claude:** On `init`, the `paper/` directory is copied from templates, including `main.tex`, `Makefile`, and `references.bib`. The writer agent (`templates/.claude/agents/writer.md`) has section-specific guidance. The paper-writing skill (`templates/.claude/skills/paper-writing.md`) contains style rules.

---

**Luca:** For example, that all plots must be rasterized but at the same time vector where possible, using rcParams42 so that all text is editable, PDFs, i.e. all figures must be exported in PDF and embedded into the documents.

**Claude:** `core/paper.py:RC_PARAMS` sets `savefig.format: "pdf"`, `savefig.dpi: 300`, `savefig.bbox: "tight"`, and publication-quality font/size settings. `save_figure()` defaults to PDF format. The `COLORS` dict provides a colorblind-safe palette. The figure-making skill file addresses these requirements. However, "rasterized with editable text" (i.e., `rasterized=True` on plot elements while keeping text as vectors) is not specifically coded — it would be up to the agent to apply this per-plot.

---

**Luca:** In short a series of rules that we will then strengthen and that allow, when the user says "make me a version of the paper" or "modernize the version of the paper" or "continue integrating information from new results into the paper," and so on, the agent to do it autonomously.

**Claude:** `research paper build` compiles the paper. `research paper modernize` runs style analysis via `core/style_transfer.py:analyze_paper_style()` and reports metrics. `research paper check` verifies figure references and citation count. `research paper update` shows current citations. The actual autonomous paper-writing (generating LaTeX content from results) would require an LLM call, which is not wired up — the commands provide analysis and compilation, not content generation.

---

**Luca:** I ask not only for a LaTeX template, but also to prepare a series of functions, including inpainting, whereby the user can upload reference papers and the agent, without plagiarizing, must be able to transform the style into that of the reference paper.

**Claude:** `core/style_transfer.py` implements: `analyze_paper_style()` (computes avg sentence length, passive voice ratio, hedging ratio, citation density, vocabulary richness, tense, common phrases), `generate_transformation_prompt()` (generates instructions to transform writing from source to target style), `verify_no_plagiarism()` (n-gram overlap detection between new text and references). The term "inpainting" here means style transfer, not image inpainting. The plagiarism check is a simple 6-gram overlap detector, not a full plagiarism detection system.

---

**Luca:** In addition to following the general paper-making rules in one of the cheat sheets I mentioned that will be provided.

**Claude:** The paper-writing skill file (`templates/.claude/skills/paper-writing.md`) and the writer agent prompts serve this role. The `defaults/PROMPTS.md` includes `write-section` and `improve-writing` prompt templates.

---

**Luca:** When the repository is created or a new sub-agent is spun up, and so on, we must obviously ensure that there are constraints whereby the agent explores the repository and becomes familiar with it, or at least with the part that concerns it.

**Claude:** The `.claude/CLAUDE.md` progressive instruction protocol requires: Phase 1 ORIENT (read GOAL.md, CONSTRAINTS.md, TODO.md), Phase 2 EXPLORE (read relevant code/data, build mental model). Each agent's system prompt is loaded via `get_agent_prompt()` from their markdown file. This is prompt-enforced.

---

**Luca:** In fact, each sub-agent could refer to different instruction files, some of which are logically modifiable, while others must absolutely not be touched because they characterize the repository itself or the spaces where the user's rules are simply transcribed.

**Claude:** `core/security.py:protect_immutable_files()` with `DEFAULT_IMMUTABLE` list protects `.env`, `secrets/*`, `*.pem`, `*.key`. `templates/knowledge/CONSTRAINTS.md` has "Hard Rules" (never violated) and "Soft Preferences" sections. The agent definition files in `.claude/agents/` are separate from the user's `knowledge/` files. However, there is no enforcement preventing agents from modifying their own agent definition files — this would need file-level write protection.

---

**Luca:** In fact, for each prompt not only must there be an execution that tries to realize the user's wishes, but also any meta-rules not yet present in the cheat sheets must be incorporated into the cheat sheets.

**Claude:** `core/meta_rules.py` implements: `detect_operational_rule()` (identifies imperative/prescriptive text like "always", "never", "must"), `classify_rule_type()` (categorizes as workflow/constraint/preference/debug/general), `append_to_cheatsheet()` (writes to `knowledge/CHEATSHEET.md` under the appropriate section). However, this is not automatically triggered on every prompt — it would need to be called by the agent or a hook. The automatic extraction of meta-rules from user prompts is not wired into the execution pipeline.

---

**Luca:** For example, I realize that the machine is not working well from the point of view of representing certain ideas in plots, I give very specific instructions and I do not want to have to give them again identically a second time. I want this information to be, at the moment I prompt, automatically also added to the cheat sheet, without me having to tell Claude "look, add it to the cheat sheet." This too must be automated.

**Claude:** The functions exist (`detect_operational_rule`, `append_to_cheatsheet`) but the automation — scanning every user prompt for rules and auto-appending — is not implemented. It would require a pre-processing step in the prompt pipeline that calls `detect_operational_rule()` and, if positive, calls `append_to_cheatsheet()`. This step does not exist in the current flow.

---

**Luca:** Then it must be ensured that the agent never guesses, but when it is uncertain it uses web search, especially because often solutions already exist and it is simply necessary for the agent to use web search to document itself.

**Claude:** `.claude/CLAUDE.md` core rule #1: "Never guess — Search or ask when uncertain." The MCP configuration (`templates/config/mcp-nucleus.json`) includes tier1_essential with `fetch` for web access. Web search behavior is prompt-enforced, not programmatically enforced.

---

**Luca:** Obviously web search consumes tokens, so it must be used judiciously.

**Claude:** Token awareness is built into `.claude/CLAUDE.md`: "Use cheap operations where possible." The model router selects cheaper models for simple tasks. No specific web-search-cost tracking exists.

---

**Luca:** And we must also ensure certain behavioral rules, such as being concise and testing autonomously.

**Claude:** `.claude/CLAUDE.md` instructs: "Test small first — Downsample data, run 1 epoch, then scale." The coder agent instructions require "Test before commit." `core/automation_utils.py:run_smoke_test()` provides a quick smoke-test function. `downsample_data()` supports quick data sampling.

---

**Luca:** In fact, I want that whenever code is created, it is run on a small scale, and this must be made clear: not at full scale at first, but a downsampling, in short something manageable, and the agent always tests the code end-to-end and ensures it works before scaling up, before giving it to the user.

**Claude:** `core/automation_utils.py:downsample_data()` with configurable fraction and seed. The `.claude/CLAUDE.md` EXECUTE phase says "Execute one subtask at a time, checkpoint after each, validate results before proceeding." The `defaults/PROMPTS.md` train-model prompt says "Run 1 epoch first to verify pipeline." This is prompt-enforced.

---

**Luca:** In fact, most of the code must be run in the background and the agent must monitor it.

**Claude:** `cli/main.py:overnight()` runs Claude CLI in a loop with `--dangerously-skip-permissions`. `core/agents.py:execute_agent_task()` runs subprocesses with a 600-second timeout. However, there is no background job management system (no task spooler, no process monitoring). The dashboard (`cli/dashboard.py`) shows status but cannot monitor running background processes.

---

**Luca:** This monitoring aspect is central to the app/VS Code extension/web app, however we want to define it. In fact, this monitoring section must be constantly live, so there must be very verbose tracking.

**Claude:** `cli/dashboard.py:live_dashboard()` provides a periodically-refreshing TUI (default 5-second interval). Panels show: active agents, resources (RAM/CPU/disk), figures, TODO, progress, sessions, goal. `_log_result()` in `core/agents.py` appends to PROGRESS.md after every task. This is terminal-only, not a web/mobile/VS Code dashboard.

---

**Luca:** So we must also—indeed this is fundamental in all aspects—tell the agent to be extremely verbose, because it is very useful both for the agent itself to self-diagnose its behavior and understand what is doing, and to give responses to the user about what is happening.

**Claude:** `.claude/CLAUDE.md` core rule #4: "Be verbose — Log extensively for self-diagnosis." All core modules use Python `logging`. `_log_result()` writes task outcomes to PROGRESS.md. `core/autonomous.py:audit_log()` writes timestamped entries. Verbosity is primarily prompt-enforced.

---

**Luca:** And for each activity there must be progress tracking, in the style of TQM, maybe also with scrolling verbose output, so the user knows that things are happening, knows how they are progressing.

**Claude:** `state/PROGRESS.md` accumulates task results with status icons (success/failure/timeout) and timestamps. The dashboard progress panel shows the last 15 entries. There is no real-time scrolling output or tqdm-style progress bars — the progress is updated after each task completes, not during execution.

---

**Luca:** And also the sub-agents themselves can observe themselves. Ideally they can also observe each other, so maybe one sub-agent needs information about what another sub-agent is doing, like in an office, and they can look at each other.

**Claude:** `get_active_agents_status()` returns currently running agents with their task descriptions. `PROGRESS.md` is a shared file visible to all agents. The ORIENT phase instructs agents to read PROGRESS.md. However, agents don't actively query each other during execution — they share state through files, not direct communication.

---

**Luca:** So having a common space where these documents are constantly visible to the sub-agents who need to understand what is happening, as well as the user being able to see them without having to go crazy clicking.

**Claude:** The `state/` directory is the common space: `TODO.md`, `PROGRESS.md`, `sessions/`. The `knowledge/` directory persists across agents. The dashboard provides a single-screen view. This meets the "no clicking" requirement for the terminal but there is no voice-accessible or mobile-accessible version.

---

**Luca:** Especially if they have wrist or hand pain inside a repository, but simply by looking at their screen and interacting by voice with the machinery.

**Claude:** Voice interaction is partially built (`core/voice.py`) but not connected to the CLI. The dashboard is read-only (display, no input). Hands-free operation would require a voice-input loop that pipes to the CLI, which is not implemented.

---

**Luca:** Furthermore, regarding the paper, I go back a bit, again I apologize for the lack of sequence, regarding the structure of the paper, we must also ensure that all references are built properly using the PubMed MCP, and that a BibTeX file is built and compiled properly, etc.

**Claude:** `core/paper.py:add_citation()` writes BibTeX entries to `paper/references.bib` with deduplication. `list_citations()` extracts all citation keys. `compile_paper()` runs `make all` which includes BibTeX compilation. PubMed access is configured in `templates/config/mcp-nucleus.json` as part of tier1_essential (`paper-search`, `arxiv`). The actual PubMed MCP integration (searching and fetching citations) depends on the MCP being installed and running — the configuration references it but no code calls it directly.

---

**Luca:** In the creation of the content environment, we must also ensure that the agent installs everything needed to then make the paper and everything else I describe in this chat. For example, a Makefile comes to mind for making the paper.

**Claude:** `templates/paper/Makefile` exists with compilation rules for LaTeX. `templates/.github/workflows/paper-build.yml` installs LaTeX packages (`texlive-latex-base`, `texlive-latex-extra`, `texlive-bibtex-extra`, `biber`, `latexmk`) in CI. Local LaTeX installation is not automated — the user must have LaTeX installed.

---

**Luca:** One of the risks, obviously, is that working at this scale, a user might crash, run out of memory, or otherwise overuse machine resources, run out of disk space, and so on. Therefore the machinery must also constantly check, with a certain rigor and logic, how many resources are available and possibly make decisions accordingly.

**Claude:** `core/resources.py:monitor_resources()` checks RAM (used/total), CPU load, disk free space. `make_resource_decision()` returns actionable decisions: `can_proceed` (False if disk < 1 GB), `should_checkpoint` (True if RAM > 90%), `should_cleanup` (True if disk < 5 GB), plus warning messages. The dashboard's resource panel displays live metrics. However, this is not automatically called before each task — it would need to be integrated into the execution pipeline.

---

**Luca:** In fact, the idea is that there is extensive checkpointing, but at the same time agents then autonomously delete those files that were important for checkpointing and not losing time in case of unexpected downstream crashes, but that occupy memory, for example.

**Claude:** `core/resources.py:CheckpointPolicy` defines: `interval_minutes`, `max_checkpoints`, `min_disk_free_gb`. `cleanup_old_checkpoints()` removes oldest checkpoints when exceeding `max_checkpoints` (default 5). `core/session.py:snapshot_state()` creates timestamped state backups. `restore_snapshot()` recovers from snapshots. Automatic scheduled cleanup is not triggered — it must be called explicitly.

---

**Luca:** So we want this type of resource management to also be totally autonomous, so that the user does not have to repeat things ten times to the agents, or even more.

**Claude:** The functions exist but are not autonomously triggered. They would need to be integrated into a monitoring loop or called as hooks before/after task execution. Currently the user or agent must explicitly call `monitor_resources()` and `cleanup_old_checkpoints()`.

---

**Luca:** Then we would also like to set up some autonomous routines, and I don't know how difficult this is. For example, that the agent can buy a machine on Hetzner to host a website and buy a domain on Namecheap.

**Claude:** `core/autonomous.py:suggest_purchase()` creates purchase suggestions with `status: "pending_confirmation"` — it never executes purchases automatically. It logs to the audit file. Actual Hetzner/Namecheap API integration does not exist. The purchase flow is a suggestion-and-confirm framework only.

---

**Luca:** Or alternatively monitor websites, for example monitor exploding topics every day and based on what it observes, monitor the news, make decisions and possibly also send emails to users.

**Claude:** `core/autonomous.py:monitor_topic()` and `monitor_news()` create monitoring specs (topic, sources, status) but are stubs — they return data structures without actually polling any APIs. `core/notifications.py:send_email()` can send emails via SMTP. `core/autonomous.py:ScheduledRoutine` stores routine definitions (name, schedule, command, enabled). `add_routine()` and `list_routines()` manage them. However, there is no scheduler that actually runs routines on a cron-like schedule — the infrastructure is defined but not executed.

---

**Luca:** So for example, an email could be when you need authorization from Luca for critical matters like confirming a purchase or entering a credit card.

**Claude:** `core/notifications.py:send_email()` sends via SMTP with throttling. `suggest_purchase()` logs audit entries. The flow would be: suggest_purchase → audit_log → send_email to user → user confirms. The email sending works, the purchase suggestion works, but the confirmation-receipt flow (user replies and system processes the reply) is not implemented.

---

**Luca:** And indeed we want monitoring that sends emails to the user every roughly two hours if the user does not provide key information needed to proceed that the machinery requires, maximum two emails per hour because otherwise the user cannot take it anymore.

**Claude:** `core/notifications.py` has throttling: `DEFAULT_THROTTLE_SECONDS = 300` (5 minutes minimum between notifications of the same type). `_check_throttle()` and `_update_throttle()` enforce this. The throttle is per-notification-type (slack, email, desktop). Configuring "every 2 hours, max 2 per hour" would require adjusting the throttle to 1800 seconds. The reminder-loop (checking if user input is needed and re-sending) is not implemented.

---

**Luca:** We also want to make space for the user to upload databases and connect their tools, for example connect email, connect Slack, and suggest other essential tools to connect for a scientific researcher.

**Claude:** `uploads/` directory exists for file uploads. Slack integration exists via `core/notifications.py:send_slack()` (webhook-based). Email integration via `send_email()`. The MCP configuration (`templates/config/mcp-nucleus.json`) includes tier6_communication with `slack`, `gmail`, `sendgrid`. The onboarding asks for notification method (email/slack). Database connections are in tier2_data (`postgres`, `sqlite`, `duckdb`, `chroma`). However, connecting these services requires manual API key setup — there is no automated service discovery or OAuth flow.

---

**Luca:** I'm not sure about this, we'll reason better about it later, but we were talking about sub-agents, and it is probably also important that sub-agents have specialized functions.

**Claude:** 6 specialized sub-agents exist: RESEARCHER (literature search), CODER (implementation), REVIEWER (quality checks), FALSIFIER (result destruction), WRITER (documentation/papers), CLEANER (refactoring). Each has a dedicated markdown file in `templates/.claude/agents/` with role-specific instructions, constraints, and output formats.

---

**Luca:** For example, a central fact in the scientific process is to do a reverse destruction of the result, i.e. let's suppose the agent obtains a good result, then we will need agents that in all ways try to understand whether there could be cheating, i.e. whether there could be information leakage, for example, and whether the result is invalidated by some procedure that negates the initial objectives and confuses and falsifies the results, so a sort of falsifier, right?

**Claude:** The FALSIFIER agent (`templates/.claude/agents/falsifier.md`) is specifically designed for this. It's described as "Popperian" — it tries to DESTROY results, not validate them. Attack vectors include: data leakage detection, statistical validity checking, code correctness verification, methodology review, and reproducibility testing. The output format is a "falsification report" with critical issues, warnings, and passed checks. `ROUTING_KEYWORDS` routes tasks containing "validate", "attack", "falsify", "verify", "leak", "statistical", "reproducib" to this agent.

---

**Luca:** We want a Popperian machine that promotes scientific ideas, but above all destroys them and sees what withstands the blows. This is absolutely central. I should perhaps have clarified this before; perhaps this is the most important thing of all.

**Claude:** The falsifier gets 20% of the token budget (second highest after coder at 35%). It is part of the `.claude/CLAUDE.md` VALIDATE phase: "Run falsifier checks." The `defaults/PROMPTS.md` includes a `validate-results` prompt with a full validation protocol (data leakage, statistical validity, reproducibility, methodology, baselines, confounders).

---

**Luca:** Then, as I was saying before, again I apologize for the disorder, about running jobs in the background. It goes without saying that while agents run jobs in the background, they must also do iterative debugging, so suppose a project is running in the background, crashes, the agents must debug and continue run, debug, run, debug until completion.

**Claude:** `cli/main.py:overnight()` runs Claude CLI in a loop for up to N iterations, checking for a `state/DONE` completion signal. If a run fails (non-zero return code), it logs the error and continues to the next iteration. `plan_execute_iterate()` in `core/agents.py` supports iterative re-planning when tasks fail. However, there is no specific crash-detection → debug → retry pipeline — the overnight mode just re-runs the full task description on failure, relying on Claude to debug.

---

**Luca:** Obviously if it goes into crisis, it must handle it accordingly; if it doesn't get out of it and hours pass and it still hasn't debugged, it should resolve itself.

**Claude:** `plan_execute_iterate()` has a `max_iterations` parameter (default 5). `execute_agent_task()` has a 600-second timeout. There is no time-based escalation (e.g., "if stuck for 2 hours, try a different approach" or "email the user"). Crisis handling is limited to max-iteration caps and timeouts.

---

**Luca:** But I believe Claude is currently so good that it does not enter this type of routine. Perfect.

**Claude:** Acknowledged as commentary. No implementation action.

---

**Luca:** Any sub-agents must also have a sort of role description and related rules in this structure of MD files that we would like to make cross-repo.

**Claude:** Each agent has a dedicated file: `templates/.claude/agents/master.md`, `researcher.md`, `coder.md`, `reviewer.md`, `falsifier.md`, `writer.md`, `cleaner.md`. These are in the `templates/` directory and copied to every new project. `core/knowledge.py:export_knowledge()` and `sync_to_shared()` support cross-project knowledge sharing.

---

**Luca:** Moreover, it would be nice, but I have no idea how possible this is, that any learnings of a given user are shared across all their repositories, so let's say I start project A, and in project A there is a lot of meta-learning by the agents, there is a construction of an infrastructure, these behavior files are updated. I would like them to be transferable, if the user wishes, also to other projects, in order to avoid repetition. A sort of continuously growing encyclopedia.

**Claude:** `core/knowledge.py:sync_to_shared()` copies a project's encyclopedia to a shared `/shared/knowledge/` directory. `export_knowledge()` exports to portable JSON. `import_knowledge()` imports from a JSON export, supporting merge mode (append new entries) or replace mode. The cross-project sharing infrastructure exists but is file-based — there is no automatic sync or notification when knowledge updates.

---

**Luca:** Then, okay, regarding interactive demos for the user, obviously the agent must then develop notebooks instead of scripts, but the default must obviously always be only scripts, and well-made scripts, manageable with proper parallelization.

**Claude:** The coder agent and code style guides emphasize scripts as the default. `jupyter` is listed as an optional dependency. The `defaults/PROMPTS.md` does not specifically differentiate between notebook and script generation. No automated notebook-generation pipeline exists — this would be agent behavior guided by prompts.

---

**Luca:** We always want to save time; the ultimate objective is to find science at the maximum of scientific beauty, but at the same time do so while saving the user's time so that they can have a life, and enjoy their few years.

**Claude:** The token budget system, model routing to cheaper models, and overnight autonomous mode all aim to save user time. The dashboard provides at-a-glance monitoring. This is a design philosophy reflected throughout, not a single feature.

---

**Luca:** We also want agents that check fidelity to the initial idea, so not only debuggers, which are fundamental, but also agents that constantly monitor: okay, are we going off on a tangent or are we adjacent to the initial idea?

**Claude:** `knowledge/GOAL.md` stores the project goal and success criteria. The `.claude/CLAUDE.md` ORIENT phase reads GOAL.md first. The VALIDATE phase says "Compare to original goal." However, there is no automated goal-drift detection system that programmatically compares current work against the stated goal. This is prompt-enforced.

---

**Luca:** Likewise, we must have constant handling of the environment. Suppose a sub-agent installs some packages, another installs others that crash; this must be handled smoothly, trying different alternatives and avoiding entering situations where sudo is needed.

**Claude:** `core/environment.py:create_conda_env()` creates isolated conda environments. The `.claude/CLAUDE.md` mentions using the mamba/conda environment. However, there is no environment conflict detection, no automatic resolution of package conflicts between agents, and no sudo-avoidance enforcement. Environment handling is basic.

---

**Luca:** Because otherwise the user is needed and things can get complicated. It would indeed be nice in the dashboard we are developing to have a terminal where any user actions, such as credit card or sudoer password, etc., are entered, obviously in a hyper-super-mega-safe way.

**Claude:** Not implemented. The dashboard is read-only (display panels). There is no secure input terminal for credentials or sudo passwords within the dashboard.

---

**Luca:** We also want functions where agents instruct other agents by behaving as if they were the user, i.e. there are many situations where it is enough to do a pushback or a data check.

**Claude:** `plan_execute_iterate()` allows a plan function to inspect previous results and generate new tasks — this is agent-to-agent instruction. The master agent concept routes tasks to sub-agents. However, there is no explicit "agent-as-user" feedback loop where one agent reviews another's output and re-prompts it.

---

**Luca:** In particular visual, where the agent must be as objective as possible and has a severe reviewer of itself, i.e. another agent that does not please but is a strict judge, looks at the plots and says, "what the hell did you do, idiot." This kind of stuff.

**Claude:** The REVIEWER agent (`templates/.claude/agents/reviewer.md`) reviews code quality. The FALSIFIER agent attacks results. The "don't please" rule is in `.claude/CLAUDE.md`. However, there is no automated visual review pipeline where an agent examines generated plots — visual inspection would require multimodal capabilities (sending images to Claude), which is not wired up.

---

**Luca:** I also have this autonomous night template to base ourselves on: x for i in {1..20};do echo $i; claude --dangerously-skip-permissions -p "$(cat ralph_loop.md)";done

**Claude:** `cli/main.py:overnight()` is a direct implementation of this pattern. It reads `state/TODO.md` (analogous to `ralph_loop.md`), runs `claude --dangerously-skip-permissions -p tasks` in a loop for up to `iterations` (default 20), and checks for a `state/DONE` completion signal. The structure matches the template exactly.

---

**Luca:** Claude Code Orchestrator (Single-file Bootstrap) [...] Startup procedure (always run first) [...] Read task.md fully. Ensure directories exist. If memory.md does not exist, create it. If progress.md does not exist, create it. If system.md does not exist OR looks stale/empty, run "System discovery" and (re)write system.md. If no agents exist, create an initial small set of agents.

**Claude:** The system maps to this: `state/TODO.md` ↔ task.md/todo.md, `knowledge/ENCYCLOPEDIA.md` ↔ memory.md, `state/PROGRESS.md` ↔ progress.md, `core/environment.py:generate_system_md()` ↔ system.md discovery, `templates/.claude/agents/` ↔ agent definitions. The `.claude/CLAUDE.md` progressive instruction protocol (ORIENT → EXPLORE → PLAN → EXECUTE → VALIDATE) maps to the startup procedure. The `init` command creates all directories and files. However, the startup procedure is not enforced programmatically at session start — it relies on the agent following `.claude/CLAUDE.md` instructions.

---

**Luca:** We therefore want an all-nighter mode in addition to the daily mode based on constant user-agent interaction.

**Claude:** `research overnight` = all-nighter mode. `research start` = interactive daily mode (launches Claude Code session). Both exist in `cli/main.py`.

---

**Luca:** Other elements to consider as we open the discussion: first of all, we must have a sort of plan-execute-iterate framework.

**Claude:** `core/agents.py:plan_execute_iterate()` implements this: accepts a `plan_fn` that generates tasks per iteration, executes them via `execute_parallel_tasks()`, checks results, and re-plans on failure. The `.claude/CLAUDE.md` protocol is ORIENT → EXPLORE → PLAN → EXECUTE → VALIDATE, which maps directly.

---

**Luca:** And in this context we must also ensure that there is efficient token reporting and max capping, so that too many tokens of the monthly availability are not burned.

**Claude:** `core/tokens.py:TokenBudget` has `session_limit` (100k) and `daily_limit` (500k). `check_budget()` returns `can_proceed`, percentage used, and warnings. `select_thinking_mode()` auto-adjusts cost. The model router routes to haiku when budget < 20%. However, actual token usage from Claude CLI is not captured — estimation uses a 4-chars-per-token heuristic.

---

**Luca:** It would also be nice to have a copilot-based option, where the agent is replaceable with Copilot, but we might keep this for the future.

**Claude:** Not implemented. The system is Claude-specific (calls `claude` CLI). No GitHub Copilot integration exists.

---

**Luca:** Moreover, it must be very clear what the user needs to import, for example the reference papers, any reference code.

**Claude:** `defaults/ONBOARDING.md` specifies post-init uploads: reference papers → `reference/papers/`, reference code → `reference/code/`, custom rules → `knowledge/CONSTRAINTS.md`. `core/onboarding.py:setup_workspace()` creates the `reference/` directory. The upload prompting (asking the user if they have papers/code to upload) is specified in ONBOARDING.md but not implemented in the interactive flow.

---

**Luca:** We will make a folder where we put all code potentially useful for the project, which can be messy and chaotic, but the agent can use for refinement, reuse of parts in the context of the project itself, as well as any passwords, API keys, etc., or certain information or input files.

**Claude:** `reference/` for read-only reference material, `local/` for local workspace, `secrets/` for credentials (git-ignored), `uploads/` for user-uploaded data (git-ignored). These are created by `setup_workspace()`. The coder agent instructions say "Check if implementation exists in reference/" before coding.

---

**Luca:** We should also ensure that we understand what the top people in the field do, in order to trace their main operating criteria.

**Claude:** The researcher agent (`templates/.claude/agents/researcher.md`) is designed to find and synthesize literature, including "seminal papers (highly cited)" and "recent papers (last 2 years)." The `defaults/PROMPTS.md` `deep-literature-review` prompt includes "Identify key themes and debates, identify gaps." This is prompt-guided, relying on the agent's capabilities and MCP access (arxiv, semantic-scholar).

---

**Luca:** And I also link below a site from which we can take information regarding paper writing, tutorial generation, and website generation, because indeed we must include website generation capabilities in every possible project.

**Claude:** Paper writing is covered. Tutorial generation and website generation are not implemented. The cross-repo system (`core/cross_repo.py`) could link a website repository, but there is no website scaffolding or generation feature.

---

**Luca:** Then update, as I partially described in the past, and we can discuss this later in more detail.

**Claude:** Acknowledged as future discussion. No specific implementation action.

---

**Luca:** And I also provide below some ideas to look for a prompt collection, which we had already partially discussed, and I ask you to reason together on how we could best exploit this collection using, for example, RAG or all the ways in which RAG can be useful.

**Claude:** `defaults/PROMPTS.md` has 15 structured prompts. `core/voice.py:load_prompt_templates()` parses them and `structure_prompt()` does keyword-based matching. `chromadb` and `sentence-transformers` are in optional dependencies for RAG. Actual RAG (vector embedding, semantic similarity search over prompts) is not implemented — only keyword matching.

---

**Luca:** Another general rule that I had not yet mentioned is to always plot everything necessary to convince the user, and thus generally make galleries, potentially scrollable within this initial canvas.

**Claude:** `cli/gallery.py:scan_figures()` scans for image files, `organize_by_run()` groups them, `display_gallery()` generates a text summary. `cli/dashboard.py:build_plots_panel()` shows the last 5 figures in the dashboard. `core/paper.py:save_figure()` saves publication-quality plots. The gallery is text-based in the terminal — no scrollable image viewer exists.

---

**Luca:** This home page, let's say, or phone application where the user can essentially see in real time what is being produced, and the machine in some way, even when not explicitly described in the prompt, must always plot graphs with well-discussed criteria.

**Claude:** The dashboard (`cli/dashboard.py`) shows a multi-panel view. `live_dashboard()` refreshes periodically. The figure gallery tracks produced plots. Auto-plotting (generating plots without explicit request) is not implemented — it would need to be in agent behavior. No phone application exists.

---

**Luca:** Then another feature: I would like the default to be Oculus 4.5 Thinking with three percent token consumption and also potentially the self-regulations where the model, as we said before, can be selected for silly tasks, even silly free models, and for intermediate-level tasks instead with normal token consumption or turning off thinking.

**Claude:** `core/tokens.py:select_thinking_mode()` returns: "ultrathink" for CRITICAL tasks (validate, prove, paper, publish), "extended" for COMPLEX (debug, design, research), "none" for SIMPLE (format, list, lookup), "standard" for default. `core/model_router.py` routes SIMPLE → haiku, MEDIUM → sonnet, COMPLEX/CRITICAL → opus. The 3% thinking budget is specified in `.claude/CLAUDE.md`: "COMPLEX: Extended thinking (3% budget)." However, the thinking mode is not actually passed to the `claude` CLI — `select_thinking_mode()` returns a string but `execute_agent_task()` doesn't use it.

---

**Luca:** But I imagine the default is better to be thinking three percent in order to ensure maximum quality.

**Claude:** The default in `select_thinking_mode()` for unclassified tasks is "standard" (not ultrathink). CRITICAL tasks get ultrathink. This could be adjusted to default to extended thinking.

---

**Luca:** For paper writing etc also we should not forget https://lamanno-epfl.github.io/tutorial_claude_code/

**Claude:** I did not fetch or incorporate content from this URL. The paper-writing features were built from the spec and prompt templates. This tutorial's specific advice is not embedded in the system.

---

**Luca:** IMPORTANT: we must also pre-organize access to the most important MCPs, for example PubMed for scientific research and many others!

**Claude:** `templates/config/mcp-nucleus.json` configures 70+ MCPs across 8 tiers: tier1_essential (git, github, filesystem, memory, sequential-thinking, fetch, paper-search, arxiv), tier2_data (postgres, sqlite, duckdb, chroma), tier3_ml (jupyter, huggingface, mlflow, wandb), tier4_math (wolfram, sympy), tier5_paper (latex-mcp, overleaf), tier6_communication (slack, gmail, sendgrid), tier7_cloud (aws, docker, terraform), tier8_startup (vercel, gamma, stripe, notion). `core/mcps.py` loads and classifies which tiers to activate based on task keywords.

---

**Luca:** https://github.com/modelcontextprotocol/servers and https://github.com/modelcontextprotocol/servers-archived Perhaps also useful: https://github.com/punkpeye/awesome-mcp-servers

**Claude:** The MCP configuration references servers from these registries. I did not crawl these URLs during implementation. The MCP names in `mcp-nucleus.json` are based on the known MCP ecosystem but actual installation/connection of each MCP is left to the user.

---

**Luca:** Certainly all the basics like Slack, Canva, Stripe, SendGrid, Google Drive, etc. must already be connected and the relevant API keys etc. provided by users at the moment of project creation (optional where possible).

**Claude:** Slack (tier6), SendGrid (tier6), Stripe (tier8) are in the MCP config. Google Drive is not explicitly listed. Canva is not listed (Gamma is listed for slides). The onboarding asks for Slack webhook and email but not all service keys. Most MCP connections require the user to install the MCP server and provide API keys manually.

---

**Luca:** Claude must also be able to create MCPs where one does not exist and it is necessary.

**Claude:** `core/mcps.py:install_mcp()` has a stub function that accepts a name and source URL and runs installation. It's a placeholder — actual MCP creation (writing a new MCP server) is not implemented.

---

**Luca:** We should also connect Zapier and connect Gamma for slides.

**Claude:** Gamma is in tier8_startup in `mcp-nucleus.json`. Zapier is not listed. Neither has actual integration code.

---

**Luca:** Moreover, these MCP GitHubs should be RAGgable by Claude to find and install MCPs autonomously under the hood as needed to satisfy user requests.

**Claude:** Not implemented. There is no RAG system over MCP registries. `core/mcps.py:classify_task()` uses keyword matching to select pre-configured tiers, not dynamic discovery from GitHub repositories.

---

**Luca:** Useful site for paper writing parts, etc.: https://lamanno-epfl.github.io/tutorial_claude_code/ Perhaps useful for orchestration: https://github.com/ruvnet/claude-flow

**Claude:** Neither URL was fetched or incorporated. The orchestration system was built independently using the plan's specifications.

---

**Luca:** Certainly all conversations must be dumped in markdown for documentation.

**Claude:** Not implemented. There is no conversation-to-markdown export. PROGRESS.md logs task results, and the audit log tracks actions, but full conversation dumps are not captured.

---

**Luca:** Use of task spooler ts or tsp.

**Claude:** Not implemented. No task spooler integration exists. Background execution relies on subprocess calls and the overnight loop.

---

**Luca:** Configure parse. Cruft.

**Claude:** Not implemented. No `parse` or `cruft` (project template management) integration exists. The project uses its own template-copying system in `init`.

---

**Luca:** GitHub actions: all the best software engineer ideas properly set up. GitHub automation.

**Claude:** Three GitHub Actions workflows in `templates/.github/workflows/`: `tests.yml` (pytest on push/PR, Python 3.11/3.12 matrix), `lint.yml` (black, isort, mypy checks), `paper-build.yml` (LaTeX compilation, PDF artifact upload). These are copied into every new project.

---

**Luca:** Cronjob routines.

**Claude:** `core/autonomous.py:ScheduledRoutine` dataclass supports `schedule` field (cron-like or "daily"/"hourly"/"weekly"). `add_routine()` and `list_routines()` manage them. However, there is no actual cron scheduler — the routines are stored but not executed on schedule.

---

**Luca:** And everything well described in documentation.

**Claude:** `docs/SPEC.md` is a formal specification covering: architecture, data models (Session, Task, RunLog, ArtifactRegistry), security model, agent types with budget allocations, MVP flow, model routing table, reproducibility. The codebase has docstrings on all public functions. No user-facing README or getting-started guide was written beyond what already existed.

---

**Luca:** We should also put into practice the advice of this fundamental repo: https://github.com/ykdojo/claude-code-tips

**Claude:** I did not fetch this URL. Some common Claude Code best practices are reflected in the design (aggressive committing, file-based persistence, structured prompts, agent definitions), but I cannot confirm alignment with specific tips from that repo.

---

**Luca:** Everything, as I said, super safe, aiming for containerization, autonomy, respect for folders and system configurations.

**Claude:** Security features: secret scanning, immutable file protection, permission boundaries, audit logging, confirmation gates, `.gitignore` for sensitive files. Containerization (Docker) is not implemented. Autonomy features exist (overnight mode, scheduled routines, resource monitoring) but are not fully autonomous. No system configuration modifications are made.

---

**Luca:** PS: memory and claude projects

**Claude:** Session persistence via `core/session.py`. Knowledge persistence via `core/knowledge.py`. Claude Projects integration (using Claude's built-in project memory) is not explicitly implemented — the system uses its own file-based persistence.

---

**Luca:** Gotta decide a core nucleus of connected MCPs to be always prepared at setup.

**Claude:** tier1_essential in `mcp-nucleus.json` is always loaded: git, github, filesystem, memory, sequential-thinking, fetch, paper-search, arxiv. `core/mcps.py:classify_task()` always includes tier1 regardless of task.

---

**Luca:** We should also make sure that we get MCPs for startup and outreach activities all embedded into the workspace at setup.

**Claude:** tier8_startup includes: vercel, gamma, stripe, notion. These are configured but not installed automatically at setup.

---

**Luca:** The idea is that when the user creates a new project they automatically get the full set up with minimal work and that the machine handles the vast majority of "finding the right tool" under the hood with users only partially aware of the toolbox.

**Claude:** `init` copies all templates, creates workspace dirs, writes settings, creates state files, initializes git. `core/mcps.py` auto-classifies needed tiers based on task keywords. The user answers ~7 onboarding questions and gets a full project. However, MCP installation, conda setup, and LaTeX installation are not automated during init.

---

**Luca:** Other important items that should be there: the & sending to cloud claude.

**Claude:** Not implemented. There is no integration with Claude's cloud/web interface. All execution is via the local `claude` CLI.

---

**Luca:** Named sessions for automatic easier retrieval.

**Claude:** `core/session.py:create_session()` creates named sessions. `load_session()` retrieves by name. `list_sessions()` shows all sessions. `cli/main.py:start()` passes `--session-id` to Claude Code. Session data is persisted as JSON in `state/sessions/`.

---

**Luca:** Ultrathink and think hard automatically selected when task requires them.

**Claude:** `core/tokens.py:select_thinking_mode()` returns "ultrathink" for CRITICAL tasks (validate, prove, paper, publish) and "extended" for COMPLEX tasks (debug, design, research). The selection exists but is not wired into `execute_agent_task()`.

---

**Luca:** Estimates of token usage even if precise is not possible.

**Claude:** `core/tokens.py:estimate_tokens()` uses ~4 chars/token heuristic. `check_budget()` tracks session and daily usage. `ModelConfig` in `core/model_router.py` has `cost_per_1k_input` and `cost_per_1k_output` rates.

---

**Luca:** Hooks - lifecycle events.

**Claude:** Not implemented. There is no hook/event system. Claude Code has built-in hooks support, but the system doesn't define or register any lifecycle hooks.

---

**Luca:** Prompt suggestions / predictive follow-ups.

**Claude:** Not implemented. `defaults/PROMPTS.md` has structured prompts and `structure_prompt()` matches keywords, but there are no predictive follow-up suggestions after task completion.

---

**Luca:** Browser integration.

**Claude:** The `fetch` MCP is in tier1_essential for web access. No browser automation (Puppeteer, Playwright) is configured. No browser extension exists.

---

**Luca:** Agent skills (already partially discussed).

**Claude:** `templates/.claude/skills/` contains `code-style.md`, `figure-making.md`, `paper-writing.md`. These are loaded as part of the template structure. Skills are markdown files that agents can reference.

---

**Luca:** Markdown files that become commands.

**Claude:** Not implemented as a command system. The markdown files (agent definitions, skills, prompts) are reference documents, not executable commands. Claude Code's built-in slash commands from markdown files are not set up.

---

**Luca:** Agents that behave as human users answering / reprompting agents as a function of goal and current results.

**Claude:** `plan_execute_iterate()` supports re-planning based on previous results. The master agent concept routes tasks. However, there is no explicit "agent-as-human-reviewer" loop where one agent re-prompts another based on output quality.

---

**Luca:** Sandboxes and controlled freedom.

**Claude:** `core/security.py` provides file protection and secret scanning. Permission boundaries exist for cross-repo operations. No actual sandboxing (Docker containers, restricted file system) is implemented.

---

**Luca:** We could also exploit the agent SDK if useful for developing this project.

**Claude:** The Anthropic Agent SDK is not used. All agent execution goes through the `claude` CLI via subprocess. The SDK could provide more control over agent behavior, tool use, and conversation management.

---

**Luca:** Also something I read helps a lot is giving AI progressive instructions rather than all at once - that should definitely happen under the hood of our superhuman agent.

**Claude:** `.claude/CLAUDE.md` implements this as the "Progressive Instruction Protocol": Phase 1 ORIENT (read goals, constraints), Phase 2 EXPLORE (read code/data), Phase 3 PLAN (break into subtasks), Phase 4 EXECUTE (one subtask at a time), Phase 5 VALIDATE (falsify, compare to goal). This is the core instruction framework for all agents.

---

**Luca:** And the docker aspect I know little about we discussed at first.

**Claude:** A `docker/` directory exists in the project structure but is empty. No Dockerfile, docker-compose, or container configuration has been created. Docker is listed as detectable in `core/environment.py:discover_system()` and as a tier7_cloud MCP, but no containerization is implemented.

---

## Summary

### Fully Implemented
- CLI tool with init/start/overnight/status/config/paper commands
- 7 agent definitions with specialized roles
- Encyclopedia/knowledge persistence system
- Session management with snapshots
- Token budget estimation and thinking mode selection
- Multi-model routing with fallback chains
- Task DAG with parallel execution
- Reproducibility enforcement (run logs, artifact registry, dataset hashing)
- Resource monitoring (RAM, CPU, disk)
- Checkpoint management with cleanup policies
- Secret scanning and immutable file protection
- Onboarding questionnaire with settings
- Paper pipeline (LaTeX compilation, citations, figure management)
- Style transfer analysis and plagiarism checking
- TUI dashboard with 6 panels
- Figure gallery
- Notification system (email, Slack, desktop) with throttling
- Cross-repository linking with permission boundaries
- Autonomous routine definitions with audit logging
- Meta-rule detection and cheatsheet management
- GitHub Actions workflows (tests, lint, paper build)
- Formal specification document
- 176 passing tests

### Partially Implemented
- Voice pipeline (transcription stub, language detection, prompt structuring — but no mic input, translation is a stub)
- MCP configuration (70+ MCPs defined — but not auto-installed)
- Conda environment creation (function exists — not wired into init flow)
- Cross-project knowledge sharing (export/import exists — no automatic sync)
- Purchase suggestion flow (suggestion + audit — no confirmation receipt)

### Not Yet Implemented
- VS Code extension
- Mobile app / web dashboard
- Docker containerization / sandboxing
- Gemini / OpenAI integration
- RAG with vector embeddings (ChromaDB is a dependency but unused)
- Actual token counting from Claude CLI output
- Automatic meta-rule extraction from user prompts
- Cron scheduler for routines
- Task spooler integration
- Conversation markdown dumps
- Dual-repo structure (experiment + clean)
- Real-time scrolling output / tqdm progress
- Website generation
- Hooks / lifecycle events
- Predictive follow-ups
- Browser automation
- Agent SDK integration
- Interactive dashboard input (secure terminal for passwords)
- Automatic MCP discovery from GitHub registries
