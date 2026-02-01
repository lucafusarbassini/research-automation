0) Clarify scope + define success criteria

 Decide initial delivery target(s): mobile app, VS Code extension, web dashboard, or combo.

 Define “automation of scientific research” scope for v1 vs later (what counts as “done”).

 Define what “cloud code” means operationally (remote runners? local+remote hybrid?).

 Define what “project initialization” must include, minimum and maximum.

 Define the strict interpretation of “do everything strictly as I describe” (validation rules, rejection behavior).

 Define a formal “project spec” schema for the user’s hyper-detailed description + agent requests + keys.

 Define success metrics: reproducibility, cost, latency, UX, reliability, safety.

1) Architecture: master agent + sub-agents + orchestration

 Design a master agent role that:

 Receives all user inputs (voice + text).

 Routes work to sub-agents.

 Tracks each sub-agent’s status, actions, and token/cost.

 Keeps a visible “active agents” panel.

 Define a sub-agent system:

 Standard role descriptions.

 Per-role rules and constraints.

 File-based definitions (MD files).

 Which instruction files are editable vs immutable.

 Implement structured task dispatch:

 Create task objects (id, goal, inputs, outputs, constraints).

 Support parallel tasks (paper writing, DL algorithm, plotting, etc.).

 Support dependencies between tasks.

 Implement a plan–execute–iterate framework:

 Initial plan from project spec.

 Sub-planning per task.

 Execution with checkpoints.

 Iteration loop with evaluation criteria.

 Implement “all-nighter mode” orchestration:

 Looping execution template (like the shared bash loop).

 Safety constraints (no filesystem escape).

 Steady progress + measurable checkpoints.

 Implement “daily mode” orchestration:

 Continuous user–agent interaction.

 Frequent updates and progress visibility.

 Implement token/cost governance:

 Per-task budget.

 Global cap.

 Alerting when nearing cap.

 “Estimate token usage” feature (even if approximate).

 Default settings like “thinking 3%” (or equivalent) where supported.

2) Model routing + “cheap model for cheap operations”

 Implement multi-model routing logic:

 Cheap model for translation + prompt structuring.

 “4.5 opus with thinking enabled” (or equivalent) for scientific reasoning.

 Intermediate model options (thinking off, standard mode).

 “free/silly” model option for trivial tasks.

 Implement task classification (cheap / intermediate / expensive).

 Add user-visible controls:

 Global default model policy.

 Per-task override.

 Implement cross-provider fallback:

 Allow Claude agents to use Gemini when Claude can’t access certain sites.

 Implement “ultrathink / think hard auto-selection” rules by task type.

3) Voice prompting pipeline (core feature)

 Build voice input in dashboard (VS Code + mobile/web path):

 Record audio.

 Speech-to-text (STT).

 Language detection.

 Translate user language → English.

 Convert “disorganized brainstorming” → structured prompt:

 Enforce prompt schema.

 Reduce verbosity while preserving meaning.

 Add required constraints and context automatically.

 Integrate prompt collection:

 Store prompts in a dedicated cheat sheet/collection.

 Retrieve best matching prompt template (RAG or equivalent).

 Fill templates with user content.

 Route structured prompt to master agent.

 Provide user preview/edit step (if desired) before dispatch.

 Log:

 Original audio reference (if stored).

 Transcription.

 Translation.

 Final structured prompt.

 Which model was used.

4) Project initialization workflow (repo creation + local setup)

 Accept user’s initialization bundle:

 Hyper-detailed project description.

 Specific requests for the agent.

 All necessary keys (API keys, GitHub access, etc.).

 Optional uploaded materials that must not be pushed (papers for inpainting, reusable code, instructions).

 Create repository (and possibly dual repos—see section 11):

 Create GitHub repo (or chosen VCS host).

 Initialize locally on the machine where agent runs.

 Create project directory structure.

 Configure remotes, branches, permissions.

 Add properly configured .gitignore:

 Exclude heavy files.

 Exclude secrets/keys.

 Exclude uploaded “must not be pushed” materials.

 Add cross-repo skeleton files (“solid skeleton”):

 Preconfigured prompts.

 Instruction MD files.

 Agent role definitions.

 TODO/progress/memory/system files (see section 6).

 Create designated local-only folders for sensitive uploads.

 Ensure initialization produces:

 A high-level action plan / initial todo list.

 A clear runnable baseline project scaffold.

5) Environment setup (conda/mamba) + “system discovery”

 Create and/or reuse conda/mamba environment:

 Use specified env name (example: agent) or project-defined env name.

 Install required dependencies.

 Maintain a persistent file with environment/tool inventory:

 Record OS info, Python version, GPU availability.

 Record installed packages + versions.

 Record toolchain (git, latex, make, etc.).

 Implement “system discovery” routine:

 Run when system.md is missing or stale/empty.

 Re-write system.md with discovered info.

 Add a predictable mechanism for environment changes by sub-agents:

 Track changes.

 Prevent conflicting installs.

 Provide rollback or alternate env strategies.

6) Persistent knowledge base (“project encyclopedia”) + cheat sheets

 Create a project-specific persistent “encyclopedia”:

 How to rsync between data and compute machines.

 Conda env name.

 Project-specific tricks learned over time.

 Ensure agents always consult it (RAG or direct retrieval) before acting.

 Implement automatic growth of this knowledge:

 When new meta-rules are introduced, incorporate them automatically.

 Do not require the user to explicitly say “add it to cheat sheet”.

 Create additional cheat sheets:

 Prompt collection cheat sheet.

 Paper writing cheat sheet.

 Figure-making cheat sheet.

 Plotting rules cheat sheet.

 Any other domain/house rules to be added later.

 Address long-context memory loss:

 Persist key decisions.

 Persist constraints and “already decided” items.

 Implement retrieval at task start + periodic refresh.

7) Repo-level persistent state files + conversation logging

 Implement required persistent files in every project:

 task.md (fixed, not changeable by agents).

 system.md (environment/tool inventory).

 todo.md (current next actions).

 memory.md (persistent learnings).

 progress.md (high-level achievements).

 Implement startup procedure (always-run sequence):

 Read task.md fully.

 Ensure .claude/ and .claude/agents/ exist.

 Create memory.md from template if missing.

 Create progress.md header + empty achievements list if missing.

 Run system discovery if needed; write/update system.md.

 If no agents exist, create initial agent set based on task.md.

 Dump all conversations to markdown for documentation.

 Implement “markdown files become commands” pattern (as described).

8) Security + safety guardrails + containerization

 Enforce “only modify files inside repo root” constraint.

 Implement containerization strategy (Docker or equivalent):

 Prevent system config changes without authorization.

 Prevent deletion of user files outside workspace.

 Sandbox risky operations.

 Secret management:

 Store API keys securely.

 Ensure keys never leak into git history.

 Ensure keys are not written to logs accidentally.

 Guardrails for destructive actions:

 Confirmation gates for deletes, overwrites, purchases, credential use.

 Safe terminal interaction channel:

 Place for user to enter sudo password / credit card / sensitive approvals.

 “Hyper-super-mega-safe” design requirement as a first-class constraint.

 Enforce “don’t modify immutable instruction files”.

 Ensure sub-agents explore repo areas they touch (familiarization step).

9) Reproducibility + traceability enforcement

 Define reproducibility rules (“non-negotiable”):

 Everything traceable.

 Every result reproducible from versioned code + data pointers.

 Enforce frequent checkpoints:

 Frequent git commits.

 Frequent git pushes.

 Avoid stepping on each other (branching + merge rules).

 Implement automatic run logging:

 Config, seeds, versions, dataset hashes/paths.

 Commands executed.

 Output artifacts registry.

10) “Use code, not by hand” + deterministic automation

 Enforce rule: agents should write scripts/tools for repeated operations.

 Provide automation utilities library:

 Data handling.

 Experiment runners.

 Plot generation.

 Report generation.

 Build pattern: minimal tokens by delegating to deterministic code.

11) Repository cleanliness + dual-repo / dual-structure approach

 Decide and implement “two repositories or two sub-repos”:

 Messy/experiment repo: everything, ordered but not hyper-clean.

 Clean/public repo: minimal, concise, optimized, review-friendly.

 Define cleanliness rules:

 Minimal code, straight to the point.

 Vectorize early.

 Comments: sufficient but not exhausting.

 No fluff, optimized.

 Implement automated code-cleaning passes:

 Refactor while preserving behavior.

 Re-run tests / rerun code to confirm identical results after cleaning.

 Clean comments as part of the pass.

 Implement artifact hygiene:

 Avoid runaway code/data generation.

 Periodic cleanup tasks.

 Keep repo usable and navigable.

12) Background jobs + monitoring + verbose progress tracking

 Implement background job runner:

 Run experiments, training, evaluation in background.

 Job queue system (task spooler ts/tsp integration requested).

 Implement iterative debugging loop:

 Detect crash.

 Debug.

 Resume.

 Repeat until completion or escalation rule triggers.

 Create live monitoring UI:

 Constantly live.

 Scrollable verbose output.

 Progress indicators per activity (TQM-style).

 Implement verbosity policy:

 Agents must be extremely verbose in logs.

 User-facing summaries remain concise if desired, but logs remain detailed.

 Implement shared “office space” visibility:

 Sub-agents can observe other sub-agents’ status and outputs.

 User can see without “clicking like crazy.”

 Add voice-first interaction patterns to reduce clicking (wrist/hand pain use case).

13) Web search policy + “never guess” behavior

 Enforce: agent must not guess when uncertain.

 Implement web search tool usage when needed:

 Use judiciously to reduce token cost.

 Prefer finding existing solutions.

 Implement “uncertainty triggers”:

 If confidence below threshold → search.

 If common solution likely exists → search.

 Persist findings into cheat sheets/encyclopedia.

14) Code execution policy: small-scale first + end-to-end tests

 Enforce “run on small scale first”:

 Downsample / toy run.

 1 epoch sanity check for training.

 Confirm losses stable.

 Enforce end-to-end testing:

 Pipeline runs successfully before scaling.

 Define scaling policy:

 GPU if available; otherwise adapt.

 Budget guideline per cycle (~10 minutes).

 Implement automatic test harness and smoke tests.

15) Paper-making feature (LaTeX template + continuous updates)

 Add baseline paper subdirectory in every repo at creation:

 Include basic LaTeX template now; allow replacing with user’s template later.

 Structure for figures, bibliography, sections.

 Add Makefile for paper build.

 Implement rules for figures:

 Export plots as PDF.

 Editable text (e.g., rcParams-based settings).

 Rasterize where needed but keep vector where possible.

 Implement “paper update commands”:

 “make me a version of the paper”

 “modernize the version of the paper”

 “integrate new results into the paper”

 Implement reference management:

 Use PubMed MCP for references.

 Build and compile BibTeX properly.

 Ensure environment installs everything needed for paper building (LaTeX toolchain etc.).

16) Style transfer / “inpainting” for paper style (non-plagiarizing)

 Support uploading reference papers (must not be pushed).

 Implement analysis of style (structure, tone, formatting).

 Implement “transform style without plagiarizing” workflow.

 Add explicit safeguards against copying text verbatim.

 Integrate this into paper-making pipeline.

17) Automatic meta-rule capture (no repeated instructions)

 Detect when user provides new operational rules (plots, formatting, workflows).

 Automatically update the appropriate cheat sheet:

 Without requiring explicit instruction.

 With versioning and attribution (“added on date because…”).

 Ensure new rules are applied in subsequent tasks.

18) Resource management + checkpointing + autonomous cleanup

 Implement continuous resource monitoring:

 RAM, disk, GPU memory, CPU.

 Detect risk of crash/out-of-space.

 Implement checkpointing policy:

 Frequent enough to avoid major loss.

 Organized checkpoint storage.

 Implement autonomous cleanup:

 Delete old checkpoints that are safe to remove.

 Preserve essential ones for reproducibility.

 Implement decisions based on resource availability:

 Downsample more.

 Move artifacts.

 Pause or ask user for action.

19) Tool/MCP ecosystem setup + “find the right tool under the hood”

 Decide core nucleus of MCPs to install by default at setup.

 Pre-organize access to key MCPs:

 PubMed MCP (explicitly required).

 Additional MCPs “and many others”.

 Make MCP repos “RAGgable”:

 Index MCP server repositories.

 Enable autonomous discovery + installation.

 Allow creation of MCPs when none exist.

 Add integrations (optional at project creation):

 Slack.

 Canva.

 Stripe.

 SendGrid.

 Google Drive.

 Zapier.

 Gamma for slides.

 Email.

 Build UI for connecting tools and uploading DBs.

 Suggest “other essential tools” to connect for scientific researchers at setup.

20) Repo-to-repo interaction + website integration

 Support linking a user website repo to the project.

 Implement workflow:

 Agent works in project repo branch.

 Agent updates website repo (feature integration) safely.

 Add cross-repo automation:

 Coordinated commits/pushes.

 Conflict avoidance.

 Define permission boundaries between repos.

21) Strict objectivity: “don’t please me” feature

 Implement behavior policy:

 Grounded responses.

 Avoid flattering/pleasing bias.

 Maintain helpful tone without pandering.

 Add strict reviewer mode:

 Another agent critiques outputs (plots, claims, reasoning).

 “Severe judge” behavior for quality control.

 Add explicit “objective pushback” triggers.

22) Scientific rigor agents: falsifier + fidelity monitor + debuggers

 Create specialized sub-agents:

 Falsifier / Popperian “try to break the result” agent:

 Check for leakage.

 Check for invalid evaluation.

 Try alternate explanations / failure modes.

 Fidelity-to-initial-idea agent:

 Detect tangent drift.

 Enforce adjacency to original goals.

 Debugger agent:

 Crash detection and repair loops.

 “Reviewer of plots” agent (visual/objective critique).

 Define triggers for when each is invoked.

 Ensure their findings persist into memory.md / cheat sheets.

23) Output expectations: plots, galleries, and real-time visibility

 Enforce default: “always plot everything necessary to convince the user.”

 Implement galleries:

 Scrollable view in dashboard/canvas/home page.

 Organized by run/task.

 Live updating.

 Define plot criteria and store them in cheat sheets.

24) Notebooks vs scripts policy

 Default to scripts (well-made, parallelizable).

 Generate notebooks only for interactive demos when needed.

 Ensure notebook outputs are reproducible and tracked.

25) Environment conflict handling (multi-agent installs)

 Prevent sub-agents from breaking shared env:

 Lockfile approach or constraints file.

 Separate envs per major component if needed.

 Avoid requiring sudo whenever possible.

 Provide alternatives when installs conflict.

 Record all install actions to system.md.

26) Email-based escalation + approvals + rate limits

 Implement “needs user input” detection.

 Send email to user for authorization on critical matters:

 Purchases.

 Credit card entry.

 Other high-risk actions.

 Implement reminder policy:

 Roughly every 2 hours if blocked.

 Hard cap: max 2 emails per hour.

 Add user controls:

 Enable/disable email escalation.

 Quiet hours / do-not-disturb.

 Ensure safe handling of sensitive responses.

27) Autonomous routines (later-stage but explicitly requested)

 Implement optional autonomous routines such as:

 Monitor “exploding topics” daily.

 Monitor news daily.

 Monitor websites.

 Make decisions based on observations.

 Send emails with summaries or requests for action.

 Implement purchase suggestion workflows:

 Buy a machine on Hetzner to host a website.

 Buy a domain on Namecheap.

 Require explicit user confirmation for any purchase.

 Ensure audit logs + reproducibility of decisions (what sources, what rationale).

28) Named sessions + retrieval + lifecycle hooks

 Implement named sessions for easy retrieval.

 Implement lifecycle hooks:

 On project create.

 On agent spawn.

 On task start/stop.

 On failure.

 On commit/push.

 Implement “prompt suggestions / predictive follow-ups.”

 Implement browser integration for research.

 Implement “agent skills” framework (as referenced).

29) Progressive instruction delivery (avoid dumping everything at once)

 Implement system that breaks instructions into progressive steps:

 Deliver only what’s needed now.

 Reveal deeper constraints as tasks advance.

 Tie progressive instructions to plan–execute–iterate loops.

30) GitHub automation + CI/CD + engineering best practices

 Add GitHub Actions baseline:

 Linting.

 Unit tests.

 Build checks.

 Paper build check (if feasible).

 Add automation scripts for routine tasks.

 Configure cronjob routines (as requested).

 Add repo documentation:

 How to run.

 How to reproduce.

 How agents operate.

 Tooling overview.

 Add “cruft” / cleanup tooling integration if desired.

 Incorporate best practices from:

 claude-code-tips repo guidance.

 Implement “everything well described in documentation.”

31) Workspace folders and rules (uploads, secrets, reusable code)

 Create a folder for user uploads that must not be pushed:

 Reference papers.

 Reference code.

 Databases.

 Input files.

 Passwords/API keys (or secure store pointer).

 Create a folder for “potentially useful messy code” to recycle.

 Ensure .gitignore covers all sensitive folders.

 Ensure agents know where to look and how to use these materials safely.

32) Cross-project knowledge transfer (user-level encyclopedia)

 Design optional mechanism to share learnings across all user repositories:

 Export/import cheat sheets.

 Shared global memory store.

 User control: opt-in, selectable scope.

 Implement “transferable behavior files” system.

33) Strict constraints from the shared orchestrator template

 Enforce: only create/modify files within repo root and subdirectories.

 Set primary implementation language: Python.

 Set primary ML framework: PyTorch.

 Assume a mamba environment named agent exists (or handle if missing).

 Ensure iterative approach (baseline → measure → improve).

 Enforce compute budget guideline (~10 minutes per major cycle; adapt if no GPU).

 Enforce training workflow:

 1 epoch first to validate pipeline.

 Only then scale up.

 Keep outputs concise in chat; record state in persistent files.

34) Explicit external references you want incorporated later

 Integrate guidance from the tutorial site on paper writing / tutorial / website generation:

 lamanno EPFL tutorial link (to be used for rules and templates).

 Evaluate orchestration ideas from:

 claude-flow repo.

 Use MCP server lists for discovery/installation:

 modelcontextprotocol/servers

 modelcontextprotocol/servers-archived

 awesome-mcp-servers (text-to-speech list, etc.)

 Ensure MCP discovery sources are indexable and searchable by agents.

35) “Start from here” kickoff tasks (implied next steps)

 Convert this brainstorming into a structured spec document.

 Extract and formalize:

 Non-negotiable constraints.

 v1 features vs later features.

 Security model and threat model.

 Data model for tasks, agents, logs, and cheat sheets.

 Decide initial MVP flow:

 Project init → repo scaffold → env setup → todo plan → voice prompt → task routing → monitoring.

 Build the initial cross-repo skeleton structure and templates.