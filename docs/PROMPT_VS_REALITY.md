# Prompt vs. Reality: How Each Sentence Was Addressed

This document pairs each sentence from Luca's founding prompt with a factual account of how the challenge was (or was not) solved in the `ricet` repository (v0.2.0).

---

**Luca:** I intend to create an app and/or a Visual Studio Code extension that allows the automation of scientific research by fully leveraging the potential of cloud code.

**Claude:** The project became `ricet` (Recursive Integration for Collaborative Experiments with Thinking), a Python CLI tool (`cli/main.py`, Typer-based) with 15+ commands rather than a standalone VS Code extension. It automates scientific research workflows by orchestrating Claude Code sessions, multi-agent swarms, and MCP integrations. There is no native VS Code extension yet; interaction happens through the terminal CLI and a Rich-based TUI dashboard (`cli/dashboard.py`).

---

**Luca:** In particular, I would like to build a system that allows a user to initialize and develop a project.

**Claude:** The `ricet init <name>` command (`cli/main.py`) launches an interactive onboarding flow defined in `core/onboarding.py` (1115 lines). It walks the user through a questionnaire, collects credentials, and scaffolds a full project workspace from the templates in `templates/`.

---

**Luca:** By initialization I mean that the user will provide a hyper-detailed description of a scientific project, together with specific requests for the agent and all the necessary keys.

**Claude:** During `ricet init`, the onboarding questionnaire prompts the user for a project description that gets written to `knowledge/GOAL.md` in the new project. API keys are collected and stored in a `.env` file. The template at `templates/knowledge/GOAL.md` serves as the structured placeholder for this hyper-detailed description.

---

**Luca:** We will discuss this in detail later.

**Claude:** Acknowledged — this was addressed incrementally throughout the 42 commits of development.

---

**Luca:** For example, the various API keys, GitHub access, and so on.

**Claude:** The onboarding flow in `core/onboarding.py` collects API keys (Anthropic, OpenAI, GitHub token, HuggingFace, W&B, etc.) and writes them to a `.env` file. The template `templates/config/settings.yml` has placeholders for `github`, `huggingface`, `wandb`, and other credential references. Security scanning in `core/security.py` uses regex patterns to detect accidentally committed secrets.

---

**Luca:** First and foremost, the agent will have to create a repository and organize it appropriately for the project, initialize it, and so on, on the local machine on which it is running.

**Claude:** The `ricet init` command creates the project directory, copies the full template structure (agents, skills, knowledge, config, paper, GitHub workflows), initializes a git repository, and makes an initial commit. This is implemented in `core/onboarding.py` and the CLI's `init` command.

---

**Luca:** To get started, the user may also upload material that must not be pushed, such as papers for inpainting or useful code to be recycled, specific instructions.

**Claude:** The template includes a `.gitignore` (generated during init) that excludes common heavy/private files. The `templates/` structure creates a `knowledge/` directory for instructions and constraints. However, there is no explicit "upload" UI or dedicated folder for reference papers or recyclable code at the template level — the user would manually place these files. The inpainting feature for papers is partially addressed in `core/style_transfer.py` (style analysis, plagiarism detection, academic tone scoring) but not a full reference-paper upload pipeline.

---

**Luca:** and the initialization of the repository will also contain various materials: first of all a properly configured gitignore to avoid all heavy files, and so on.

**Claude:** The project initialization generates a `.gitignore`. The security module (`core/security.py`) enforces that secrets and sensitive files (`.env`, `*.pem`, `secrets/`) are never committed.

---

**Luca:** as well as a series of useful files that we will now develop and that will be cross-repo, meaning they will essentially be the solid skeleton of this entire project, for example with preconfigured prompts and so on.

**Claude:** The `templates/` directory contains the cross-repo skeleton: 7 agent definitions in `templates/.claude/agents/` (master, researcher, coder, reviewer, falsifier, writer, cleaner), 3 skill files in `templates/.claude/skills/` (code-style, figure-making, paper-writing), knowledge templates, config files, paper templates, and GitHub workflows. The `defaults/` directory holds `PHILOSOPHY.md`, `CODE_STYLE.md`, `PROMPTS.md`, and `LEGISLATION.md` as cross-repo defaults.

---

**Luca:** This is to give you the general idea; then I will give you the specific instructions and you will have to do everything strictly as I describe.

**Claude:** Acknowledged.

---

**Luca:** So the system starts with the user initializing the project by providing everything necessary to get it started, and the agent simply builds the repository, prepares a detailed to-do list or at least an initial action plan to develop the project with a relatively high level of abstraction, i.e. at a high level, which will then be developed step by step during the development of the project itself.

**Claude:** After `ricet init`, a `state/TODO.md` is created with high-level tasks. The `state/PROGRESS.md` tracks achievements. The `core/prompt_queue.py` manages task queuing and priority. The overnight mode (`core/autonomous.py`) iterates through the TODO list, executing and refining step by step. The planning phase is embedded in the philosophy (`defaults/PHILOSOPHY.md`: ORIENT → EXPLORE → PLAN → EXECUTE → VALIDATE).

---

**Luca:** Likewise, the agent will set up a conda environment, and in doing so it will update a file where all the information necessary for its use is kept.

**Claude:** The `core/environment.py` module performs system discovery including conda/mamba detection. The template `templates/config/settings.yml` has a `compute` section. However, automatic conda environment creation during init is not fully implemented — the system detects existing environments but does not auto-create one with all dependencies. The overnight scripts (`scripts/overnight-enhanced.sh`) assume a mamba environment named `agent` exists.

---

**Luca:** In fact, the system must be able to consult each time a sort of project-specific encyclopedia, i.e. a set of information, for example how to do rsync between machines where the data are located and machines where the code is run, or the name of the conda environment, in short a series of project-specific tricks that the various agents will accumulate during the project.

**Claude:** This is the **encyclopedia** system, implemented in `core/knowledge.py` (266 lines). It provides auto-update functionality and search (HNSW vector search via claude-flow when available, keyword search as fallback). The template `templates/knowledge/ENCYCLOPEDIA.md` is the starting file that agents append to. The CLI command `ricet memory <query>` lets users search it.

---

**Luca:** So it is knowledge that, during the interaction of the agents with the reality of the scientific project and with the code, is formed and grows, and persists, and the agents must always be aware that they can then essentially do RAG to read this encyclopedia to understand all the tricks of the trade that previous agents before them have learned.

**Claude:** The `core/knowledge.py` module supports both keyword and vector (HNSW) search. The `core/rag_mcp.py` (353 lines) provides RAG integration via MCP servers. The `core/claude_flow.py` bridge enables hybrid memory (in-memory + persistent vector DB). Each agent definition in `templates/.claude/agents/` instructs agents to consult the encyclopedia. The `.claude-flow/` state directory persists memory across sessions.

---

**Luca:** Now I list in a chaotic way some of the features that this application or extension must have, and then we will draw conclusions to restructure this brainstorming a bit.

**Claude:** Acknowledged — the restructuring happened across 42 commits and 10 development phases.

---

**Luca:** First of all, the machinery must be capable of using cheap models for cheap operations.

**Claude:** The `core/model_router.py` (240 lines) implements 3-tier model routing: Tier 1 (Booster/free — formatting, lookups), Tier 2 (Haiku — simple tasks, $0.0002), Tier 3 (Sonnet/Opus — complex reasoning, $0.003–$0.015). Task complexity is classified and routed to the cheapest capable model. The `.swarm/model-router-state.json` persists routing state.

---

**Luca:** I'll give you an example: the user prompts by voice in their natural language; we want to transform the prompt into English, the language used to talk with AIs, and structure it from a disorganized brainstorming of the user's words into an efficient prompt, using for example a collection of prompts that we will discuss later.

**Claude:** The `core/voice.py` (5.0 KB) handles audio transcription, language detection, and prompt structuring — converting spoken input into structured English prompts. The `core/prompt_suggestions.py` (433 lines) provides auto-generated prompt recommendations. The `defaults/PROMPTS.md` contains the prompt collection. However, actual voice recording/streaming from a mobile app or VS Code is not yet implemented; `voice.py` defines the processing pipeline but relies on an external transcription MCP server.

---

**Luca:** This translation prompting and intelligent prompting does not need to be done by an expensive agent.

**Claude:** The model router (`core/model_router.py`) classifies prompt translation as a low-complexity task, routing it to Tier 1 or Tier 2 models (Haiku or free alternatives) rather than Opus.

---

**Luca:** In fact, we want all agents to be 4.5 opus with thinking enabled for scientific operations, while this kind of basic and obvious operations must be done with the cheapest models possible, not necessarily Claude.

**Claude:** The `core/tokens.py` (3.9 KB) implements thinking mode selection. The default configuration targets Opus 4.5 with thinking (3% extended thinking budget) for scientific operations. The model router explicitly handles the split: Opus for architecture, validation, and complex reasoning; Haiku/Sonnet for simpler tasks. The philosophy in `defaults/PHILOSOPHY.md` encodes this as a core principle.

---

**Luca:** I was just talking about voice. One of the first features we must develop is that in this dashboard, which will be available either via a mobile app or via a VS Code extension, the key feature is that the user can directly prompt by voice in their language, whatever it is, and the machinery translates into English and transforms the user's brainstorming into a structured prompt that goes to the agent.

**Claude:** The `core/voice.py` module defines the voice-to-prompt pipeline. The `cli/dashboard.py` (14.5 KB) implements a Rich TUI dashboard showing progress, TODO, and metrics — but it is terminal-based, not a mobile app or VS Code extension. Mobile access is documented in `docs/tutorials/mobile-access.md` as a configuration guide (likely using ttyd or similar web terminal), but a native mobile app does not exist. The Docker setup exposes port 7681 for ttyd web terminal access, which could serve as a mobile-accessible dashboard.

---

**Luca:** Moreover, in this idea of mine, which we will then refine together by reasoning about the current capabilities of agents, I would like the dashboard to be a place where the user interacts with a master agent, which in turn distributes tasks among different sub-agents in an extremely structured way, always keeping for the user a list of currently active sub-agents, their operations, and their token consumption.

**Claude:** The master agent is defined in `templates/.claude/agents/master.md` and routes tasks to 6 sub-agents. The `core/agents.py` (540 lines) implements task routing, DAG execution, and parallel execution with budget allocation (Coder 35%, Falsifier 20%, Researcher 15%, Writer 15%, Reviewer 10%, Cleaner 5%). The `ricet agents` CLI command shows active agent status. The `ricet metrics` command shows token usage. The `cli/dashboard.py` TUI displays active agents and progress. Token consumption tracking is in `core/tokens.py`.

---

**Luca:** After voice prompting, I would also like us to build a series of cheat sheets.

**Claude:** These are implemented as the skill files in `templates/.claude/skills/` (code-style.md, figure-making.md, paper-writing.md), the knowledge files in `templates/knowledge/` (ENCYCLOPEDIA.md, CONSTRAINTS.md, GOAL.md), and the defaults in `defaults/` (PHILOSOPHY.md, CODE_STYLE.md, PROMPTS.md, LEGISLATION.md). They serve as the "cheat sheets" agents consult.

---

**Luca:** I mentioned one before, which is the one that agents update with all the tricks of the trade learned on the scientific project, and also basic things like, okay, I need this conda environment, etc., so that there do not have to be repetitions by the user.

**Claude:** This is `knowledge/ENCYCLOPEDIA.md`, managed by `core/knowledge.py`. The auto-update mechanism appends new learnings after each task. The `core/meta_rules.py` (3.4 KB) automates meta-rule capture from task history so the user does not have to repeat instructions.

---

**Luca:** Other cheat sheets include a cheat sheet that is a collection of prompts that I will provide later, which work, and when we transform the user's voice from their natural language into English, we will also do a RAG or otherwise use this prompt collection to find an appropriate prompt and thus build an efficient prompt for the sub-agents to run.

**Claude:** The `defaults/PROMPTS.md` contains the prompt collection. The `core/rag_mcp.py` provides RAG integration. The `core/prompt_suggestions.py` generates prompt recommendations based on context. The voice pipeline in `core/voice.py` is designed to structure prompts using this collection. However, full RAG over the prompt collection (embedding + retrieval) depends on claude-flow's HNSW vector memory being available.

---

**Luca:** Among other features, we will need to store securely and appropriately all the user's API keys, which will therefore be provided at the moment of initialization of the new project.

**Claude:** API keys are collected during `ricet init` (via `core/onboarding.py`) and stored in `.env` files. The `core/security.py` module scans for accidentally committed secrets using regex patterns for API keys, tokens, and private keys. The `.gitignore` excludes `.env` files. Immutable file protection prevents modification of secret files.

---

**Luca:** Then there is the issue of reproducibility: I would like it to always be mentioned and somehow enforced in all the different rules of the game that everything must be traceable backwards and reproducible.

**Claude:** The `core/reproducibility.py` (5.2 KB) implements run logging (command, timestamp, git hash, parameters, metrics), an artifact registry with SHA-256 checksums, and environment capture. The philosophy (`defaults/PHILOSOPHY.md`) states "Reproducibility is Non-Negotiable" as principle #10: pin dependencies, seed randomness, log everything. GitHub Actions workflows in `templates/.github/workflows/` enforce CI checks.

---

**Luca:** Another feature: one of the main characteristics I have noticed in dense interaction with cloud tools in recent times is the lack of memory, i.e. when chat compaction happens, memory tends to crumble and many important pieces of information are lost.

**Claude:** This is addressed through multiple persistence mechanisms: the encyclopedia (`core/knowledge.py`), the claude-flow hybrid memory backend (HNSW + persistent storage in `.claude-flow/`), the `.swarm/memory.db` SQLite database, and the state files (`state/PROGRESS.md`, `state/TODO.md`). All critical information is written to disk rather than relying on chat context.

---

**Luca:** One of the mitigation mechanisms I was thinking of is creating these cheat sheets.

**Claude:** Implemented as described above: skills, knowledge files, defaults, and the encyclopedia all serve as persistent cheat sheets that survive context compaction because they are on-disk files, not in-context memory.

---

**Luca:** Another cheat sheet I will create later includes, for example, information on how to write a good paper, another on how figures should be made, and so on.

**Claude:** `templates/.claude/skills/paper-writing.md` covers academic writing guidelines. `templates/.claude/skills/figure-making.md` covers matplotlib configuration, colorblind-safe palettes (#0077BB, #EE7733, #009988, #CC3311, #AA3377), rcParams for publication quality, and PDF export rules.

---

**Luca:** So there will be various ones that machine learning must retrieve, but in very long conversations, where perhaps one agent prompts another agent and there is back-and-forth between agents, I fear that this issue of certain elements already discussed being lost from the long context will arise again. So this is an issue we absolutely have to address.

**Claude:** The mitigation strategy is multi-layered: (1) on-disk files that agents re-read each session, (2) claude-flow's HNSW vector memory for semantic retrieval, (3) the encyclopedia that accumulates learnings, (4) session state persistence in `.claude-flow/sessions/`, and (5) the `core/meta_rules.py` module that auto-captures rules. This does not fully eliminate the problem — within a single very long Claude Code session, context compaction still occurs — but the persistent file system serves as external memory.

---

**Luca:** I was saying: a dashboard jointly accessible either from VS Code or from mobile, which allows monitoring multiple actions simultaneously.

**Claude:** The `cli/dashboard.py` (14.5 KB) is a Rich TUI dashboard for terminal use, showing TODO status, progress, active agents, and resource metrics. Docker exposes port 7681 for ttyd web terminal, enabling remote/mobile access to the TUI. A native VS Code extension or mobile app with a graphical dashboard has not been built.

---

**Luca:** For example, I am in a complex project, I am giving instructions to the agent on how to behave for different matters, maybe one related to writing a paragraph of the paper, another to a deep learning algorithm, and so on, and I would like this to be distributed by the master agent.

**Claude:** The master agent (`templates/.claude/agents/master.md`) routes tasks to specialized sub-agents: the writer agent handles paper paragraphs, the coder agent handles algorithms. The `core/agents.py` implements DAG execution and parallel task routing. Budget allocation ensures resources are distributed appropriately.

---

**Luca:** I send all the voice messages in a single channel, the master agent understands to whom to forward them, always minimizing the cost in terms of tokens.

**Claude:** The `core/voice.py` handles voice input processing. The master agent definition includes task routing logic. The `core/model_router.py` minimizes token cost by routing to the cheapest capable model. However, a true "single channel" for voice messages that the master agent triages in real-time is not implemented as a streaming service — it would require the voice pipeline and master agent to operate continuously, which is beyond the current CLI-based interaction model.

---

**Luca:** And also suggest where you think I might be thinking in overkill and could easily burn tokens; I have the 200-franc-per-month Claude plan and we want to exploit it as much as possible, but we also do not want to go into overkill, I do not know how easy that is.

**Claude:** The `core/tokens.py` (3.9 KB) implements token estimation, budget tracking, and thinking mode selection. The `ricet metrics` command shows token usage and costs. The model router enforces cost minimization. The philosophy warns against overkill. However, precise real-time token metering against the monthly plan limit is not implemented — estimates are approximate.

---

**Luca:** Among other features there must be a "don't please me" feature, i.e. we must ensure that agents always respond in a grounded, objective way and not try to please the user, without necessarily tearing them down, but there is a tendency to please the user that we must avoid.

**Claude:** Principle #1 in `defaults/PHILOSOPHY.md` is "Never Please the User — Be objective, challenge assumptions." The falsifier agent (`templates/.claude/agents/falsifier.md`) is specifically designed to attack results and find flaws. The reviewer agent (`templates/.claude/agents/reviewer.md`) provides strict, honest code review. These behavioral instructions are baked into the agent definitions that get copied into every new project.

---

**Luca:** Moreover, we must allow Claude agents to use Gemini when Claude agents cannot access certain websites where Gemini excels.

**Claude:** The `core/browser.py` (293 lines) provides headless browser automation via Puppeteer MCP with fallback to curl/wkhtmltopdf. However, there is no explicit Gemini integration for web access. The model router supports fallback chains, but Gemini is not configured as a fallback model. This feature is not yet implemented.

---

**Luca:** Then there are many other features. We want connections with various personal objects. For example, a user might want to link their website and the agent should be able, if the user provides the repository that builds the website, etc., to integrate, for example, a feature in the website related to the project.

**Claude:** The `core/website.py` (462 lines) handles static website generation and deployment (GitHub Pages, Netlify). The `core/cross_repo.py` (5.8 KB) implements cross-repository coordination with permission boundaries. The `core/multi_project.py` (315 lines) manages multi-project parallel operations. So the infrastructure for repo-to-repo interaction exists, though it has not been battle-tested with real website integration workflows.

---

**Luca:** So also a sort of repo-to-repo interaction.

**Claude:** Implemented in `core/cross_repo.py` with permission levels (read-only, execute, write, admin) and coordinated commits for multi-repo atomic operations.

---

**Luca:** Let's hypothesize that my agent works on a branch of my project-specific repository and then I also want it to be constantly updating my main repository that builds my website.

**Claude:** The `core/git_worktrees.py` (261 lines) manages git worktrees for isolated branch work. Combined with `core/cross_repo.py`, the system can theoretically work on a project branch while updating another repo. However, an automated "constantly updating" pipeline (e.g., a watcher or hook that triggers website repo updates after each project commit) is not implemented.

---

**Luca:** Obviously everything must be done securely, using Docker containerization to prevent the agent from modifying system configurations without my authorization, which could be potentially dangerous, or especially from deleting my files or doing other stupid things.

**Claude:** The `docker/` directory contains a multi-stage `Dockerfile` (Ubuntu 24.04 base, Python 3.12, Node.js 20, LaTeX, claude-flow) and `docker-compose.yml`. The `core/security.py` enforces repo root boundaries, immutable file protection, and secret scanning. The philosophy principle #12 is "Safety First — Docker isolation, permission levels, no delete without backup." The Docker setup is defined but requires the user to actively run inside the container; there is no enforcement that prevents non-containerized usage.

---

**Luca:** So we also need guardrails so that the agent behaves properly.

**Claude:** Guardrails are implemented across multiple layers: `core/security.py` (secret scanning, immutable files, repo root enforcement), `core/verification.py` (claim extraction, factuality checking), the falsifier agent (attacks results), permission boundaries in `core/cross_repo.py`, and audit logging to `state/audit.log`. The claude-flow security directory (`.claude-flow/security/`) maintains audit logs.

---

**Luca:** Other fundamental rules: agents must always, as soon as possible, use code, i.e. not do things "by hand," which would cost a huge amount of tokens for many operations, but instead write code, as agents already tend to do well, to automate things deterministically.

**Claude:** This is encoded in the philosophy (`defaults/PHILOSOPHY.md`) and in agent definitions. The coder agent (`templates/.claude/agents/coder.md`) is specifically tasked with implementation and automation. The code style rules (`defaults/CODE_STYLE.md`) emphasize vectorization, efficiency, and automation. This is a behavioral instruction rather than an enforced constraint.

---

**Luca:** Then there is an issue of cleanliness: often agents go into crazy mode and start generating a huge amount of code and data, which is obviously risky and problematic in many ways.

**Claude:** The cleaner agent (`templates/.claude/agents/cleaner.md`) is dedicated to refactoring, optimization, and code hygiene. The code style defaults (`defaults/CODE_STYLE.md`) mandate functions under 50 lines, minimal code, and no fluff. The `core/resources.py` monitors disk usage. However, automatic detection of "crazy mode" code generation bloat is not implemented as a real-time guardrail.

---

**Luca:** We must ensure that every so often, when a task is complete, without losing things, we maintain very frequent git pushes, and this too must be incorporated into the structure of the app/VS Code extension, i.e. agents must push aggressively, being careful not to step on each other.

**Claude:** Philosophy principle #5 is "Commit Aggressively — Meaningful commits after subtasks." The `core/devops.py` (404 lines) handles CI/CD integration, GitHub Actions, and release management. The git worktrees system (`core/git_worktrees.py`) enables concurrent branch work to avoid conflicts. However, automated aggressive pushing (auto-commit + auto-push after each subtask) is defined as a behavioral rule in agent instructions rather than an enforced hook that triggers automatically.

---

**Luca:** This is something I believe Claude has solved and we must ensure it works, i.e. that there are no merging problems. So constant pushing so that everything is tracked, but also constant cleaning, so that the repository remains usable, clear, and functional.

**Claude:** The git worktrees module provides branch isolation. The cleaner agent handles periodic cleanup. The dual-repo pattern (`core/two_repo.py`) separates messy experiments from clean production code. Merge conflict prevention through worktrees is the primary strategy.

---

**Luca:** In fact, I would like to propose a dual structure, i.e. for each project two sub-repositories are built, or rather two repositories altogether perhaps, I don't know how you prefer: one for experiments and general messiness, where we put everything we do, and it does not need to be hyper-clean, even though it obviously must be ordered and usable for an external user who is not a machine; and another super-clean one that could potentially go into the hands of users, which is very organized and easy for the user to review.

**Claude:** Implemented in `core/two_repo.py` (6.4 KB). It defines the dual-repo pattern: an experiments repository (for exploration, intermediate results, drafts) and a clean repository (production-quality, minimal, well-documented). The module handles coordinated operations between the two repos.

---

**Luca:** In fact, the code must always be minimal, concise, straight to the point, without fluff, it must be optimized, and this must be clear to the agents.

**Claude:** `defaults/CODE_STYLE.md` and `templates/.claude/skills/code-style.md` encode these rules: type hints, functions under 50 lines, vectorization, no unnecessary abstractions. Philosophy principle #11 is "Code Quality Standards." The cleaner agent enforces these during cleanup passes.

---

**Luca:** For example, everything must be vectorized as soon as possible, and commented not in an excessive and tiring way, but in a way that the user can always know what is going on.

**Claude:** Vectorization is mentioned in the code style defaults. Comment guidelines are part of the code style skill. The philosophy balances verbosity (for logging/tracking) with code conciseness.

---

**Luca:** So we should also automate code-cleaning passes, and every code-cleaning pass must ensure that the effect does not change, i.e. when the agent that cleans the code is called, the agent must then rerun the code and ensure that the results are exactly the same as before the cleaning.

**Claude:** The cleaner agent definition (`templates/.claude/agents/cleaner.md`) specifies this workflow. The `core/reproducibility.py` provides artifact checksums (SHA-256) that could be compared before/after cleaning. However, an automated "clean then verify identical results" pipeline is not wired up as a single command — it relies on the cleaner agent following its instructions to re-run and compare.

---

**Luca:** Cleaning also includes comments. Perfect.

**Claude:** Included in the cleaner agent's responsibilities.

---

**Luca:** Then I would like to develop a paper-making feature, i.e. in every repository there is also the possibility of extracting a paper, according to the user's directions, using a predefined LaTeX template inside the repository that I will provide later.

**Claude:** The `core/paper.py` (5.2 KB) implements the paper pipeline: LaTeX compilation, citation management, and figure generation. The template `templates/paper/main.tex` provides a structured LaTeX document with sections (abstract, intro, methods, results, discussion, conclusion). The `templates/paper/references.bib` is the BibTeX file. The CLI command `ricet paper build|check|update|modernize` drives the pipeline. A GitHub Actions workflow (`templates/.github/workflows/paper-build.yml`) automates LaTeX compilation and PDF artifact upload.

---

**Luca:** For now you can put a very basic one, then we will improve it, but structure it already.

**Claude:** The current `templates/paper/main.tex` is a basic but structured LaTeX template. The `templates/paper/journals/` directory exists for future journal/conference-specific templates.

---

**Luca:** So when the project repository is created, the subpart of the repository that constitutes a baseline for a paper is also created, with all the rules that we will put into the paper-making rules.

**Claude:** When `ricet init` runs, the `paper/` directory with `main.tex`, `references.bib`, and `journals/` is created as part of the template scaffolding. The paper-writing skill (`templates/.claude/skills/paper-writing.md`) contains the rules.

---

**Luca:** For example, that all plots must be rasterized but at the same time vector where possible, using rcParams42 so that all text is editable, PDFs, i.e. all figures must be exported in PDF and embedded into the documents, in short a series of rules that we will then strengthen and that allow, when the user says "make me a version of the paper" or "modernize the version of the paper" or "continue integrating information from new results into the paper," and so on, the agent to do it autonomously.

**Claude:** The figure-making skill (`templates/.claude/skills/figure-making.md`) configures matplotlib rcParams for publication quality, specifies PDF export, colorblind-safe palettes, and text editability. The `core/paper.py` handles figure generation with these settings. The CLI commands `ricet paper update` and `ricet paper modernize` map to these use cases. The writer agent (`templates/.claude/agents/writer.md`) handles autonomous paper updates.

---

**Luca:** In fact, I ask not only for a LaTeX template, but also to prepare—i.e. not that I ask you, but the goal is also to prepare through this app/VS Code integration—a series of functions, including inpainting, whereby the user can upload reference papers and the agent, without plagiarizing, must be able to transform the style into that of the reference paper, in addition to following the general paper-making rules in one of the cheat sheets I mentioned that will be provided.

**Claude:** The `core/style_transfer.py` (6.4 KB) implements writing style analysis, plagiarism detection (scoring), and academic tone scoring. It can analyze a reference paper's style and attempt to match it. However, the "inpainting" concept (deeply adapting writing style from reference papers while avoiding plagiarism) is partially implemented — the module provides the analysis tools but a full inpainting workflow (upload reference → analyze → rewrite in that style) is not a one-command feature.

---

**Luca:** When the repository is created or a new sub-agent is spun up, and so on, we must obviously ensure that there are constraints whereby the agent explores the repository and becomes familiar with it, or at least with the part that concerns it.

**Claude:** Agent definitions in `templates/.claude/agents/` instruct each agent to explore relevant parts of the repository. The `templates/.claude/CLAUDE.md` project-level instructions (80 lines max, self-maintained) serve as the entry point for agent orientation. The philosophy's progressive instruction model (ORIENT → EXPLORE → PLAN → EXECUTE → VALIDATE) starts with exploration.

---

**Luca:** In fact, each sub-agent could refer to different instruction files, some of which are logically modifiable, while others must absolutely not be touched because they characterize the repository itself or the spaces where the user's rules are simply transcribed.

**Claude:** The `core/security.py` implements immutable file protection — certain files (`.env`, secrets, user rule files) cannot be modified by agents. The distinction between modifiable files (encyclopedia, TODO, progress) and immutable files (GOAL, CONSTRAINTS, user-provided rules) is enforced through the security module's immutable file list.

---

**Luca:** In fact, for each prompt not only must there be an execution that tries to realize the user's wishes, but also any meta-rules not yet present in the cheat sheets must be incorporated into the cheat sheets.

**Claude:** The `core/meta_rules.py` (3.4 KB) implements automatic meta-rule capture from task history. It extracts implicit rules from user instructions and appends them to the appropriate cheat sheet/skill file. This is the automated "learn from every prompt" mechanism.

---

**Luca:** For example, I realize that the machine is not working well from the point of view of representing certain ideas in plots, I give very specific instructions and I do not want to have to give them again identically a second time. I want this information to be, at the moment I prompt, automatically also added to the cheat sheet, without me having to tell Claude "look, add it to the cheat sheet." This too must be automated.

**Claude:** This is the exact purpose of `core/meta_rules.py`. It parses user instructions, detects meta-rules (e.g., "always use log scale for loss plots"), and auto-appends them to the relevant skill file or encyclopedia. The automation is defined in code; whether it reliably triggers in practice depends on the orchestration layer invoking it after each user prompt.

---

**Luca:** Then it must be ensured that the agent never guesses, but when it is uncertain it uses web search, especially because often solutions already exist and it is simply necessary for the agent to use web search to document itself.

**Claude:** Philosophy principle #3 is "Never Guess — Search docs, ask when uncertain." The `core/browser.py` provides web access via Puppeteer MCP or curl fallback. The MCP nucleus includes the `fetch` server in Tier 1 (always loaded) for web retrieval. This is primarily enforced through agent instructions rather than a technical mechanism that detects guessing.

---

**Luca:** Obviously web search consumes tokens, so it must be used judiciously.

**Claude:** The model router and token tracker (`core/tokens.py`) account for web search costs. The philosophy emphasizes token awareness. Judicious use is an instruction to agents rather than an enforced limit.

---

**Luca:** And we must also ensure certain behavioral rules, such as being concise and testing autonomously.

**Claude:** Philosophy principles include verbosity for logging but conciseness in code. Principle #4 is "Test Small, Then Scale — Downsample first, 1 epoch, then scale." The `core/auto_debug.py` (296 lines) provides automated error parsing, fix suggestion, and retry (3 iterations max).

---

**Luca:** In fact, I want that whenever code is created, it is run on a small scale, and this must be made clear: not at full scale at first, but a downsampling, in short something manageable, and the agent always tests the code end-to-end and ensures it works before scaling up, before giving it to the user.

**Claude:** This is principle #4 in the philosophy: "Test Small, Then Scale." The overnight mode instructions and agent definitions encode this: "Start with a baseline, measure, and improve. When training models, first run 1 epoch to confirm the pipeline works end-to-end and losses don't blow up, only then scale up." Enforcement is through agent instructions; there is no automatic downsampling mechanism.

---

**Luca:** In fact, most of the code must be run in the background and the agent must monitor it.

**Claude:** The `core/task_spooler.py` (257 lines) implements task scheduling, batching, and execution monitoring. The `core/autonomous.py` handles background execution. The scripts (`scripts/overnight.sh`, `scripts/overnight-enhanced.sh`) launch background processes. The overnight mode is explicitly designed for unattended background execution with monitoring.

---

**Luca:** This monitoring aspect is central to the app/VS Code extension/web app, however we want to define it.

**Claude:** The `cli/dashboard.py` TUI provides real-time monitoring of TODO status, active agents, progress, and resource metrics. The Docker setup exposes port 7681 for remote web terminal access. A dedicated web app or VS Code extension panel for monitoring has not been built.

---

**Luca:** In fact, this monitoring section must be constantly live, so there must be very verbose tracking, so we must also—indeed this is fundamental in all aspects—tell the agent to be extremely verbose, because it is very useful both for the agent itself to self-diagnose its behavior and understand what it is doing, and to give responses to the user about what is happening.

**Claude:** Philosophy principle #6 is "Be Extremely Verbose — Log what/why/how/learned." The `core/reproducibility.py` logs all runs. The `.claude-flow/logs/` directory stores execution logs. The state files (`state/PROGRESS.md`, `state/TODO.md`) maintain high-level tracking. Agent definitions instruct verbose output.

---

**Luca:** And for each activity there must be progress tracking, in the style of TQM, maybe also with scrolling verbose output, so the user knows that things are happening, knows how they are progressing, and also the sub-agents themselves can observe themselves.

**Claude:** The `state/PROGRESS.md` tracks achievements. The `state/TODO.md` tracks tasks. The `cli/dashboard.py` renders these in a TUI. The Rich library provides formatted, scrollable terminal output. However, a true tqdm-style progress bar per sub-agent activity is not implemented — progress is tracked at the task level, not at a granular operation level with percentage completion.

---

**Luca:** Ideally they can also observe each other, so maybe one sub-agent needs information about what another sub-agent is doing, like in an office, and they can look at each other.

**Claude:** The claude-flow integration (`.claude-flow/`) provides shared state via the hybrid memory backend and agent session files. The `.swarm/memory.db` SQLite database enables swarm coordination. Shared data in `.claude-flow/data/` is accessible to all agents. The `core/claude_flow.py` bridge enables inter-agent communication through the claude-flow mesh topology. Whether agents can truly "observe each other" in real-time depends on claude-flow's capabilities.

---

**Luca:** So having a common space where these documents are constantly visible to the sub-agents who need to understand what is happening, as well as the user being able to see them without having to go crazy clicking, especially if they have wrist or hand pain inside a repository, but simply by looking at their screen and interacting by voice with the machinery.

**Claude:** The `state/` directory serves as the common space (PROGRESS.md, TODO.md, audit.log). The encyclopedia (`knowledge/ENCYCLOPEDIA.md`) is shared. The dashboard (`cli/dashboard.py`) shows this information without requiring navigation into the repo. Voice interaction is defined in `core/voice.py` but is not a fully working real-time interface — the user still primarily interacts via the CLI.

---

**Luca:** Furthermore, regarding the paper, I go back a bit, again I apologize for the lack of sequence, regarding the structure of the paper, we must also ensure that all references are built properly using the PubMed MCP, and that a BibTeX file is built and compiled properly, etc.

**Claude:** The MCP nucleus (`defaults/MCP_NUCLEUS.json`) includes `paper-search` and `arxiv` in Tier 1 (always loaded). PubMed is listed among literature search integrations. The `templates/paper/references.bib` is the BibTeX file. The `core/paper.py` handles citation management. The GitHub Actions workflow `paper-build.yml` compiles LaTeX with biber. However, automatic PubMed MCP-to-BibTeX pipeline (search → fetch citation → format → append to .bib) is not a single automated function yet.

---

**Luca:** In the creation of the content environment, we must also ensure that the agent installs everything needed to then make the paper and everything else I describe in this chat. For example, a Makefile comes to mind for making the paper.

**Claude:** The Docker image installs `texlive-full`, `biber`, and `latexmk`. The `core/environment.py` performs system discovery to verify LaTeX availability. A `Makefile` for the paper is not included in the templates — paper building is handled through `ricet paper build` and the GitHub Actions workflow instead.

---

**Luca:** One of the risks, obviously, is that working at this scale, a user might crash, run out of memory, or otherwise overuse machine resources, run out of disk space, and so on. Therefore the machinery must also constantly check, with a certain rigor and logic, how many resources are available and possibly make decisions accordingly.

**Claude:** The `core/resources.py` (4.9 KB) implements resource monitoring: CPU usage, memory usage, GPU monitoring, disk space tracking, and checkpointing. It can trigger decisions based on resource thresholds. The Docker health check runs every 30 seconds. The overnight-enhanced script includes resource monitoring.

---

**Luca:** In fact, the idea is that there is extensive checkpointing, but at the same time agents then autonomously delete those files that were important for checkpointing and not losing time in case of unexpected downstream crashes, but that occupy memory, for example. So we want this type of resource management to also be totally autonomous, so that the user does not have to repeat things ten times to the agents, or even more.

**Claude:** The `core/resources.py` includes checkpointing functionality. The `core/autonomous.py` saves state after each subtask. Automatic checkpoint cleanup (deleting old checkpoints when disk is low) is described as a goal in the resource management module but the autonomous deletion logic is not fully implemented as a self-triggering routine.

---

**Luca:** Then we would also like to set up some autonomous routines, and I don't know how difficult this is. For example, that the agent can buy a machine on Hetzner to host a website and buy a domain on Namecheap, or alternatively monitor websites, for example monitor exploding topics every day and based on what it observes, monitor the news, make decisions and possibly also send emails to users.

**Claude:** The `core/notifications.py` (6.0 KB) implements email (SendGrid) and Slack notifications with formatted message templates. The `core/autonomous.py` supports scheduled routines. The MCP nucleus includes Stripe (Tier 8) for payment operations. However, Hetzner machine purchasing, Namecheap domain registration, Exploding Topics monitoring, and news monitoring are not implemented. These would require specific MCP servers or API integrations that do not exist in the current codebase.

---

**Luca:** So for example, an email could be when you need authorization from Luca for critical matters like confirming a purchase or entering a credit card, because the user will be able to confirm purchases that you suggest, for example for hosting a website, a more trivial idea, then in that case we want to develop that the machinery is able to send an email to the user.

**Claude:** The `core/notifications.py` supports sending emails via SendGrid and Slack messages. The security module defines confirmation gates for autonomous actions. The infrastructure for "email user for authorization" exists at the notification level, but an end-to-end "suggest purchase → email user → wait for confirmation → proceed" workflow is not wired up.

---

**Luca:** so if the user is not on the dashboard but is, for example, on a lunch break, they can see the email and provide the necessary information so the workflow continues.

**Claude:** The notification system can send emails when the user is away. However, a mechanism for the user to respond to an email and have that response feed back into the running workflow (e.g., reply "approved" to continue) is not implemented.

---

**Luca:** And indeed we want monitoring that sends emails to the user every roughly two hours if the user does not provide key information needed to proceed that the machinery requires, maximum two emails per hour because otherwise the user cannot take it anymore.

**Claude:** The notification module has rate-limiting awareness in its design, but automated periodic reminder emails (every 2 hours, max 2/hour) for pending user decisions are not implemented as a scheduled routine.

---

**Luca:** We also want to make space for the user to upload databases and connect their tools, for example connect email, connect Slack, and suggest other essential tools to connect for a scientific researcher.

**Claude:** The MCP nucleus (`defaults/MCP_NUCLEUS.json`) pre-configures 70+ tool integrations across 8 tiers, including databases (Tier 2: postgres, sqlite, duckdb, chroma, snowflake, supabase), communication (Tier 6: slack, gmail, sendgrid), and many others. The onboarding collects credentials for these services. The `core/mcps.py` auto-discovers and lazy-loads MCPs based on keyword triggers. Database upload/connection is supported through MCP servers rather than a dedicated upload UI.

---

**Luca:** I'm not sure about this, we'll reason better about it later, but we were talking about sub-agents, and it is probably also important that sub-agents have specialized functions.

**Claude:** Seven specialized agents are defined in `templates/.claude/agents/`: master (routing), researcher (literature), coder (implementation), reviewer (quality), falsifier (attack results), writer (papers/docs), and cleaner (refactoring). Each has a detailed role description, responsibilities, and output format.

---

**Luca:** For example, a central fact in the scientific process is to do a reverse destruction of the result, i.e. let's suppose the agent obtains a good result, then we will need agents that in all ways try to understand whether there could be cheating, i.e. whether there could be information leakage, for example, and whether the result is invalidated by some procedure that negates the initial objectives and confuses and falsifies the results, so a sort of falsifier, right?

**Claude:** The **falsifier agent** (`templates/.claude/agents/falsifier.md`) is exactly this. It is dedicated to Popperian falsification: attacking results, finding information leakage, checking for confounders, and attempting to invalidate findings. It receives 20% of the agent budget, the second-highest allocation after the coder.

---

**Luca:** We want a Popperian machine that promotes scientific ideas, but above all destroys them and sees what withstands the blows. This is absolutely central. I should perhaps have clarified this before; perhaps this is the most important thing of all.

**Claude:** Philosophy principle #2 is "Popperian Falsification — Try to break results, not validate." The falsifier agent, combined with the verification module (`core/verification.py` — claim extraction, factuality checking), embodies this principle. The `core/doability.py` (509 lines) also performs feasibility analysis and risk assessment before execution begins.

---

**Luca:** Then, as I was saying before, again I apologize for the disorder, about running jobs in the background. It goes without saying that while agents run jobs in the background, they must also do iterative debugging, so suppose a project is running in the background, crashes, the agents must debug and continue run, debug, run, debug until completion.

**Claude:** The `core/auto_debug.py` (296 lines) implements exactly this: error parsing, fix suggestion, and automatic retry with a maximum of 3 iterations. The overnight mode (`core/autonomous.py`) runs this debug-retry loop. The scripts (`scripts/overnight-enhanced.sh`) wrap execution with error handling.

---

**Luca:** Obviously if it goes into crisis, it must handle it accordingly; if it doesn't get out of it and hours pass and it still hasn't debugged, it should resolve itself, but I believe Claude is currently so good that it does not enter this type of routine. Perfect.

**Claude:** The 3-iteration retry limit in `core/auto_debug.py` prevents infinite debug loops. If the agent cannot fix the issue after 3 attempts, it logs the failure and moves to the next task. The notification system can alert the user. Graceful crisis handling is defined but has not been stress-tested at scale.

---

**Luca:** Any sub-agents must also have a sort of role description and related rules in this structure of MD files that we would like to make cross-repo.

**Claude:** Each agent has a markdown definition file in `templates/.claude/agents/` (master.md, researcher.md, coder.md, reviewer.md, falsifier.md, writer.md, cleaner.md). These are copied into every new project during `ricet init`, making them cross-repo. The definitions include role descriptions, responsibilities, tool access, and output format rules.

---

**Luca:** Moreover, it would be nice, but I have no idea how possible this is, that any learnings of a given user are shared across all their repositories, so let's say I start project A, and in project A there is a lot of meta-learning by the agents, there is a construction of an infrastructure, these behavior files are updated. I would like them to be transferable, if the user wishes, also to other projects, in order to avoid repetition. A sort of continuously growing encyclopedia.

**Claude:** The `core/multi_project.py` (315 lines) manages multi-project operations and result aggregation. The `core/cross_repo.py` enables cross-repository coordination. However, an explicit "sync learnings from project A to project B" feature — where the encyclopedia and meta-rules from one project are automatically offered to another — is not implemented as a dedicated mechanism. The shared defaults in `defaults/` serve as a static cross-project baseline, but dynamic learning transfer between projects does not exist yet.

---

**Luca:** A sort of continuously growing encyclopedia.

**Claude:** Within a single project, the encyclopedia grows via `core/knowledge.py` and `core/meta_rules.py`. Across projects, this continuous growth does not carry over automatically. This cross-project encyclopedia feature is not yet implemented.

---

**Luca:** Then, okay, regarding interactive demos for the user, obviously the agent must then develop notebooks instead of scripts, but the default must obviously always be only scripts, and well-made scripts, manageable with proper parallelization.

**Claude:** The code style defaults emphasize scripts as the default output. The MCP nucleus includes Jupyter (Tier 3) for notebook creation when needed. The `cli/gallery.py` (2.5 KB) provides a figure gallery viewer for experiment outputs. The distinction "scripts by default, notebooks for demos" is encoded in agent instructions.

---

**Luca:** We always want to save time; the ultimate objective is to find science at the maximum of scientific beauty, but at the same time do so while saving the user's time so that they can have a life, and enjoy their few years.

**Claude:** Philosophy principle #13 is "User Time is Precious — Maximize output, minimize intervention." The entire autonomous mode, voice prompting, auto-debug, and meta-rule capture are designed to minimize user effort.

---

**Luca:** We also want agents that check fidelity to the initial idea, so not only debuggers, which are fundamental, but also agents that constantly monitor: okay, are we going off on a tangent or are we adjacent to the initial idea?

**Claude:** The `knowledge/GOAL.md` stores the initial project description. The `knowledge/CONSTRAINTS.md` stores boundaries. The reviewer agent is tasked with checking alignment. The `core/verification.py` performs claim verification. However, a dedicated "fidelity checker" agent that continuously compares current work against GOAL.md is not implemented as an explicit, always-running monitor — it would rely on the reviewer agent being periodically invoked.

---

**Luca:** Likewise, we must have constant handling of the environment. Suppose a sub-agent installs some packages, another installs others that crash; this must be handled smoothly, trying different alternatives and avoiding entering situations where sudo is needed, because otherwise the user is needed and things can get complicated.

**Claude:** The `core/environment.py` performs system discovery including conda/mamba detection. The `core/auto_debug.py` handles crash recovery. The Docker setup provides an isolated environment where package conflicts are contained. The philosophy emphasizes avoiding sudo. However, automated conflict resolution when two sub-agents install incompatible packages simultaneously is not implemented — the system relies on conda/mamba environment isolation and the auto-debug retry loop.

---

**Luca:** It would indeed be nice in the dashboard we are developing to have a terminal where any user actions, such as credit card or sudoer password, etc., are entered, obviously in a hyper-super-mega-safe way.

**Claude:** The Docker setup exposes port 7681 for a web terminal (ttyd). The `core/security.py` provides secret scanning and immutable file protection. However, a dedicated secure input terminal within the dashboard for sensitive actions (credit card entry, sudo password) with special encryption or isolation is not implemented.

---

**Luca:** We also want functions where agents instruct other agents by behaving as if they were the user, i.e. there are many situations where it is enough to do a pushback or a data check, in particular visual, where the agent must be as objective as possible and has a severe reviewer of itself, i.e. another agent that does not please but is a strict judge, looks at the plots and says, "what the hell did you do, idiot." This kind of stuff.

**Claude:** The reviewer agent (`templates/.claude/agents/reviewer.md`) and falsifier agent (`templates/.claude/agents/falsifier.md`) serve this purpose. The claude-flow integration enables agent-to-agent communication where one agent can reprompt another. The "don't please" philosophy is encoded throughout. The `core/agents.py` supports DAG execution where one agent's output feeds into another's input. Whether agents can truly act as "strict judge users" to each other depends on the orchestration layer.

---

**Luca:** I also have this autonomous night template to base ourselves on: [overnight orchestrator template]

**Claude:** The overnight mode is implemented in `core/autonomous.py` (4.2 KB) with scheduling and iteration. The scripts `scripts/overnight.sh` and `scripts/overnight-enhanced.sh` implement the loop pattern (`for i in {1..20}; do claude ...; done`). The CLI command `ricet overnight` launches autonomous execution. The philosophy encodes the non-negotiable constraints from the template: only modify local files, Python/PyTorch primary, iterative approach, compute budget guidelines.

---

**Luca:** We therefore want an all-nighter mode in addition to the daily mode based on constant user–agent interaction.

**Claude:** Two modes exist: `ricet start` for interactive daily sessions and `ricet overnight` for autonomous overnight execution. The `core/autonomous.py` handles the overnight mode with scheduling, checkpointing, and auto-debug.

---

**Luca:** Other elements to consider as we open the discussion: first of all, we must have a sort of plan–execute–iterate framework, i.e. the general framework in which we operate must include various planning steps, starting from initial planning, when the scientific project is discussed, to sub-planning, to execution, to iteration.

**Claude:** The philosophy encodes the progressive framework: ORIENT → EXPLORE → PLAN → EXECUTE → VALIDATE. The `state/TODO.md` serves as the plan. The `core/prompt_queue.py` manages task execution. The overnight mode iterates through the plan. Agent definitions include planning responsibilities.

---

**Luca:** And in this context we must also ensure that there is efficient token reporting and max capping, so that too many tokens of the monthly availability are not burned.

**Claude:** The `core/tokens.py` (3.9 KB) implements token estimation, budget tracking, and thinking mode selection. The `ricet metrics` command shows token usage and costs. Budget allocation per agent is defined in `core/agents.py`. However, hard capping against the monthly plan limit (e.g., "stop all agents when 80% of monthly tokens consumed") is not enforced — the system tracks and reports but does not automatically halt.

---

**Luca:** It would also be nice to have a copilot-based option, where the agent is replaceable with Copilot, but we might keep this for the future, so that users who do not have a Cloud account can also use Copilot.

**Claude:** Not implemented. The system is built around Claude Code and Claude models. No GitHub Copilot integration exists.

---

**Luca:** Moreover, it must be very clear what the user needs to import, for example the reference papers, any reference code.

**Claude:** The onboarding in `core/onboarding.py` guides the user through what to provide. The `defaults/ONBOARDING.md` describes what is needed. The template structure makes the expected inputs clear (knowledge/GOAL.md for description, config/settings.yml for credentials, paper/ for references).

---

**Luca:** We will make a folder where we put all code potentially useful for the project, which can be messy and chaotic, but the agent can use for refinement, reuse of parts in the context of the project itself, as well as any passwords, API keys, etc., or certain information or input files.

**Claude:** The template structure includes `knowledge/` for project information and `.env` for credentials. A dedicated "messy reference code" folder is not explicitly created in the templates. The dual-repo pattern (`core/two_repo.py`) uses the experiments repo for messy work, but a specific "reference materials" folder for user-uploaded code snippets is not scaffolded by default.

---

**Luca:** We should also ensure that we understand what the top people in the field do, in order to trace their main operating criteria.

**Claude:** The researcher agent (`templates/.claude/agents/researcher.md`) is tasked with literature search across arXiv, PubMed, bioRxiv, and Semantic Scholar. The MCP nucleus includes paper search tools in Tier 1. However, a specific "analyze top researchers' methods and criteria" feature is not a dedicated function — it would be a task given to the researcher agent.

---

**Luca:** And I also link below a site from which we can take information regarding paper writing, tutorial generation, and website generation, because indeed we must include website generation capabilities in every possible project.

**Claude:** The `core/website.py` (462 lines) handles static website generation and deployment (GitHub Pages, Netlify). The paper pipeline (`core/paper.py`) handles paper writing. The `docs/tutorials/website-setup.md` documents website setup. The reference to `lamanno-epfl.github.io/tutorial_claude_code/` is noted in the codebase as a resource for paper writing and tutorial practices.

---

**Luca:** Then update, as I partially described in the past, and we can discuss this later in more detail.

**Claude:** Acknowledged — iterative updates have been made across 42 commits.

---

**Luca:** And I also provide below some ideas to look for a prompt collection, which we had already partially discussed, and I ask you to reason together on how we could best exploit this collection using, for example, RAG or all the ways in which RAG can be useful.

**Claude:** The `defaults/PROMPTS.md` contains the prompt collection. The `core/rag_mcp.py` (353 lines) provides RAG integration via MCP servers for semantic search over the collection. The `core/knowledge.py` supports HNSW vector search via claude-flow. The `core/prompt_suggestions.py` generates prompt recommendations based on context. The RAG infrastructure is built, though its effectiveness depends on the claude-flow memory backend being active and the prompt collection being sufficiently rich.

---

**Luca:** Another general rule that I had not yet mentioned is to always plot everything necessary to convince the user, and thus generally make galleries, potentially scrollable within this initial canvas, this home page, let's say, or phone application where the user can essentially see in real time what is being produced, and the machine in some way, even when not explicitly described in the prompt, must always plot graphs with well-discussed criteria.

**Claude:** The `cli/gallery.py` (2.5 KB) provides a figure gallery viewer for experiment outputs. The figure-making skill (`templates/.claude/skills/figure-making.md`) specifies plotting standards (colorblind-safe palettes, PDF export, rcParams). The dashboard (`cli/dashboard.py`) shows progress but does not embed live figure previews. A scrollable gallery within a web/mobile app is not implemented — the gallery viewer is terminal-based.

---

**Luca:** Then another feature: I would like the default to be Oculus 4.5 Thinking with three percent token consumption and also potentially the self-regulations where the model, as we said before, can be selected for silly tasks, even silly free models, and for intermediate-level tasks instead with normal token consumption or turning off thinking.

**Claude:** The `core/tokens.py` implements thinking mode selection with Opus 4.5 as the default with extended thinking. The `core/model_router.py` provides 3-tier routing: free/Haiku for simple tasks (no thinking), Sonnet for intermediate tasks, Opus with thinking for complex tasks. The 3% thinking budget default is referenced in the design. Self-regulation (automatic thinking mode adjustment based on task complexity) is part of the model router's classification logic.

---

**Luca:** But I imagine the default is better to be thinking three percent in order to ensure maximum quality.

**Claude:** The default configuration targets Opus with extended thinking for scientific operations, as encoded in the token management and model routing modules.

---

**Luca:** For paper writing etc also we should not forget https://lamanno-epfl.github.io/tutorial_claude_code/

**Claude:** This resource is referenced in the documentation and influenced the paper-writing skill design. The paper pipeline and skill files incorporate practices from this tutorial.

---

**Luca:** IMPORTANT: we must also pre-organize access to the most important MCPs, for example PubMed for scientific research and many others!

**Claude:** The MCP nucleus (`defaults/MCP_NUCLEUS.json` and `templates/config/mcp-nucleus.json`) pre-organizes 70+ MCP servers across 8 tiers. Tier 1 (always loaded) includes paper-search, arxiv, git, github, puppeteer, filesystem, memory, and fetch. Higher tiers lazy-load on keyword triggers.

---

**Luca:** https://github.com/modelcontextprotocol/servers and https://github.com/modelcontextprotocol/servers-archived Perhaps also useful: https://github.com/punkpeye/awesome-mcp-servers

**Claude:** These repositories were used as the source for the MCP nucleus configuration. The `core/mcps.py` and `core/lazy_mcp.py` implement the discovery and lazy-loading system. The `defaults/MCP_NUCLEUS.json` is the curated result of surveying these MCP server registries.

---

**Luca:** Certainly all the basics like Slack, Canva, Stripe, SendGrid, Google Drive, etc. must already be connected and the relevant API keys etc. provided by users at the moment of project creation (optional where possible).

**Claude:** The MCP nucleus includes: Slack (Tier 6), SendGrid (Tier 6), Stripe (Tier 8), Gmail (Tier 6), Notion (Tier 8). Google Drive and Canva are not explicitly listed but could be added. The onboarding collects API keys, and connections are optional (lazy-loaded on demand).

---

**Luca:** Claude must also be able to create MCPs where one does not exist and it is necessary.

**Claude:** This is mentioned as a goal but not implemented. The system can install existing MCP servers from npm, but auto-generating new MCP server code for a service that lacks one is not a built-in capability.

---

**Luca:** We should also connect Zapier and connect Gamma for slides.

**Claude:** Gamma is listed in the MCP nucleus (Tier 8) for slide generation. Zapier is not explicitly listed in the current MCP nucleus configuration. Neither has been tested in integration.

---

**Luca:** Moreover, these MCP GitHubs should be RAGgable by Claude to find and install MCPs autonomously under the hood as needed to satisfy user requests.

**Claude:** The `core/mcps.py` implements keyword-triggered MCP discovery (e.g., "database" triggers Tier 2 loading). The `core/lazy_mcp.py` handles on-demand initialization. However, RAG over the MCP GitHub repositories (embedding their README files and searching semantically to find the right MCP for a novel request) is not implemented — the system uses a pre-curated mapping of keywords to known MCPs.

---

**Luca:** Useful site for paper writing parts, etc.: https://lamanno-epfl.github.io/tutorial_claude_code/ Perhaps useful for orchestration: https://github.com/ruvnet/claude-flow

**Claude:** claude-flow is a core integration. The `core/claude_flow.py` (303 lines) bridges ricet to claude-flow v3 CLI. The `.mcp.json` configures claude-flow as an MCP server. The `.claude-flow/` directory contains extensive state, agents, hooks, and metrics. claude-flow provides swarm orchestration, HNSW memory, model routing, and inter-agent communication.

---

**Luca:** Certainly all conversations must be dumped in markdown for documentation.

**Claude:** Session state is persisted in `.claude-flow/sessions/` as JSON. The `state/` directory maintains markdown files (PROGRESS.md, TODO.md). Audit logging goes to `state/audit.log`. However, automatic full conversation transcript dumping (every message in/out as markdown) is not implemented as a dedicated feature.

---

**Luca:** Use of task spooler ts or tsp.

**Claude:** The `core/task_spooler.py` (257 lines) implements task scheduling, batching, and execution monitoring, inspired by the Unix `ts`/`tsp` task spooler concept.

---

**Luca:** Configure parse. Cruft. GitHub actions: all the best software engineer ideas properly set up. GitHub automation. Cronjob routines.

**Claude:** GitHub Actions workflows are in `templates/.github/workflows/` (tests.yml, lint.yml, paper-build.yml). The `core/devops.py` handles CI/CD integration, GitHub Actions, and release management. The `state/routines.json` stores scheduled routines. Cruft (project template updating) is not explicitly integrated. Parse configuration is not present. Cron-style routines are supported through the autonomous mode and task spooler.

---

**Luca:** And everything well described in documentation.

**Claude:** The `docs/` directory contains 262 documentation files: site docs (7 pages), tutorials (8 guides), specification, demo walkthrough, API reference, architecture, and FAQ. MkDocs is configured (`mkdocs.yml`) with Material theme for building a documentation site.

---

**Luca:** We should also put into practice the advice of this fundamental repo: https://github.com/ykdojo/claude-code-tips

**Claude:** The tips from this repository influenced the project's design: named sessions (session management in `core/session.py`), CLAUDE.md configuration (project-level `templates/.claude/CLAUDE.md`), agent definitions as markdown files, and the hooks system (`.claude-flow/hooks/`). Specific tips like "invest in your own workflow" are reflected in the cross-repo template structure.

---

**Luca:** Everything, as I said, super safe, aiming for containerization, autonomy, respect for folders and system configurations.

**Claude:** Docker containerization is set up (`docker/Dockerfile`, `docker/docker-compose.yml`). The `core/security.py` enforces repo root boundaries, secret scanning, and immutable file protection. Philosophy principle #12 is "Safety First." Audit logging tracks all autonomous actions. The system respects folder boundaries but does not technically prevent non-containerized usage.

---

**Luca:** Let's start from here!

**Claude:** Started. 42 commits, 38 core modules, 10.8K lines of Python, 70+ MCP integrations, comprehensive test suite, documentation, and Docker setup later — ricet v0.2.0 (Beta) is the result.

---

**Luca:** memory and claude projects

**Claude:** The claude-flow hybrid memory backend (HNSW + persistent storage) serves as the memory system. Claude Projects integration (Anthropic's project feature for persisting instructions) is not explicitly implemented — the system uses on-disk files instead.

---

**Luca:** gotta decide a core nucleus of connected MPCs to be always prepared at setup

**Claude:** Decided and implemented. The MCP nucleus is organized in 8 tiers in `defaults/MCP_NUCLEUS.json`, with Tiers 0–1 always loaded at setup (orchestration, paper search, arxiv, git, github, puppeteer, filesystem, memory, fetch).

---

**Luca:** we should also make sure that we get MCPs for startup and outreach activities all embedded into the workspace at setup.

**Claude:** Tier 8 (Web/Marketing) includes Vercel, Gamma, Stripe, and Notion. The `core/social_media.py` (345 lines) covers Twitter, LinkedIn, and Mastodon integration. These are available but lazy-loaded rather than always present at setup.

---

**Luca:** the idea is that when the user creates a new project they automatically get the full set up with minimal work and that the machine handles the vast majority of "finding the right tool" under the hood with users only partially aware of the toolbox.

**Claude:** The `ricet init` command scaffolds the full setup from templates. The `core/mcps.py` and `core/lazy_mcp.py` handle automatic MCP discovery and loading based on keyword triggers, so the user does not need to manually configure tool connections. The toolbox is pre-curated but loads transparently.

---

**Luca:** other important items that should be there: * the & sending to cloud claude

**Claude:** Background execution is supported through `core/task_spooler.py`, `core/autonomous.py`, and the overnight scripts. The `&` background pattern is used in the shell scripts.

---

**Luca:** * named sessions for automatic easier retrieval

**Claude:** The `core/session.py` (4.5 KB) implements session lifecycle management with UUIDs. The `ricet list-sessions` command lists past and active sessions. The `.claude-flow/sessions/` directory stores session state. Sessions have metadata (timestamps, agent assignments).

---

**Luca:** * ultrathink and think hard automatically selected when task requires them

**Claude:** The `core/tokens.py` implements thinking mode selection based on task complexity. The model router (`core/model_router.py`) classifies tasks and selects appropriate thinking levels. The default is extended thinking (3% budget) for scientific operations, with automatic adjustment for simpler tasks.

---

**Luca:** * estimates of token usage even if precise is not possible

**Claude:** The `core/tokens.py` provides token estimation and budget tracking. The `ricet metrics` command displays usage statistics. Estimates are approximate since exact token counts require API response data.

---

**Luca:** * hooks - lifecycle events

**Claude:** The `.claude-flow/hooks/` directory contains pre-task and post-task hooks. Pre-task hooks handle intent detection, model routing, and memory search. Post-task hooks handle neural pattern training, memory storage, and result validation. 27 hooks and 12 workers are configured.

---

**Luca:** * prompt suggestions / predictive follow-ups

**Claude:** The `core/prompt_suggestions.py` (433 lines) provides auto-generated prompt recommendations based on current context, serving as predictive follow-ups for the user.

---

**Luca:** * browser integration

**Claude:** The `core/browser.py` (293 lines) provides headless browser automation via Puppeteer MCP with fallback to curl/wkhtmltopdf. The MCP nucleus includes Puppeteer in Tier 1 (always loaded).

---

**Luca:** * agent skills (already partially discussed)

**Claude:** Three skill files in `templates/.claude/skills/`: code-style.md, figure-making.md, paper-writing.md. These are persistent instruction sets that agents can reference.

---

**Luca:** * markdown files that become commands

**Claude:** The `core/markdown_commands.py` (5.8 KB) parses markdown files into executable CLI commands. Agent definitions in markdown serve as both documentation and operational instructions.

---

**Luca:** * agents that behave as human users answering / reprompting agents as a function of goal and current results

**Claude:** The claude-flow integration supports agent-to-agent communication. The reviewer and falsifier agents are designed to critique and reprompt other agents. The master agent routes and re-assigns tasks based on results. The overnight orchestrator template explicitly describes this pattern.

---

**Luca:** * sandboxes and controlled freedom

**Claude:** Docker containerization provides sandboxing. The `core/security.py` enforces repo root boundaries and immutable files. Permission levels in `core/cross_repo.py` (read-only, execute, write, admin) provide controlled freedom. The Docker setup prevents system-level modifications.

---

**Luca:** we could also exploit the agent SDK if useful for developing this project.

**Claude:** The Agent SDK is not currently used in the implementation. The system is built on top of Claude Code CLI and claude-flow rather than the Anthropic Agent SDK. This could be a future integration point.

---

**Luca:** also something i read helps a lot is giving AI progressive instructions rather than all at once - that should definitely happen under the hood of our superhuman agent.

**Claude:** The philosophy encodes progressive instructions: ORIENT → EXPLORE → PLAN → EXECUTE → VALIDATE. Agent definitions instruct step-by-step exploration rather than dumping all context at once. The master agent breaks tasks into subtasks distributed to specialized agents sequentially.

---

**Luca:** and the docker aspect i know little about we discussed at first

**Claude:** Docker is set up in `docker/Dockerfile` (multi-stage build: Ubuntu 24.04, Python 3.12, Node.js 20, texlive-full, claude-flow, ricet) and `docker/docker-compose.yml`. The Docker setup exposes ports 7681 (web terminal) and 4000 (docs preview), includes health checks, and provides an isolated environment. The tutorial `docs/tutorials/docker-setup.md` documents how to use it.

---

*Document generated from ricet repository at v0.2.0 (Beta), 42 commits, 38 core modules.*
