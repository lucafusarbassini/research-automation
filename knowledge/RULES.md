# Behavioral Rules

Fundamental principles captured from user corrections.
Edit freely — this file is loaded into every session.

- try-except should be exceptionally rare; code must crash loudly so bugs are found and fixed, not silently swallowed
- La Manno lab papers use mixed tense (past for methods/results, present for interpretation) — never identify as "pure present tense"
- Style analysis heuristics are too crude for subtle lab-specific differences; use Claude's full intelligence for style transfer
- Never call nested claude CLI subprocess from inside a Claude Code session (CLAUDECODE env var blocks it)
- Do exactly what is asked; nothing more, nothing less — no unrequested refactoring, features, or content creation
- When in doubt about scope, ask rather than guess or assume
- Always double-check user's message at end of task to make sure all requests are addressed
- claude-flow is discontinued; remove references when encountered, keep MCP option available but not default
