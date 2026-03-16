# Project Instructions

Scientific research project. Read these files before starting any work:
- `knowledge/GOAL.md` — project description and objectives
- `knowledge/CONSTRAINTS.md` — hard rules and preferences
- `knowledge/LEGISLATION.md` — detailed behavioral rules (coding, writing, figures, communication)
- `knowledge/PHILOSOPHY.md` — core research principles (Popperian falsification, the Mantra)
- `state/TODO.md` — current task list

## Session Start Checklist

1. Re-read `knowledge/GOAL.md`
2. Scan `knowledge/DECISION_LOG.md` for recent entries relevant to current work
3. For domain questions, search `knowledge/ENCYCLOPEDIA.md` before answering

## Research Skills (slash commands)

| Command | What it does |
|---------|-------------|
| `/lit-review` | Search PubMed/arXiv, synthesize findings, update Encyclopedia |
| `/experiment-review` | Audit experiment results for statistical issues and leakage |
| `/paper-draft` | Draft a paper section with lab style conventions |
| `/falsify` | Adversarial validation — try to break current results (Popper mode) |
| `/reproduce` | Re-run analysis with different seeds/splits, test reproducibility |
| `/research-retro` | Session retrospective — what worked, what failed, update Encyclopedia |
| `/slides` | Generate a polished presentation (.pptx) with AI diagrams |
| `/overnight` | Autonomous overnight session — execute TODO list unattended |
| `/style-transfer` | Match writing style to reference papers from the lab |
| `/add-citations` | Find, verify, and insert citations (PubMed/arXiv) |
| `/verify` | Fact-check claims against data, code, and literature |
| `/figure-audit` | Audit figures for publication readiness (fonts, labels, accessibility) |
| `/debug` | Systematic debugging: reproduce, isolate, bisect, fix, verify |
| `/code-review` | Research code audit: leakage, seeds, metrics, parameter logging |
| `/doability` | Assess research goal feasibility before committing resources |

## Memory Hierarchy

| File | Loaded | Purpose | Updated by |
|------|--------|---------|------------|
| `knowledge/RULES.md` | Every session (via CLAUDE.md) | Behavioral rules from user corrections | meta_learn_hook (auto) |
| `knowledge/ENCYCLOPEDIA.md` | On-demand (search before domain questions) | Domain knowledge, techniques, what works/fails | meta_learn_hook (auto) |
| `knowledge/DECISION_LOG.md` | On-demand (before architectural choices) | Project decisions with rationale | meta_learn_hook (auto) |

The meta-learn hook runs on every user prompt via Haiku. It extracts rules, insights, and decisions and appends them to the appropriate file. Do not duplicate this by manually writing the same information.

## The Mantra

**Do not guess — verify when uncertain. Minimal code edits and concise answers, to the point, unless otherwise stated.**

## Anti-Drift Rules (MANDATORY)

- ONLY make changes that were directly requested.
- Do NOT refactor, rename, or reformat surrounding code.
- Do NOT add features, helpers, or abstractions not asked for.
- If tempted to "improve" something adjacent — stop. Note it and ask first.

## Work Protocol

1. **Orient** — Read goal, constraints, and TODO.
2. **Plan** — Propose approach. Get approval before executing.
3. **Execute** — One subtask at a time. Minimal, focused changes.
4. **Verify** — Re-read changed files, run tests, compare to goal.
5. **Record** — Commit after each subtask.

## Directory Convention

- `lab/` — experimental scripts, notebooks, WIP analysis
- `stable/` — validated code promoted via `ricet promote` (with provenance tracking)

## Operating Rules

- Never guess — search or ask when uncertain.
- Test small first — downsample, 1 epoch, then scale.
- Be objective — challenge assumptions, report flaws, don't flatter.
- Prefer simple solutions. Less code is better code.

## Self-Maintenance

This file must stay under 80 lines. Every 5 sessions, trim stale content.
