# ricet - Research Automation Framework

## Project overview

ricet automates the full lifecycle of scientific research: literature search, experiment tracking,
reproducibility, paper generation, and knowledge accumulation. The central innovation is the
**persistent Encyclopedia** (`knowledge/ENCYCLOPEDIA.md`) with vector search -- insights compound
across sessions instead of being lost.

Documentation: https://lucafusarbassini.github.io/research-automation/

## claude-flow MCP

claude-flow (ruflo) is available as an MCP server (`claude-flow` in `claude mcp list`).
Use its tools via `mcp__claude-flow__*` for:

- **Memory** -- `memory_store`, `memory_search`, `memory_retrieve`, `memory_list`
  Store and retrieve patterns, solutions, decisions across sessions with HNSW vector search.
- **Sessions** -- `session_save`, `session_restore`, `session_list`
  Persist and restore conversation state.
- **Swarm coordination** -- `swarm_init`, `swarm_status`, `agent_spawn`, `agent_list`
  Multi-agent orchestration when tasks touch 3+ files or need parallel work.

Use these tools naturally when relevant. For simple tasks, just work directly.

## Workflow habits

- Before starting non-trivial work, search memory: `mcp__claude-flow__memory_search` for relevant past patterns.
- After solving something tricky, store it: `mcp__claude-flow__memory_store` with namespace "patterns".
- For complex multi-file tasks, spawn background agents via the Agent tool with `run_in_background: true`, all in one message. Tell the user what's running, then wait.

## File organization

Never save working files to the root folder. Use: `core/`, `cli/`, `tests/`, `docs/`, `config/`, `scripts/`, `knowledge/`, `state/`.

## User-specific behavioral rules

Captured automatically from past corrections. Obey these without question:

@knowledge/RULES.md

## General rules

- Do what is asked; nothing more, nothing less.
- Never proactively create documentation files unless explicitly requested.
- Use Opus 4.6 with default medium thinking for everything -- no model routing.
- Batch parallel operations in a single message when possible.

## On-demand context (read when relevant — never load all upfront)

- **Behavioral rules for user projects**: `defaults/LEGISLATION.md` — the canonical rulebook; read it when starting any substantive task on a user project.
- **MCP tools**: three searchable catalogs in `defaults/`:
  - `defaults/MCP_NUCLEUS.json` — curated MCPs organized by tier and purpose
  - `defaults/MCP_CATALOG.md` — full catalog; use `Grep` to find by keyword
  - `defaults/raggable_mcps.md` — same, indexed for sentence-transformers RAG (`ricet memory search` finds MCPs here once indexed)
  - Install pattern: `npx -y <package>` or add entry to `.mcp.json`
- **Accumulated research knowledge**: `knowledge/ENCYCLOPEDIA.md` — use `ricet memory search <query>` before answering domain questions.
- **Project decision history**: `knowledge/DECISION_LOG.md` — read when making architectural or methodological choices to avoid re-litigating past decisions.
- **Startup workflow skills**: `ricet gstack install` — installs [gstack](https://github.com/garrytan/gstack) globally for /plan-ceo-review, /plan-eng-review, /review, /ship, /browse, /qa, /retro. Use `--skip-browser` on systems without bun.

## Token economy

- **Do not use subagents** (Agent tool) unless tasks are genuinely parallel AND each subtask takes >10 min. Simple searches, single-file edits, and quick lookups must be done directly.
- **Do not use extended thinking** unless explicitly blocked or reasoning about a novel algorithm. Default thinking is sufficient.
- **Keep MCP queries narrow**: always pass filters, limits, or specific IDs. Never fetch unbounded lists.
- **Avoid redundant context reads**: if a file was just read, don't re-read it. Trust the conversation window.
