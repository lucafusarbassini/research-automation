# Feature Requests — Chat 1e42abd0 (Init UX Overhaul)

Extracted from user messages in `chat-1e42abd0-init-ux-overhaul.jsonl`
Session date: 2026-02-01 / 2026-02-02

---

## Init & Onboarding

1. **Remove `project_type` from configuration** — Eliminate the unused `project_type` field; hardcode to `"general"` instead of asking the user.
2. **GOAL.md enforcement on `ricet start`** — Block `ricet start` until `knowledge/GOAL.md` contains at least 200 characters of real prose (strip placeholders, headings, HTML comments).
3. **API credential collection during init** — Prompt for all needed API keys (GitHub, HuggingFace, W&B, Google, Medium, LinkedIn, Slack, SMTP, etc.) during `ricet init`, writing to `secrets/.env`.
4. **Step-by-step API key onboarding guide** — Show users how to obtain each API key one at a time, with URLs/video links, covering everything from GitHub SSH (required) to optional services like Google Drive.
5. **Include all MCP-relevant API keys** — Ensure the credential collection and docs cover every key needed by the MCP nucleus tiers (LinkedIn, Medium, Slack, email, Notion, AWS, etc.).
6. **Guided folder structure with READMEs** — Create self-documenting subdirectories (`reference/papers/`, `reference/code/`, `uploads/data/`, `uploads/personal/`) each with a README explaining what to put there. Print a folder map after init.

## Package Management

7. **Automatic package installation at init** — Detect and auto-install missing required packages (typer, rich, pyyaml, python-dotenv) during `ricet init`.
8. **Runtime package auto-install during user work** — Package installation and conflict resolution should happen during active sessions, not only at startup.
9. **Goal-aware AI-driven package detection** — Use a Claude API call (not hardcoded keywords) to analyze `GOAL.md` and intelligently infer which pip packages the project needs (e.g., niche domains like spatial metabolomics).

## Overnight & Execution

10. **Overnight result reporting to user** — Send Slack/email notifications with a summary when overnight jobs complete; write results to `state/PROGRESS.md`.
11. **Docker sandbox for overnight jobs** — Ensure dockerization is set up and documented, with overnight jobs running in sandboxed containers.

## Documentation & Demo

12. **Replace fake README demo with real workflow docs** — Remove the fake console output demo from README; create `docs/demo.md` with a realistic end-to-end workflow (init -> GOAL -> start -> literature -> experiments -> paper -> verify -> publish).
13. **Comprehensive testing guide** — Provide a guide for users to test all functionalities end-to-end, including API keys for major MCPs and voice input.

## Other

14. **Voice input support** — Voice input as a user interaction method (mentioned alongside testing of all functionalities).

---

*4 user messages parsed | 14 unique feature requests identified*
