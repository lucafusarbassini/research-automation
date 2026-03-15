---
name: lit-review
description: Search literature, summarize findings, update Encyclopedia
---

# Literature Review

You are now in **researcher mode**. Your job is to find, read, and synthesize relevant literature for the user's query.

## Workflow

1. **Clarify scope** — Ask the user what topic, time range, and depth they want. If they already specified, proceed.

2. **Search** — Use available tools to find relevant papers:
   - PubMed MCP tools (`mcp__claude_ai_PubMed__search_articles`, `get_full_text_article`)
   - arXiv search if relevant
   - Google Scholar via web search
   - Target: 10-20 papers for a focused review, 30-50 for a comprehensive one

3. **Read and extract** — For each relevant paper:
   - Title, authors, year, journal
   - Key findings (1-2 sentences)
   - Methods used
   - Relevance to the user's project (check `knowledge/GOAL.md`)

4. **Synthesize** — Organize findings into themes:
   - What is known (consensus)
   - What is debated (contradictions)
   - What is missing (gaps = opportunities)
   - Methodological trends

5. **Output** — Write a structured summary with:
   - Executive summary (3-5 sentences)
   - Themed sections with citations
   - Gap analysis
   - Suggested next steps
   - BibTeX entries for all cited papers (append to `paper/references.bib` if it exists)

6. **Update Encyclopedia** — Append key domain insights to `knowledge/ENCYCLOPEDIA.md` under the appropriate section.

## Quality Standards

- Prefer primary sources over reviews (unless the user asked for a review of reviews)
- Always note sample sizes, species/model systems, and key limitations
- Flag papers that contradict each other explicitly
- Distinguish correlation from causation in your summaries
