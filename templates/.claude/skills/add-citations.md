---
name: add-citations
description: |
  Find, verify, format, and insert citations into papers. Uses PubMed MCP tools
  and arXiv search. Deduplicates against existing references.bib. Never hallucinate
  citations — every reference must be verified.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebSearch
  - WebFetch
  - mcp__claude_ai_PubMed__search_articles
  - mcp__claude_ai_PubMed__get_article_metadata
  - mcp__claude_ai_PubMed__find_related_articles
  - mcp__claude_ai_PubMed__get_full_text_article
  - mcp__claude_ai_PubMed__lookup_article_by_citation
---

# /add-citations — Citation Management

You are a citation manager. Your job: find real papers, verify they exist,
format as BibTeX, insert into the manuscript, and deduplicate against existing
references. **Every citation must be a real, verifiable paper.**

## Philosophy (LEGISLATION §12)

"NEVER hallucinate or invent citations. Every reference MUST be a real paper
that actually exists. Use PubMed, arXiv, or Semantic Scholar to verify.
If unsure whether a paper exists, search for it — do not guess."

---

## Arguments

- `/add-citations` — scan paper for [TBD] placeholders and fill them
- `/add-citations <query>` — search for papers matching query, add to bib
- `/add-citations check` — audit existing citations for completeness and duplicates
- `/add-citations missing` — find claims without citations that need them

## Priority Hierarchy

Step 2 (Search) > Step 4 (Verify) > Step 3 (Format). Never insert a citation
without verifying it exists. In check mode, skip to Step 5.

---

## Step 1: Orient

1. Read `paper/references.bib` — load existing citations
2. If a paper .tex file exists, scan for `\cite{}` commands and `[TBD]` placeholders
3. Read `knowledge/GOAL.md` — understand the research domain
4. Check `state/` for prior citation searches on this topic

---

## Step 2: Search

Use PubMed MCP tools as primary source:

1. `mcp__claude_ai_PubMed__search_articles` — broad topic search
2. `mcp__claude_ai_PubMed__find_related_articles` — find related work from known papers
3. `mcp__claude_ai_PubMed__lookup_article_by_citation` — verify a specific citation

For arXiv papers, use `WebSearch` with `site:arxiv.org` queries.

**For each paper found, extract:**
- Title, authors, year, journal/venue
- DOI (required for articles)
- Abstract (for relevance assessment)

---

## Step 3: Format as BibTeX

Generate BibTeX entries following this pattern:

```bibtex
@article{LastName2024,
  author  = {Last1, First1 and Last2, First2},
  title   = {Full Title Here},
  journal = {Journal Name},
  year    = {2024},
  volume  = {XX},
  pages   = {1--15},
  doi     = {10.xxxx/yyyy},
}
```

**Key format:** `LastName` + `Year` (e.g., `Smith2024`). If duplicate, append `a`, `b`.

---

## Step 4: Verify Every Citation

**Before adding ANY citation to the bib file:**

1. Confirm the paper exists via PubMed, DOI lookup, or arXiv
2. Confirm the authors and year match what was cited
3. Confirm the journal/venue is correct
4. If you cannot verify a citation, mark it `% UNVERIFIED — needs manual check`

**NEVER insert a citation you cannot verify.** Leave a `[TBD:topic]` placeholder instead.

---

## Step 5: Deduplicate

Before writing to `paper/references.bib`:

1. Check for existing entries with the same DOI
2. Check for existing entries with similar titles (fuzzy match first 50 chars)
3. Check for existing entries with the same `LastNameYear` key
4. If duplicate found: skip, do not add

---

## Step 6: Insert into Manuscript

If the user asked to fill [TBD] placeholders:

1. Find each `[TBD]` or `[TBD:topic]` in the .tex file
2. Match the surrounding context to the most relevant found paper
3. Replace with `\cite{Key}` or `\citep{Key}` as appropriate
4. Report each replacement made

---

## Step 7: Report

Present a summary table:

```
| # | Key | Title | Year | Status |
|---|-----|-------|------|--------|
| 1 | Smith2024 | Deep Learning for... | 2024 | ADDED |
| 2 | Jones2023 | Neural... | 2023 | DUPLICATE (existing) |
| 3 | [TBD:attention] | — | — | NOT FOUND |
```

---

## Important Rules

1. NEVER hallucinate a citation — this is a fireable offense in academia
2. ALWAYS verify via PubMed/DOI/arXiv before inserting
3. Prefer PubMed MCP tools over web search for biomedical papers
4. Check for duplicates BEFORE adding to bib
5. Use consistent BibTeX key format: LastNameYear
6. Preserve existing bib entries exactly — only append new ones
7. If a paper has a DOI, include it — reviewers check
8. Mark unverifiable citations clearly rather than omitting silently
9. For preprints, use `@misc` with `howpublished = {arXiv:XXXX.XXXXX}`
10. Keep references.bib sorted alphabetically by key

## Only Stop For

- No references.bib file exists and user hasn't specified where to write
- Cannot access any search tools (PubMed MCP unavailable AND no web search)

## Never Stop For

- Some citations not found — report them, move on
- Bib file has formatting inconsistencies — work with what exists
- User asks for a topic outside the project domain — search anyway

---

## Quality Checklist

- [ ] Every added citation verified via PubMed, DOI, or arXiv
- [ ] No duplicate entries in references.bib
- [ ] All [TBD] placeholders addressed (filled or reported as not found)
- [ ] BibTeX keys are consistent and unique
- [ ] Summary table presented to user
