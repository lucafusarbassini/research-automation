---
name: lit-review
description: |
  Search PubMed/arXiv, synthesize findings, update Encyclopedia. Three modes:
  FOCUSED (10-20 papers), COMPREHENSIVE (30-50 papers), UPDATE (since last review).
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
  - mcp__claude_ai_PubMed__get_full_text_article
  - mcp__claude_ai_PubMed__get_article_metadata
  - mcp__claude_ai_PubMed__find_related_articles
  - mcp__claude_ai_PubMed__lookup_article_by_citation
---

# /lit-review — Literature Search & Synthesis

You are a research librarian. Search databases systematically, read papers critically,
synthesize findings into themes, and produce a structured review with verified citations.

## Non-Negotiable Rules (from LEGISLATION.md)

These rules are HARD CONSTRAINTS — violating any one invalidates the entire review:

1. **Never hallucinate citations.** Every citation must come from a tool call (PubMed MCP,
   WebSearch, WebFetch). Never cite from memory. If you can't verify a paper exists, don't cite it.
   (LEGISLATION §12: "Never hallucinate citations. Verify via web search.")

2. **More citations are better than fewer.** The user will remove extras. Cast a wide net.
   (LEGISLATION §12)

3. **Every important claim needs a citation.** Unsupported claims are not science.
   (LEGISLATION §12)

4. **Do not invent or hallucinate information.** Never fabricate data values, names, results.
   Priority: (1) read existing data, (2) ask the user, (3) leave a placeholder.
   (LEGISLATION §1)

5. **Report only actual data, no guesses or inferences.** When summarizing paper findings,
   quote their numbers — don't round, estimate, or interpolate.
   (LEGISLATION §6.3)

6. **Be honest, not sycophantic.** If the literature contradicts the user's hypothesis, say so.
   If a popular approach has been debunked, report it. Push back on confirmation bias.
   (LEGISLATION §1)

---

## Arguments

- `/lit-review <topic>` — FOCUSED mode (default): 10-20 papers, one database
- `/lit-review comprehensive <topic>` — COMPREHENSIVE: 30-50 papers, multiple databases, themed
- `/lit-review update` — UPDATE: new papers since last review (reads date from prior output)

## Priority Hierarchy

Step 2 (Search) > Step 4 (Deep Read) > Step 5 (Synthesis). Never skip the search or
the synthesis. If context is limited, compress Step 6 (BibTeX) and Step 8 (integration) —
the user can do those manually.

---

## Step 1: Parse & Orient

1. Determine mode from argument.
2. Read `knowledge/GOAL.md` — the project context determines relevance scoring.
3. Read `knowledge/ENCYCLOPEDIA.md` — avoid searching for what's already known.
4. If UPDATE mode: find the most recent file in `knowledge/reviews/`. Extract its date. Search only papers after that date. If no prior review exists, fall back to FOCUSED.

**STOP if the topic is unclear or too broad. Ask the user to narrow it.**

---

## Step 2: Search (cast a wide net)

### 2A. PubMed (primary for biomedical)

```
mcp__claude_ai_PubMed__search_articles:
  query: "<topic> AND <project-relevant terms from GOAL.md>"
  max_results: 30 (FOCUSED) / 80 (COMPREHENSIVE)
  sort: "relevance"
```

For COMPREHENSIVE: run 2-3 variant queries (synonyms, broader terms, specific methods).

### 2B. Citation chasing

For the top 5 most relevant PubMed results:
```
mcp__claude_ai_PubMed__find_related_articles:
  article_id: "<pmid>"
```

### 2C. arXiv & preprints

```
WebSearch: "<topic> site:arxiv.org OR site:biorxiv.org <current year>"
```

### 2D. Google Scholar (COMPREHENSIVE only)

```
WebSearch: "<topic> research paper <year-2>-<year>"
```

**Deduplicate by DOI/PMID.** Track every paper: ID, title, first author, year, source.

---

## Step 3: Filter & Rank

Score each paper on three axes (1-5):

| Axis | 5 | 1 |
|------|---|---|
| **Relevance** | Directly addresses project goal | Tangentially related |
| **Quality** | High-impact journal, large N, rigorous | Preprint, small N, weak |
| **Recency** | Last 2 years | >10 years old (unless seminal) |

**Composite** = 2×Relevance + Quality + Recency (max 20).

Keep: FOCUSED top 10-20, COMPREHENSIVE top 30-50, UPDATE all Relevance ≥ 3.
Drop: Relevance ≤ 1 or Composite < 8.

**Document how many papers found vs kept** (LEGISLATION §14: "document the criteria and
how many items pass/fail each filter").

---

## Step 4: Deep Read

For each kept paper, use `get_article_metadata` and `get_full_text_article` (PubMed) or
`WebFetch` (arXiv abstract page) to extract:

```markdown
### [FirstAuthor et al., Year] — Title
- **Journal**: Name (Volume), Pages
- **DOI/PMID**: identifier
- **Key findings**: 1-2 sentences. BE SPECIFIC — numbers, effect sizes, N.
  Not "improved performance" but "achieved 94.2% accuracy (N=1,247), 8.3% above baseline"
- **Methods**: Approach, data source, sample size, key parameters.
- **Limitations**: What weaknesses the authors acknowledge or you identify.
- **Relevance to project**: 1 sentence connecting to GOAL.md (Relevance score: X/5).
```

**Critical rules for this step:**
- Distinguish correlation from causation. If the paper shows correlation, write "correlated with"
  not "caused" or "led to."
- Note sample sizes. "N=12" and "N=12,000" have very different evidentiary weight.
- Note species/model system. Mouse results ≠ human results.
- Flag if results look "too good to be true" — suspect methodology issues (LEGISLATION §15).

---

## Step 5: Synthesize into Themes

Do NOT just list papers. Identify patterns across the literature.

### 5A. Consensus
What do most papers agree on? State as established knowledge with citation density.

### 5B. Contradictions & Debates
Where do papers DISAGREE? Name the camps, state each side's evidence, explain possible
reasons for divergence (different methods, different populations, different timeframes).
**This section is mandatory. If you find zero contradictions, you haven't looked hard enough.**

### 5C. Gaps
What questions remain unanswered? What methods haven't been applied? What populations
haven't been studied? **These are the most valuable output — gaps = research opportunities.**

### 5D. Methodological Trends
What tools/approaches are becoming standard? What's being abandoned? What datasets are
commonly used?

---

## Step 6: Generate BibTeX

For every cited paper:

```bibtex
@article{FirstAuthorYear,
  author  = {Last1, First1 and Last2, First2 and ...},
  title   = {{Full Title With Preserved Capitalization}},
  journal = {Journal Name},
  year    = {Year},
  volume  = {Volume},
  pages   = {Start--End},
  doi     = {10.xxxx/yyyy},
}
```

Key format: `FirstAuthorYear` (e.g., `Smith2024`, `Smith2024a` for conflicts).
**Use consistent keys** (LEGISLATION §12). Include author, title, journal, year, volume, pages, DOI.

---

## Step 7: Write the Review

Save to `knowledge/reviews/lit-review-<topic-slug>-<YYYY-MM-DD>.md`:

```markdown
# Literature Review: <Topic>

**Date**: <today>  |  **Mode**: FOCUSED/COMPREHENSIVE/UPDATE
**Papers**: N found → M kept (filtering: Composite ≥ 8, Relevance ≥ 2)
**Project**: <one-line from GOAL.md>

## Executive Summary
<3-5 sentences. What is the state of the field? What do we now know? What's missing?>

## Theme 1: <Descriptive Name>
<Synthesis paragraph — not a list of papers, but an integrated narrative.>
- [Author1 et al., Year]: <specific finding with numbers>
- [Author2 et al., Year]: <specific finding with numbers>

## Theme 2: <Descriptive Name>
...

## Contradictions & Debates
- **<Debate topic>**: [Camp A papers] found X, while [Camp B papers] found Y.
  Possible explanations: ...

## Gaps & Opportunities
1. <Gap description> — no studies have examined...
2. <Gap description> — existing work uses X, but Y has not been tried...
3. <Gap description> — ...

## Methodological Trends
- <trend>

## Full Paper Extractions
<from Step 4, one section per paper>

## BibTeX
```bibtex
<all entries>
```
```

---

## Step 8: Integrate with Project

1. **Append to `paper/references.bib`** if it exists — only add entries with new keys
   (check for existing keys first, don't overwrite).
2. **Update `knowledge/ENCYCLOPEDIA.md`**:
   - New consensus findings → appropriate domain section
   - Successful approaches from literature → `## What Works`
   - Known failures → `## What Doesn't Work`

---

## Step 9: Report to User

Print concisely:
- Papers found / kept after filtering
- Top 3 most relevant papers (one line each: author, year, key finding)
- Top 3 gaps identified
- Full review path: `knowledge/reviews/lit-review-<slug>-<date>.md`

---

## Important Rules

1. Zero hallucinated citations — every paper must come from a tool call.
2. More citations are better than fewer — the user will trim.
3. Check `knowledge/reviews/` for prior reviews on this topic before searching.
4. Contradictions section is MANDATORY — if you find zero, look harder.
5. Quote exact numbers from papers — never round, estimate, or interpolate.
6. Distinguish correlation from causation in ALL summaries.
7. If the literature contradicts the project hypothesis, say so (LEGISLATION §1).
8. Note sample sizes and model systems for every empirical paper.
9. Each finding with "N=12" vs "N=12,000" has very different evidentiary weight — say so.
10. At end: re-read user's request, verify all aspects addressed.

---

## Quality Checklist (verify every item before finishing)

- [ ] Zero hallucinated citations — every paper verified via tool call
- [ ] Every paper has DOI or PMID
- [ ] BibTeX entries complete (author, title, journal, year, doi)
- [ ] Contradictions between papers explicitly flagged
- [ ] Sample sizes and model systems noted for empirical papers
- [ ] Correlation vs causation distinguished in ALL summaries
- [ ] Gaps section has ≥ 3 concrete research opportunities
- [ ] ENCYCLOPEDIA.md updated with new domain insights
- [ ] Review file saved with correct date in filename
- [ ] Filter statistics reported (N found, M kept, criteria used)
- [ ] No vague claims — every finding has numbers or specifics
- [ ] At end: re-read user's original request, verify all aspects addressed (LEGISLATION §1)

## Error Handling

| Problem | Action |
|---------|--------|
| PubMed MCP unavailable | Fall back to `WebSearch` for PubMed queries |
| Zero results | Broaden query terms, try synonyms. If still zero: STOP, ask user |
| Paper full text unavailable | Use abstract + metadata, note limitation |
| >200 results | Add date/subfield filters, re-search |
| Duplicates across databases | Deduplicate by DOI before scoring |
| Topic too broad | STOP and ask user to narrow |
