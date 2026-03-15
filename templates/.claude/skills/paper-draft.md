---
name: paper-draft
description: Draft a paper section with lab style conventions
---

# Paper Draft

You are now in **writer mode**. Your job is to draft a section of a scientific paper following the lab's conventions.

## Before Writing

1. Read `knowledge/GOAL.md` — understand the project
2. Read `knowledge/LEGISLATION.md` — follow coding and writing style rules
3. Read `paper/main.tex` if it exists — understand the paper structure
4. Check `paper/references.bib` — know what citations are available

## Style Conventions

- **Tense**: Past tense for methods and results. Present tense for established facts and interpretation.
- **Voice**: Active voice preferred ("We analyzed..." not "The data was analyzed...")
- **Structure**: One idea per paragraph. First sentence = topic sentence.
- **Citations**: [Author, Year] format. Every claim needs a citation or data reference.
- **Figures**: Reference every figure before it appears in the text.

## Workflow

1. **Ask which section** — Introduction, Methods, Results, Discussion, Abstract? Or a specific subsection?

2. **Outline first** — Present a bullet-point outline for approval before writing prose.

3. **Draft** — Write in LaTeX. Use:
   - `\section{}`, `\subsection{}` for structure
   - `\cite{}` for references (check bib file for keys)
   - `\ref{}` for figures and tables
   - Precise, quantitative language ("increased by 15%" not "increased significantly")

4. **Self-review** — Before presenting:
   - Every paragraph has exactly one main point
   - No paragraph exceeds 150 words
   - All abbreviations defined at first use
   - No dangling references or citations

5. **Output** — Present the LaTeX source. If the user approves, write it to the appropriate file in `paper/`.
