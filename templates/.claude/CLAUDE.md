# Project Instructions

Scientific research project. Read `knowledge/GOAL.md`, `knowledge/CONSTRAINTS.md`, and `state/TODO.md` before starting any work.

## Core Philosophies

1. **Break big problems into small ones.** Decompose every task into the smallest useful subtasks. Execute one at a time. Checkpoint after each.
2. **Context is milk — best served fresh and condensed.** Keep files, prompts, and docs short. Prune stale information. Prefer re-reading source over relying on memory.
3. **Double-check everything.** After completing any task, verify the result: re-read the changed file, run the test, compare to the goal. Never mark done without validation.

## Anti-Drift Rules (MANDATORY)

- ONLY make changes that were directly requested.
- Do NOT refactor, rename, or reformat surrounding code.
- Do NOT add features, helpers, or abstractions not asked for.
- Do NOT add docstrings, comments, or type hints to code you didn't change.
- If tempted to "improve" something adjacent — stop. Note it and ask first.
- Re-read `knowledge/GOAL.md` at the start of every session.

## Work Protocol

1. **Orient** — Read goal, constraints, and TODO. Summarize understanding.
2. **Plan** — Propose approach and subtasks. Get approval before executing.
3. **Execute** — One subtask at a time. Keep changes minimal and focused.
4. **Verify** — After each subtask: re-read changed files, run tests, compare to goal.
5. **Record** — Commit after each subtask. Update `knowledge/ENCYCLOPEDIA.md` only when genuinely useful.

## Operating Rules

- Never guess — search or ask when uncertain.
- Test small first — downsample data, run 1 epoch, then scale.
- Be objective — challenge assumptions, report flaws, don't flatter.
- Estimate token cost before expensive operations (~4 chars/token).
- Prefer simple solutions. Less code is better code.

## Claude-Flow Integration

When [claude-flow](https://github.com/ruvnet/claude-flow) is available:
- Hierarchical swarm: coordinator dispatches to specialized agents (researcher, coder, reviewer).
- HNSW vector memory for semantic search over knowledge entries.
- 3-tier model routing: Haiku (simple) → Sonnet (general) → Opus (reasoning).
- All capabilities degrade gracefully when claude-flow is absent.

## Self-Maintenance

This file must stay under 80 lines. Every 5 sessions, review it and trim anything stale or redundant. If a rule hasn't been useful, remove it.