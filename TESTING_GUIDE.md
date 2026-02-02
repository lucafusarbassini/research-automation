# ricet 0.3.0 -- Comprehensive Testing Guide

Copy-paste commands to test every feature as a real user. Each section covers one feature area with realistic usage. Check outputs against the expected behavior described in each section.

---

## Prerequisites

```bash
# From the repo root where pyproject.toml lives.
# -e installs in editable mode: imports resolve to your local source,
# so any code changes take effect immediately without reinstalling.
cd /home/fusar/claude/research-automation
pip install -e ".[dev]"
ricet --version
# Expected: ricet 0.3.0
```

---

## 1. Project Initialization (`ricet init`)

### 1a. Basic init

```bash
mkdir -p /tmp/ricet-test && cd /tmp/ricet-test
ricet init demo-project
```

**Check:** Interactive wizard asks for goal, project type, timeline. A `demo-project/` directory is created with:
- `.claude/` (CLAUDE.md, agents/, skills/, hooks/)
- `knowledge/` (GOAL.md, ENCYCLOPEDIA.md, CONSTRAINTS.md)
- `paper/` (main.tex, references.bib)
- `config/` (settings.yml)
- `state/`

### 1b. Init with custom path and skip-repo TBD

```bash
ricet init test-skip --path /tmp/ricet-test --skip-repo
```

**Check:** Project created at `/tmp/ricet-test/test-skip/` without GitHub repo creation prompt.

### 1c. Verify scaffolded files

```bash
ls -la /tmp/ricet-test/demo-project/.claude/agents/
cat /tmp/ricet-test/demo-project/knowledge/GOAL.md
cat /tmp/ricet-test/demo-project/config/settings.yml
```

**Check:** 7 agent markdown files exist. GOAL.md contains your entered goal. settings.yml has your compute/notification config.

---

## 2. Configuration (`ricet config`)

```bash
cd /tmp/ricet-test/demo-project

# View current config
ricet config

# Reconfigure notifications
ricet config notifications

# Reconfigure compute
ricet config compute

# Reconfigure credentials
ricet config credentials
```

**Check:** Each section shows an interactive prompt to update settings. `config/settings.yml` is updated after each change.

---

## 3. Interactive Session (`ricet start`)

```bash
cd /tmp/ricet-test/demo-project

# Basic start
ricet start

# Named session
ricet start --session-name "test-session-1"
```

**Check:** Claude Code launches with the project's agent prompts loaded. A session is recorded in `state/sessions/`. Try giving it a simple task like "List the files in this project."

---

## 4. Project Status (`ricet status`)

```bash
cd /tmp/ricet-test/demo-project
ricet status
```

**Check:** Displays TODO items from `state/TODO.md`, progress from `state/PROGRESS.md`, and resource stats.

---

## 5. Session Listing (`ricet list-sessions`)

```bash
cd /tmp/ricet-test/demo-project
ricet list-sessions
```

**Check:** Shows a table of all recorded sessions with name, start time, status, and task counts.

---

## 6. Agent Status (`ricet agents`)

```bash
cd /tmp/ricet-test/demo-project
ricet agents
```

**Check:** Lists all agent types (master, researcher, coder, reviewer, falsifier, writer, cleaner) with their roles and budget allocations.

---

## 7. Knowledge / Memory (`ricet memory`)

### 7a. Log a decision

```bash
cd /tmp/ricet-test/demo-project
ricet memory log-decision "Use Adam optimizer with lr=0.001 based on initial experiments"
```

**Check:** Entry appended to `knowledge/ENCYCLOPEDIA.md` under "Decisions" with a timestamp.

### 7b. Search knowledge

```bash
ricet memory search "optimizer" --top-k 3
```

**Check:** Returns matching entries from the encyclopedia.

### 7c. Export knowledge

```bash
ricet memory export
```

**Check:** Prints the full encyclopedia content.

### 7d. Knowledge stats

```bash
ricet memory stats
```

**Check:** Shows entry counts by section.

---

## 8. Metrics (`ricet metrics`)

```bash
cd /tmp/ricet-test/demo-project
ricet metrics
```

**Check:** Displays token usage estimates, cost stats, and system resource info. If claude-flow is available, shows actual metrics.

---

## 9. Paper Pipeline (`ricet paper`)

### 9a. Check paper structure

```bash
cd /tmp/ricet-test/demo-project
ricet paper check
```

**Check:** Verifies `paper/main.tex` exists and has expected sections (Abstract, Introduction, Methods, Results, Discussion, Conclusion).

### 9b. Build paper (requires LaTeX)

```bash
ricet paper build
```

**Check:** Runs pdflatex -> biber -> pdflatex -> pdflatex. Produces `paper/main.pdf` if LaTeX is installed.

### 9c. Update paper content

```bash
ricet paper update
```

**Check:** Uses Claude to suggest updates to paper sections based on project state.

### 9d. Modernize paper formatting

```bash
ricet paper modernize
```

**Check:** Updates LaTeX formatting to modern standards.

### 9e. Style transfer (requires a reference PDF)

```bash
ricet paper adapt-style --reference /home/fusar/claude/research-automation/templates/paper/journals/nature/s41586-023-06812-z.pdf
```

**Check:** Analyzes the reference style and reports style metrics. Attempts to rewrite paper sections in that style.

---

## 10. Literature Search (`ricet cite` and `ricet discover`)

### 10a. Citation search

```bash
cd /tmp/ricet-test/demo-project
ricet cite "attention mechanisms in transformers" --max 3
```

**Check:** Searches Semantic Scholar/arXiv, displays results, and appends BibTeX entries to `paper/references.bib`.

### 10b. Broad discovery

```bash
ricet discover "graph neural networks for drug discovery" --max 3
```

**Check:** Broader literature scan with ranked results, abstracts, and citation counts.

### 10c. Discover with auto-cite

```bash
ricet discover "large language model efficiency" --cite --max 2
```

**Check:** Results are automatically added to `paper/references.bib`.

---

## 11. URL Browsing (`ricet browse`)

```bash
cd /tmp/ricet-test/demo-project
ricet browse "https://en.wikipedia.org/wiki/Attention_(machine_learning)"
```

**Check:** Fetches the URL and extracts readable text content.

### 11a. Browse with screenshot

```bash
ricet browse "https://paperboatch.com/" --screenshot /tmp/example-screenshot.png
```

**Check:** Saves a screenshot (requires Puppeteer MCP).

---

## 12. Verification (`ricet verify`)

```bash
cd /tmp/ricet-test/demo-project
ricet verify "Our model achieves 95% accuracy on CIFAR-10 using a simple MLP"
```

**Check:** Fact-checks the claim and reports confidence scores. Flags suspicious claims.

---

## 13. Auto-Debug (`ricet debug`)

```bash
cd /tmp/ricet-test/demo-project

# Create a buggy script to debug
cat > /tmp/buggy.py << 'EOF'
def divide(a, b):
    return a / b

result = divide(10, 0)
print(result)
EOF

ricet debug "python /tmp/buggy.py"
```

**Check:** Captures the ZeroDivisionError, suggests a fix, and attempts to apply and retry.

---

## 14. Overnight Mode (`ricet overnight`)

### 14a. Dry run with minimal iterations

```bash
cd /tmp/ricet-test/demo-project

# Create a TODO file
cat > state/TODO.md << 'EOF'
# TODO

- [ ] Create a simple hello world script
- [ ] Add a docstring to the script
EOF

ricet overnight --iterations 2
```

**Check:** Reads TODO, executes tasks autonomously, commits after each. Stops after 2 iterations.

### 14b. Custom task file

```bash
cat > /tmp/custom-tasks.md << 'EOF'
# Tasks

- [ ] Print the current date in Python
EOF

ricet overnight --task-file /tmp/custom-tasks.md --iterations 1
```

**Check:** Uses the custom task file instead of `state/TODO.md`.

---

## 15. Autonomous Routines (`ricet auto`)

### 15a. Add a routine

```bash
cd /tmp/ricet-test/demo-project
ricet auto add-routine --name nightly-check --command "ricet verify 'hello'" --schedule daily --desc "Nightly verification"
```

**Check:** Routine is registered and shown in the output.

### 15b. List routines

```bash
ricet auto list-routines
```

**Check:** Shows all registered routines with schedule and last run time.

### 15c. Monitor a topic

```bash
ricet auto monitor --topic "transformer architectures"
```

**Check:** Sets up topic monitoring for literature updates.

---

## 16. Reproducibility (`ricet repro`)

### 16a. Log an experiment run

```bash
cd /tmp/ricet-test/demo-project
ricet repro log --run-id exp-001 --command "python train.py --lr 0.001" --notes "Baseline experiment"
```

**Check:** Creates `state/runs/exp-001.json` with run metadata.

### 16b. List all runs

```bash
ricet repro list
```

**Check:** Shows a table of all logged runs.

### 16c. Show run details

```bash
ricet repro show --run-id exp-001
```

**Check:** Displays full details of the specified run.

### 16d. Hash a dataset

```bash
echo "sample,data,here" > /tmp/dataset.csv
ricet repro hash --path /tmp/dataset.csv
```

**Check:** Computes and displays SHA-256 hash of the file.

---

## 17. MCP Discovery (`ricet mcp-search`)

### 17a. Search for MCPs

```bash
ricet mcp-search "database migration"
ricet mcp-search "browser automation"
ricet mcp-search "paper search arxiv"
```

**Check:** Returns matching MCP servers from the 1300+ catalog with name, description, and install command.

### 17b. Search with auto-install (use with caution)

```bash
ricet mcp-search "sequential thinking" --install
```

**Check:** Installs the matched MCP server.

---

## 18. MCP Server Creation (`ricet mcp-create`)

```bash
ricet mcp-create my-custom-mcp --desc "A custom MCP for my research data" --tools "fetch_data,process_data,export_results"
```

**Check:** Generates MCP server boilerplate code with the specified tools.

---

## 19. Test Generation (`ricet test-gen`)

```bash
cd /tmp/ricet-test/demo-project

# Create a source file to generate tests for
mkdir -p src
cat > src/calculator.py << 'EOF'
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
EOF

ricet test-gen
```

**Check:** Scans for source files without tests and generates pytest stubs.

### 19a. Test generation for specific file

```bash
ricet test-gen --file src/calculator.py
```

**Check:** Generates tests specifically for `calculator.py`.

---

## 20. Auto-Documentation (`ricet docs`)

```bash
cd /tmp/ricet-test/demo-project
ricet docs --force
```

**Check:** Scans source files, extracts functions/classes, and updates `docs/API.md`, `docs/MODULES.md`, and appends missing commands to README.

---

## 21. Goal Fidelity (`ricet fidelity`)

```bash
cd /tmp/ricet-test/demo-project
ricet fidelity
```

**Check:** Compares codebase state against `knowledge/GOAL.md`. Reports a fidelity score (0-100) and flags drift areas.

---

## 22. Daily Maintenance (`ricet maintain`)

```bash
cd /tmp/ricet-test/demo-project
ricet maintain
```

**Check:** Runs four routines sequentially: test-gen, docs-update, fidelity-check, verify-pass. Reports results for each.

---

## 23. Adopt Existing Repo (`ricet adopt`)

### 23a. Adopt a local directory

```bash
mkdir -p /tmp/existing-repo
cd /tmp/existing-repo
git init
echo "# My Existing Project" > README.md
git add . && git commit -m "Initial commit"

cd /tmp/ricet-test
ricet adopt /tmp/existing-repo --name adopted-project
```

**Check:** Overlays ricet workspace structure onto the existing repo. `knowledge/GOAL.md` is pre-filled from the README. Project is registered in `~/.ricet/projects.json`.

### 23b. Adopt from GitHub (no fork)

```bash
ricet adopt https://github.com/octocat/Hello-World --no-fork --name hello-test
```

**Check:** Clones the repo and scaffolds it as a ricet project without forking.

---

## 24. Cross-Repo RAG (`ricet link`, `ricet unlink`, `ricet reindex`)

### 24a. Link a repository

```bash
cd /tmp/ricet-test/demo-project

# Create a repo to link
mkdir -p /tmp/linked-repo
echo "def attention(q, k, v): return softmax(q @ k.T) @ v" > /tmp/linked-repo/model.py
echo "# Shared Utils" > /tmp/linked-repo/README.md

ricet link /tmp/linked-repo --name shared-utils
```

**Check:** Links the repo for read-only RAG search. Indexes text files.

### 24b. Search across linked repos

```bash
ricet memory search "attention mechanism"
```

**Check:** Results include matches from linked repos, tagged with `[shared-utils]`.

### 24c. Re-index

```bash
ricet reindex
```

**Check:** Re-indexes all linked repositories.

### 24d. Unlink

```bash
ricet unlink shared-utils
```

**Check:** Removes the linked repo. Subsequent searches no longer include its files.

---

## 25. Cross-Project Learning (`ricet sync-learnings`)

```bash
cd /tmp/ricet-test/demo-project

# First add some knowledge to another project
mkdir -p /tmp/ricet-test/other-project/knowledge
cat > /tmp/ricet-test/other-project/knowledge/ENCYCLOPEDIA.md << 'EOF'
# Project Encyclopedia

## Tricks

- [2025-01-15 10:00] Using mixed precision training reduces memory by 40% with minimal accuracy loss.

## What Works

- [2025-01-15 11:00] Cosine annealing schedule works better than step decay for fine-tuning.
EOF

ricet sync-learnings /tmp/ricet-test/other-project
```

**Check:** Transfers encyclopedia entries from the other project into the current project's knowledge base.

---

## 26. Dual-Repo Structure (`ricet two-repo`)

### 26a. Initialize

```bash
cd /tmp/ricet-test/demo-project
ricet two-repo init
```

**Check:** Creates `experiments/` and `clean/` directories.

### 26b. Check status

```bash
ricet two-repo status
```

**Check:** Shows what files are in each side.

### 26c. Promote files

```bash
# Create a file in experiments
mkdir -p experiments
echo "validated_code = True" > experiments/validated.py

ricet two-repo promote --files "validated.py" --message "Promote validated code"
```

**Check:** Copies `validated.py` from `experiments/` to `clean/`.

### 26d. Diff between sides

```bash
ricet two-repo diff
```

**Check:** Shows differences between experiments/ and clean/.

---

## 27. Infrastructure (`ricet infra`)

### 27a. Infrastructure check

```bash
cd /tmp/ricet-test/demo-project
ricet infra check
```

**Check:** Verifies Docker, CI, and dependency status.

### 27b. CI/CD setup

```bash
ricet infra cicd --template python
```

**Check:** Generates GitHub Actions workflow files.

### 27c. Secrets management

```bash
ricet infra secrets
```

**Check:** Lists project secrets configuration.

---

## 28. Runbook Execution (`ricet runbook`)

### 28a. Dry run

```bash
cat > /tmp/test-runbook.md << 'RUNBOOK'
# Setup Runbook

## Step 1: Check Python

```bash
python3 --version
```

## Step 2: Check pip

```bash
pip --version
```

## Step 3: List files

```bash
ls -la
```
RUNBOOK

cd /tmp/ricet-test/demo-project
ricet runbook /tmp/test-runbook.md
```

**Check:** Parses 3 code blocks and shows them without executing (dry-run mode).

### 28b. Execute

```bash
ricet runbook /tmp/test-runbook.md --execute
```

**Check:** Executes each code block sequentially and reports pass/fail.

---

## 29. Git Worktrees (`ricet worktree`)

### 29a. List worktrees

```bash
cd /tmp/ricet-test/demo-project
ricet worktree list
```

**Check:** Lists active git worktrees (may be empty initially).

### 29b. Add a worktree

```bash
ricet worktree add experiment-branch
```

**Check:** Creates a new git worktree for `experiment-branch`.

### 29c. Remove a worktree

```bash
ricet worktree remove experiment-branch
```

**Check:** Removes the worktree.

### 29d. Prune stale worktrees

```bash
ricet worktree prune
```

**Check:** Cleans up stale worktree references.

---

## 30. Task Queue (`ricet queue`)

### 30a. Submit tasks

```bash
cd /tmp/ricet-test/demo-project
ricet queue submit --prompt "Analyze the dataset and report summary statistics"
ricet queue submit --prompt "Generate a scatter plot of the results"
```

**Check:** Tasks added to the queue.

### 30b. Check queue status

```bash
ricet queue status
```

**Check:** Shows queued tasks with their IDs and status.

### 30c. Drain the queue

```bash
ricet queue drain --workers 2
```

**Check:** Executes queued tasks with up to 2 parallel workers.

### 30d. Cancel all

```bash
ricet queue cancel-all
```

**Check:** Clears all pending tasks.

---

## 31. Multiple Projects (`ricet projects`)

### 31a. List projects

```bash
ricet projects list
```

**Check:** Shows all registered ricet projects with paths and status.

### 31b. Register current project

```bash
cd /tmp/ricet-test/demo-project
ricet projects register
```

**Check:** Registers the current project in `~/.ricet/projects.json`.

---

## 32. Package Management (`ricet package`)

### 32a. Initialize package

```bash
cd /tmp/ricet-test/demo-project
ricet package init
```

**Check:** Scaffolds `pyproject.toml`, `setup.cfg`, and package directory structure.

### 32b. Build package

```bash
ricet package build
```

**Check:** Builds sdist and wheel distributions in `dist/`.

### 32c. Publish (use --test for TestPyPI)

```bash
# Don't run this without a real package -- just check it prompts correctly
ricet package publish
```

**Check:** Attempts to publish to PyPI (will fail without valid credentials -- that's expected).

---

## 33. Website Builder (`ricet website`)

### 33a. Initialize site

```bash
cd /tmp/ricet-test/demo-project
ricet website init
```

**Check:** Scaffolds an MkDocs site with Material theme.

### 33b. Build site

```bash
ricet website build
```

**Check:** Builds static HTML site.

### 33c. Preview site

```bash
ricet website preview
```

**Check:** Starts a local preview server.

---

## 34. Voice Prompting (`ricet voice`)

```bash
cd /tmp/ricet-test/demo-project
ricet voice --duration 5
```

**Check:** Attempts to record audio for 5 seconds, transcribe, and display the structured prompt. If no microphone or whisper is installed, shows helpful error messages with install instructions.

---

## 35. Mobile Companion (`ricet mobile`)

### 35a. Server status

```bash
cd /tmp/ricet-test/demo-project
ricet mobile status
```

**Check:** Shows mobile server status.

### 35b. Connection info

```bash
ricet mobile connect-info
```

**Check:** Displays connection details (IP, port, QR code if possible).

### 35c. Pair a device

```bash
ricet mobile pair --label "my-phone"
```

**Check:** Generates a pairing token for mobile access.

### 35d. List tokens

```bash
ricet mobile tokens
```

**Check:** Lists all active pairing tokens.

---

## 36. Social Publishing (`ricet publish`)

```bash
cd /tmp/ricet-test/demo-project
ricet publish medium
ricet publish linkedin
```

**Check:** Drafts a research summary for the specified platform using Claude. Shows the draft for review.

---

## 37. Zapier Integration (`ricet zapier`)

```bash
cd /tmp/ricet-test/demo-project
ricet zapier setup --key "test-key-12345"
```

**Check:** Configures Zapier NLA integration with the provided API key.

---

## 38. Review CLAUDE.md (`ricet review-claude-md`)

```bash
cd /tmp/ricet-test/demo-project
ricet review-claude-md
```

**Check:** Reviews and suggests simplifications to the project's `.claude/CLAUDE.md`.

---

## 39. Auto-Commit Behavior

```bash
cd /tmp/ricet-test/demo-project

# Verify auto-commit is on
echo $RICET_AUTO_COMMIT  # Should be "true" or unset (defaults to true)
echo $AUTO_PUSH           # Should be "true" or unset (defaults to true)

# Disable auto-commit for testing
export RICET_AUTO_COMMIT=false
ricet config notifications   # Make a change
git status                    # Changes should NOT be committed

# Re-enable
export RICET_AUTO_COMMIT=true
ricet config compute          # Make a change
git log --oneline -3          # Should see an auto-commit
```

**Check:** Auto-commit behavior toggles correctly with environment variables.

---

## 40. Environment Variables

Test the key environment variables that control behavior:

```bash
# Disable Claude CLI calls (for offline/CI testing)
export RICET_NO_CLAUDE=true
ricet agents           # Should work with keyword fallback
ricet fidelity         # Should work with local heuristics
unset RICET_NO_CLAUDE

# Disable auto-commit
export RICET_AUTO_COMMIT=false
# ... run commands, verify no auto-commits ...
unset RICET_AUTO_COMMIT

# Disable auto-push
export AUTO_PUSH=false
# ... run commands, verify commits but no pushes ...
unset AUTO_PUSH
```

---

## 41. Running the Test Suite

### 41a. Full test suite

```bash
cd /home/fusar/claude/research-automation
python -m pytest tests/ -v
```

### 41b. Single module tests

```bash
python -m pytest tests/test_agents.py -v
python -m pytest tests/test_onboarding.py -v
python -m pytest tests/test_paper.py -v
python -m pytest tests/test_mcps.py -v
python -m pytest tests/test_model_router.py -v
python -m pytest tests/test_knowledge.py -v
python -m pytest tests/test_verification.py -v
python -m pytest tests/test_reproducibility.py -v
python -m pytest tests/test_auto_debug.py -v
python -m pytest tests/test_autonomous.py -v
python -m pytest tests/test_browser.py -v
python -m pytest tests/test_voice.py -v
python -m pytest tests/test_mobile.py -v
python -m pytest tests/test_cross_repo.py -v
python -m pytest tests/test_adopt.py -v
python -m pytest tests/test_collaboration.py -v
python -m pytest tests/test_auto_commit.py -v
python -m pytest tests/test_style_transfer.py -v
python -m pytest tests/test_security.py -v
python -m pytest tests/test_notifications.py -v
python -m pytest tests/test_session.py -v
python -m pytest tests/test_tokens.py -v
python -m pytest tests/test_resources.py -v
python -m pytest tests/test_environment.py -v
python -m pytest tests/test_doability.py -v
python -m pytest tests/test_prompt_suggestions.py -v
python -m pytest tests/test_rag_mcp.py -v
python -m pytest tests/test_lazy_mcp.py -v
python -m pytest tests/test_devops.py -v
python -m pytest tests/test_git_worktrees.py -v
python -m pytest tests/test_multi_project.py -v
python -m pytest tests/test_two_repo.py -v
python -m pytest tests/test_markdown_commands.py -v
python -m pytest tests/test_meta_rules.py -v
python -m pytest tests/test_gallery.py -v
python -m pytest tests/test_website.py -v
python -m pytest tests/test_task_spooler.py -v
python -m pytest tests/test_prompt_queue.py -v
python -m pytest tests/test_social_media.py -v
python -m pytest tests/test_automation_utils.py -v
python -m pytest tests/test_claude_helper.py -v
python -m pytest tests/test_claude_flow.py -v
python -m pytest tests/test_auto_docs.py -v
python -m pytest tests/test_goal_orchestration.py -v
python -m pytest tests/test_integration_bridge.py -v
python -m pytest tests/test_task_management.py -v
```

### 41c. With coverage

```bash
python -m pytest tests/ -v --cov=core --cov=cli --cov-report=term-missing
```

---

## 42. Docker Overnight (requires Docker)

```bash
cd /home/fusar/claude/research-automation

# Build the Docker image
docker build -t ricet docker/

# Run overnight in Docker sandbox
cd /tmp/ricet-test/demo-project
ricet overnight --iterations 3 --docker
```

**Check:** Builds image if needed, mounts project directory, runs overnight loop inside the container.

---

## 43. Cleanup

```bash
rm -rf /tmp/ricet-test
rm -rf /tmp/existing-repo
rm -f /tmp/buggy.py /tmp/dataset.csv /tmp/reference.txt /tmp/test-runbook.md /tmp/custom-tasks.md
```
