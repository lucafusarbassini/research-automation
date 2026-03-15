---
name: overnight
description: |
  Autonomous overnight research session. Reads TODO list, executes tasks
  sequentially with checkpointing. Sends significant results to Slack.
  Generates review report. Fully autonomous — no human interaction.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
  - WebSearch
---

# /overnight — Autonomous Research Session

You are running an autonomous overnight research session. Execute the project's TODO list
without human supervision. Checkpoint aggressively. Send significant results to Slack.
Generate a review report when done.

**This is fully autonomous. Do NOT ask questions. Make decisions yourself.**

## Only stop for

- A task that requires external data you cannot access (API keys, datasets, hardware)
- A critical failure that makes all remaining tasks impossible (corrupted data, broken env)
- A safety concern (about to delete important data, overwrite user edits)

## Never stop for

- A single task failing (skip after 3 retries, continue to next)
- Missing optional dependencies (work around or skip gracefully)
- Ambiguous task descriptions (interpret best you can, document your interpretation)
- Test failures on non-critical tasks (log and continue)
- Warnings from linters, compilers, or libraries (log and continue)

---

## Priority Hierarchy

Step 1 (Orient) > Step 3 (Execute Loop) > Step 4A (Retrospective). Never skip orientation
or the retrospective. If time runs out, compress Step 4B (Review Report) but still commit.

---

## Step 1: Orient

Read ALL of these (order matters — later files depend on earlier context):

```
knowledge/GOAL.md              # What we're trying to achieve
knowledge/CONSTRAINTS.md       # Hard rules
knowledge/LEGISLATION.md       # Behavioral rules (FOLLOW THESE)
knowledge/RULES.md             # User corrections (FOLLOW THESE)
state/TODO.md                  # Task list — this is your work queue
knowledge/ENCYCLOPEDIA.md      # Domain knowledge accumulated so far
```

**Check for prior overnight reports:**
```bash
ls -t state/overnight-report-*.md 2>/dev/null | head -3
```
If prior reports exist, read the most recent one. Note: what was completed, what failed,
what was deferred. Do not repeat failed tasks unless TODO.md explicitly re-queues them.

**Summarize your understanding internally:** What is the goal? What's done? What's next?

**Continue silently.** Do not output your understanding — just proceed.

---

## Step 2: Prioritize

From `state/TODO.md`, build a task queue:

1. **Blocked tasks** → skip entirely, note in report
2. **Quick wins** (<10 min) → do first for momentum
3. **High priority** → do next
4. **Medium priority** → fill remaining time
5. **Risky/experimental** → do last, with extra verification

**Output a one-line task list** before starting:
```
Overnight queue: [task1] → [task2] → [task3] → ... (N tasks, M blocked)
```

---

## Step 3: Execute Loop

For each task in priority order:

### 3A. Before Starting
- Read any files the task touches
- Search `knowledge/ENCYCLOPEDIA.md` for relevant prior work
- Estimate: SMALL (<10 min), MEDIUM (10-30 min), LARGE (30+ min)

### 3B. Execute
Delegate to the appropriate skill when applicable:
- Analysis/audit → run the experiment-review or falsify procedure internally
- Writing → run the paper-draft procedure internally
- Literature → run the lit-review procedure internally
- Reproducibility → run the reproduce procedure internally
- Everything else → execute directly

**For each task, follow LEGISLATION.md.** Every rule applies during overnight mode.

### 3C. After Each Task

1. **Verify** — re-read changed files, run tests if applicable, confirm outputs exist
2. **Commit** — `git add <specific files> && git commit -m "<type>: <descriptive message>"`
3. **Update state** — mark task done in `state/TODO.md`
4. **Slack notify** (significant results only):
   ```python
   from core.slack_delivery import send_plot, send_text
   # Only for: new best metric, surprising finding, milestone, critical failure
   send_text("Overnight: completed <task>. Key finding: <result>.")
   ```

**Continue silently after routine tasks.** Only log significant events.

### 3D. Failure Handling

```
Attempt 1: Investigate error, fix root cause, retry
Attempt 2: Try alternative approach, retry
Attempt 3: Log failure with full error trace, SKIP, move to next task
```

- If a critical dependency is missing: skip all dependent tasks, note in report
- NEVER silently swallow errors — every failure logged to `state/overnight-log-<date>.md`
- If a task produces suspicious results ("too good to be true"): run falsification
  checks before accepting (LEGISLATION §15)

---

## Step 4: Wrap Up

### 4A. Research Retrospective
Run the research-retro procedure internally:
- What worked, what failed, what surprised
- Update `knowledge/ENCYCLOPEDIA.md` with learnings
- Update `knowledge/DECISION_LOG.md` with any decisions made

### 4B. Review Report
Generate `state/overnight-report-<YYYY-MM-DD>.md`:

```markdown
## Overnight Session Report

**Date**: <today>
**Duration**: <start> to <end>
**Tasks**: X completed / Y total (Z skipped, W failed)

### Task Results

| # | Task | Status | Key Output |
|---|------|--------|------------|
| 1 | <task> | DONE / SKIPPED / FAILED | <one-line result> |
| 2 | ... | ... | ... |

### Files Changed
<output of `git diff --name-status` against session start commit>

### Files Needing Human Review
- <file> — reason: <security-sensitive / algorithmic change / config change>

### Key Findings
1. <most important finding with evidence>
2. <second finding>
3. <third finding>

### Failures & Deferred
1. <task> — failed because: <reason> — suggested fix: <action>

### Knowledge Updates
- ENCYCLOPEDIA.md: <N> entries added
- DECISION_LOG.md: <N> decisions recorded
```

### 4C. Slack Summary
```python
send_text(
    "Overnight session complete.\n"
    f"Completed: {done}/{total} tasks\n"
    f"Key results: {top_findings}\n"
    f"Review: state/overnight-report-{date}.md"
)
```

### 4D. Final Commit
```bash
git add state/TODO.md state/overnight-report-*.md state/overnight-log-*.md
git commit -m "overnight: session complete — X/Y tasks done"
```

---

## Important Rules

1. **Follow LEGISLATION.md** — every rule applies to overnight mode, no exceptions.
2. **Commit after every task.** If the session crashes, completed work is preserved.
3. **Never overwrite existing outputs.** Save to new paths with timestamps.
4. **Slack only for significant events** — not routine progress. Max 5 notifications per session.
5. **Never modify files the user explicitly edited** (check git blame if unsure).
6. **Skip after 3 failures** — don't burn the entire session on one stuck task.
7. **Log everything.** The human reads the report to understand what happened overnight.
8. **Check prior overnight reports** before starting — don't repeat known failures.
9. **Run falsification on any result that looks too good** (LEGISLATION §15).
10. **At end: verify every TODO item was addressed or explicitly skipped with reason.**
