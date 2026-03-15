# ricet v1 Testing Guide

Comprehensive manual testing guide for all features built or modified in the last week.
Run these tests in order; each section is independent unless noted.

---

## Prerequisites

```bash
# Install ricet in dev mode
pip install -e .

# Verify CLI is available
ricet --version

# Ensure Claude Code is installed
claude --version
```

---

## 1. Project Initialization (`ricet init`)

```bash
mkdir /tmp/test-project && cd /tmp/test-project
ricet init
```

**Verify:**
- [ ] Interactive questionnaire runs (project name, goal, compute type, credentials)
- [ ] `knowledge/` created with: GOAL.md, CONSTRAINTS.md, RULES.md, ENCYCLOPEDIA.md, DECISION_LOG.md
- [ ] `knowledge/LEGISLATION.md` and `knowledge/PHILOSOPHY.md` deployed from defaults
- [ ] `.claude/CLAUDE.md` created with skills table, memory hierarchy, anti-drift rules
- [ ] `.claude/skills/` contains all 8 skills: lit-review, experiment-review, paper-draft, falsify, reproduce, research-retro, overnight, slides
- [ ] `state/SYSTEM.md` created
- [ ] `lab/` and `stable/` directories created
- [ ] `paper/` directory with LaTeX template (Albert's template)
- [ ] meta_learn_hook registered (check `.claude/settings.json` for UserPromptSubmit hook)
- [ ] GOAL.md populated with user's project description (not empty placeholder)
- [ ] state/TODO.md auto-generated from GOAL.md
- [ ] tectonic, biber, and uv installed or install attempted
- [ ] No MEMORY.md anywhere (dead file removed)

---

## 2. Project Adoption (`ricet adopt`)

```bash
cd /tmp
git clone https://github.com/some-user/some-repo test-adopt
cd test-adopt
ricet adopt
```

**Verify:**
- [ ] Detects existing README and pre-fills GOAL.md from it
- [ ] Creates personal branch (`user-<username>`)
- [ ] Installs ricet scaffolding without clobbering existing files
- [ ] `.claude/` and `knowledge/` created alongside existing code

---

## 3. Session Start (`ricet start`)

```bash
cd /tmp/test-project
ricet start
```

**Verify:**
- [ ] Refuses to start if GOAL.md is empty or placeholder
- [ ] Enriches tasks with CONSTRAINTS.md content
- [ ] Opens Claude Code session with project context

---

## 4. Mobile Companion (`ricet mobile`)

```bash
ricet mobile start
```

**Verify:**
- [ ] Tunnel mode is the default (not ngrok)
- [ ] Tailscale serve used if available (`tailscale serve --bg`)
- [ ] Screen session created for background persistence
- [ ] URL written to disk for retrieval
- [ ] Phone can access the endpoint and send voice/text prompts
- [ ] Output ring buffer works (mobile-friendly truncated output)

---

## 5. Voice Input (`ricet voice`)

```bash
ricet voice
```

**Verify:**
- [ ] Microphone recording works
- [ ] Transcription produces text
- [ ] Supports 30+ languages (test with non-English if possible)
- [ ] Transcribed prompt is executed by Claude

---

## 6. Meta-Learn Hook

The hook runs automatically on every user prompt in a Claude Code session.

**Test procedure:**
1. Start a session: `ricet start`
2. Give Claude a correction: "don't use print statements for logging, always use the logging module"
3. End the session
4. Check files:

**Verify:**
- [ ] `knowledge/RULES.md` contains the new behavioral rule
- [ ] Entry is clean text, not garbled user frustration (quality filter works)
- [ ] No duplicate entries if the same rule was given before (dedup works)
- [ ] Entries shorter than 15 chars or with excessive punctuation (!!!) are rejected
- [ ] `knowledge/ENCYCLOPEDIA.md` not polluted with auto-commit noise

---

## 7. Knowledge & RAG

```bash
# Semantic search over encyclopedia
ricet memory search "machine learning classification"

# Log a decision
ricet memory log-decision "chose XGBoost over RF because of feature importance"

# Stats
ricet memory stats
```

**Verify:**
- [ ] `search` returns ranked results from ENCYCLOPEDIA.md
- [ ] `log-decision` appends to DECISION_LOG.md with timestamp
- [ ] `stats` shows entry counts per file

---

## 8. Code Indexing & Search

```bash
# Index a codebase
ricet index-code core/

# Search it
ricet search-code "notification slack"
```

**Verify:**
- [ ] `index-code` creates `state/code_index.md` with function/class signatures
- [ ] `search-code` returns relevant file matches with context

---

## 9. Lab/Stable Promotion

```bash
# Create a test script in lab/
echo 'print("hello")' > lab/test_analysis.py

# Promote it
ricet promote lab/test_analysis.py
```

**Verify:**
- [ ] File copied to `stable/test_analysis.py`
- [ ] Provenance file created: `stable/test_analysis.py.provenance.json`
- [ ] Provenance contains: source path, git hash, timestamp, metrics

---

## 10. Feature Requests

```bash
# Log a feature request
ricet feature-request "add dark mode to dashboard"

# Review pending requests
ricet implement-features
```

**Verify:**
- [ ] Request appended to `state/feature_requests.md` with timestamp
- [ ] `implement-features` lists pending features for selection
- [ ] Selected features get worktree branches (uses `core/git_worktrees.py`)

---

## 11. Collaboration

```bash
# Morning sync (merge user-* branches)
ricet morning-sync

# Daily sync (pull, rebase, push)
ricet sync
```

**Verify:**
- [ ] `morning-sync` finds and merges all `user-*` branches into main
- [ ] `sync` does pull --rebase then push without data loss

---

## 12. Auto-Commit

```bash
# Make some changes in a session, check that auto-commit doesn't pollute ENCYCLOPEDIA.md
```

**Verify:**
- [ ] Auto-commits work (files are committed)
- [ ] ENCYCLOPEDIA.md does NOT get noisy "auto-commit: test" entries
- [ ] Commit messages are descriptive

---

## 13. Slack Integration

Requires `SLACK_BOT_TOKEN` with `files:write` scope.

```bash
# Test via Python
python -c "
from core.slack_delivery import send_plot
# send_plot('test.png', '#claude_plots', 'Test upload')
print('Import works')
"
```

**Verify:**
- [ ] `send_plot()` uploads files via Slack v2 API (files.getUploadURLExternal)
- [ ] No auth header sent to the upload URL (bug was fixed)
- [ ] Text notifications via webhook work (`core/notifications.py`)

---

## 14. Paper Pipeline

```bash
ricet paper status
```

**Verify:**
- [ ] LaTeX template uses Albert's template
- [ ] `tectonic` compiles `paper/main.tex` without errors
- [ ] `biber` runs for bibliography

---

## 15. Slides

```bash
ricet slides create
```

**Verify:**
- [ ] `slides/slides_task.md` generated
- [ ] `/slides` skill produces `make_slides.py`
- [ ] Script generates schematics and builds `.pptx`

---

## 16. Research Skills (Slash Commands)

Test each in a Claude Code session (`ricet start`):

| Skill | Test prompt | Verify |
|-------|------------|--------|
| `/lit-review` | `/lit-review single-cell RNA-seq` | Searches PubMed, writes review to `knowledge/reviews/` |
| `/experiment-review` | `/experiment-review lab/analysis.py` | Produces 6-dimension audit with traffic-light scores |
| `/paper-draft` | `/paper-draft intro` | Presents outline first, waits for approval, then drafts LaTeX |
| `/falsify` | `/falsify lab/analysis.py` | Tries to break results, checks for leakage |
| `/reproduce` | `/reproduce lab/analysis.py` | Runs with multiple seeds, produces stability matrix |
| `/research-retro` | `/research-retro` | Produces session retrospective with tweetable summary |
| `/overnight` | `/overnight` | Runs TODO list autonomously |
| `/slides` | `/slides` | Generates presentation |

---

## 17. Zenodo Publishing

```bash
ricet zenodo --help
```

**Verify:**
- [ ] `zenodo publish-software` packages and uploads to Zenodo
- [ ] `zenodo publish-dataset` uploads datasets with DOI
- [ ] Reads GOAL.md for metadata

---

## 18. Package Publishing

```bash
ricet package --help
```

**Verify:**
- [ ] Generates pyproject.toml if missing
- [ ] Uses `uv` as package manager (not pip)
- [ ] Builds and publishes to PyPI

---

## 19. Updater (Cascading Self-Update)

```bash
ricet --version  # note current version
# After a git pull of ricet itself:
# _init_update() should refresh skills and defaults in existing projects
```

**Verify:**
- [ ] `_init_update()` refreshes `.claude/skills/` if source is newer
- [ ] `_init_update()` refreshes `knowledge/LEGISLATION.md` and `knowledge/PHILOSOPHY.md`
- [ ] Existing user edits in other files are not overwritten

---

## 20. gstack Integration

```bash
ricet gstack install
ricet gstack status
```

**Verify:**
- [ ] gstack skills installed globally to `~/.claude/skills/`
- [ ] `status` shows installed skills
- [ ] Does not interfere with ricet's own `.claude/skills/`

---

## 21. claude-flow (ruflo) MCP

```bash
ricet enable-ruflo
ricet disable-ruflo
```

**Verify:**
- [ ] `enable-ruflo` adds claude-flow MCP to `.mcp.json`
- [ ] `disable-ruflo` removes it
- [ ] MCP tools (`mcp__claude-flow__*`) available in session after enabling

---

## 22. Website & Docs

```bash
ricet website create
ricet docs
```

**Verify:**
- [ ] Website scaffold generated
- [ ] `docs` auto-updates documentation from source code

---

## 23. ENCYCLOPEDIA.md Cleanliness

After running several sessions:

**Verify:**
- [ ] ENCYCLOPEDIA.md is under 200 lines (was cleaned from 3910 to ~152)
- [ ] No duplicate "auto-commit:" entries
- [ ] Entries are meaningful domain knowledge, not operational noise

---

## Running Automated Tests

```bash
# Unit tests
pytest tests/ -x -q

# Specific modules
pytest tests/test_onboarding.py -v
pytest tests/test_meta_rules.py -v
pytest tests/test_adopt.py -v
pytest tests/test_mobile.py -v
pytest tests/test_collaboration.py -v
pytest tests/test_auto_commit.py -v
pytest tests/test_knowledge.py -v

# Integration test
python tests/integration/run_full_test.py
```

---

## Under Development (not ready for testing)

- **Reproducibility pipeline** (`/reproduce` skill): placeholder, needs real multi-seed experiments
- **Manual curation of MD skills**: all 8 written but need human review and field-testing
- **core/agents.py**: AgentType enum is stale (references deleted agent types); routing now handled by skills

---

## Quick Smoke Test (5 minutes)

If you only have time for a quick check:

```bash
# 1. Init a fresh project
mkdir /tmp/smoke && cd /tmp/smoke && ricet init

# 2. Verify scaffolding
ls knowledge/ .claude/skills/ state/ lab/ stable/

# 3. Check skills deployed
ls .claude/skills/  # should show 8 .md files

# 4. Check meta-learn hook
cat .claude/settings.json | grep -A2 UserPromptSubmit

# 5. Start a session
ricet start --session-name smoke-test

# 6. In session: test a skill
# Type: /research-retro

# 7. Check knowledge files after session
cat knowledge/RULES.md
wc -l knowledge/ENCYCLOPEDIA.md
```
