# Decision Log

Chronological log of key project decisions.
Updated automatically by the meta-learn hook — edit freely.

Each entry records a choice made for THIS project, its rationale, and (where relevant)
alternatives that were considered and rejected.

---

## 2026-03-13 — Use anthropic SDK directly for all Claude calls (no CLI subprocess)
**Rationale**: Nested `claude` CLI subprocess is blocked inside Claude Code sessions via the `CLAUDECODE` environment variable. The SDK (`anthropic.Anthropic().messages.create()`) works without restriction.
**Alternatives rejected**: subprocess with timeout, temporary file passing, `run_cmd` wrapper.

## 2026-03-13 — Claude-intelligence-driven meta-learning (not regex prefix capture)
**Rationale**: Explicit prefix model ("remember: X") requires unnatural user discipline and captures nothing from normal conversation. Regex over all sentences was too noisy. Semantic extraction by Claude Haiku correctly identifies behavioral rules, domain insights, and project decisions from natural language.
**Alternatives rejected**: magic prefix model, broad regex heuristics.

## 2026-03-13 — Style transfer uses Claude API for qualitative analysis (not surface metrics)
**Rationale**: Regex heuristics (passive ratios, word-ending counts, hedging word lists) are too crude for subtle lab-specific stylistic differences. La Manno papers use mixed tense in ways that surface metrics misidentify. Claude's intelligence correctly identifies 10 qualitative dimensions.
**Alternatives rejected**: spaCy POS-based passive detection, sentence length histograms, hedging lexicon.

## 2026-03-13 — ENCYCLOPEDIA.md is for domain knowledge; RULES.md for AI behavioral rules; DECISION_LOG.md for project choices
**Rationale**: Mixing all captured knowledge into one file (ENCYCLOPEDIA.md) caused noise and made each file less useful. Separation enables targeted loading: RULES.md in every session, ENCYCLOPEDIA.md on-demand for domain questions, DECISION_LOG.md for auditing past choices.

## 2026-03-13 — Token economy: no subagents for simple tasks; no extended thinking by default
**Rationale**: Subagents and extended thinking are expensive and slow. Most tasks are simple enough for direct execution. Reserve subagents for genuinely parallel multi-file work (>10 min subtasks each), extended thinking for novel algorithmic reasoning.

---
