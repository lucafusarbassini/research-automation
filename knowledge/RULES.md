# Behavioral Rules

Automatically captured from user corrections during Claude Code sessions.
Edit or delete entries freely — this file is loaded into every session.

<!-- 2026-03-13 — seeded from session corrections -->
- Never add auto-commit entries to ENCYCLOPEDIA.md; it is for meaningful research insights only
- try-except should be exceptionally rare; code should crash and be debugged, not silently swallowed
- La Manno lab papers use mixed tense, not pure present tense — style analysis must not misidentify tense
- Slack xapp- tokens (Socket Mode) cannot call chat.postMessage or files.upload; always use xoxb- Bot User tokens
- context-hub integration should happen immediately when requested, never deferred to "future work"
- uv should self-install during ricet onboarding just like other tools
- When disabling claude-flow/ruflo, also provide ricet enable-ruflo / disable-ruflo commands
- SLACK_BOT_TOKEN belongs in onboarding credential setup before WandB, not after
- Memory search must not try to start the claude-flow daemon; go straight to keyword search
- Never call nested claude CLI subprocess from inside a Claude Code session (CLAUDECODE env var is set)
- Paper adapt-style style analysis heuristics are too crude for subtle lab-specific style differences
- Do what is asked; nothing more, nothing less — do not add unrequested features or refactoring
