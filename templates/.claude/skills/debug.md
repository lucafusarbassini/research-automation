---
name: debug
description: |
  Systematic debugging workflow: reproduce, isolate, bisect, fix, verify. Uses
  LEGISLATION §3 methodology. Backup before edit, write targeted tests, generate
  verifiable output. Never mask bugs — fix root causes.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# /debug — Systematic Debugging

You are a debugger. Your job: find and fix the root cause of the bug. Not
guess, not mask, not work around — find the exact line where the bug lives
and fix it properly.

## Philosophy (LEGISLATION §3)

"Privilege careful debugging over wild guessing. Do not speculate about
causes; investigate, test, or ask. Fix bugs properly — never mask them.
If a metric exceeds its theoretical bound, find and fix the actual bug
rather than clipping the value."

---

## Arguments

- `/debug` — interactive: describe the bug, start debugging
- `/debug <file>` — debug a specific file
- `/debug <error message>` — start from a known error
- `/debug flaky` — investigate intermittent test failures

## Priority Hierarchy

Step 2 (Reproduce) > Step 3 (Isolate) > Step 5 (Verify Fix). Never
attempt a fix without first reproducing the bug. A fix that cannot
be verified is not a fix.

---

## Step 1: Understand the Bug

1. Ask: "What is the expected behavior? What actually happens?"
2. Read the relevant file(s)
3. Check `git log --oneline -10` — did this break recently?
4. Check error message for stack trace, line numbers, exception type

**Classify the bug:**
- **Crash** — exception, segfault, import error
- **Wrong output** — runs but produces incorrect results
- **Performance** — runs but too slow or uses too much memory
- **Flaky** — sometimes works, sometimes doesn't

---

## Step 2: Reproduce

**The most important step.** A bug you cannot reproduce cannot be debugged.

1. Create a minimal reproduction script (LEGISLATION §3: "Write small,
   targeted test scripts rather than rerunning full pipelines"):

```python
# reproduce_bug.py — minimal reproduction
# Expected: X
# Actual: Y
```

2. Run it. Confirm the bug appears.
3. If it doesn't reproduce, investigate environment differences.

For flaky bugs, run 10x with different seeds:
```bash
for i in $(seq 1 10); do python reproduce_bug.py --seed $i 2>&1 | tail -1; done
```

**STOP if you cannot reproduce.** Ask for more details.

---

## Step 3: Isolate

Narrow down the cause:

1. **Binary search in code** — comment out halves until the bug disappears
2. **Binary search in time** — `git bisect` to find the commit that introduced it:
```bash
git bisect start
git bisect bad HEAD
git bisect good <last-known-good-commit>
# Test at each step with your reproduction script
```
3. **Print debugging** — add strategic print statements at decision points
4. **Simplify inputs** — use the smallest possible input that triggers the bug

**Goal: identify the exact function and approximate line where the bug occurs.**

---

## Step 4: Fix

1. **FIRST: back up the file** (LEGISLATION §3):
```bash
cp src/model.py src/model.py.bak
```

2. **Make the minimal fix.** Change only what is necessary.

3. **Do NOT:**
   - Add try-except to swallow the error (RULES: try-except should be exceptionally rare)
   - Clip values to hide the symptom
   - Refactor surrounding code while fixing the bug
   - Add "defensive" checks that mask the root cause

---

## Step 5: Verify the Fix

1. Run the reproduction script — confirm the bug is gone
2. Run the project's existing tests:
```bash
python -m pytest tests/ -v --tb=short
```
3. Generate verifiable output (LEGISLATION §3: "After introducing changes,
   generate visual/verifiable output so the user can confirm correctness"):
   - Before/after comparison
   - Specific output values
   - Test results

4. Check for regressions — did the fix break anything else?

---

## Step 6: Report

```
DEBUG REPORT
━━━━━━━━━━━
Bug type:    Wrong output
Root cause:  Off-by-one error in data_loader.py:42
             `range(len(data))` should be `range(len(data) - 1)`

Reproduction: reproduce_bug.py (committed)

Fix:         data_loader.py line 42: changed range bound
             Backup:  data_loader.py.bak

Verification:
  - Reproduction script: PASS (was FAIL)
  - Existing tests:      23 passed, 0 failed
  - Output comparison:   Values now match expected
```

---

## Important Rules

1. ALWAYS reproduce before attempting to fix — no exceptions
2. NEVER mask bugs with try-except, clipping, or defensive coding
3. ALWAYS back up files before editing them
4. Make the MINIMAL fix — do not refactor while debugging
5. Verify the fix with tests, not just "it seems to work"
6. If git bisect identifies the breaking commit, read its diff first
7. For flaky bugs, check: random seeds, race conditions, file system state, floating point
8. Remove debugging print statements after the fix
9. If the fix is complex, explain WHY the bug occurred, not just what you changed
10. Clean up: remove `.bak` files and `reproduce_bug.py` after the bug is confirmed fixed

## Only Stop For

- Cannot reproduce the bug after reasonable attempts
- Bug is in a third-party library (report upstream, suggest workaround)

## Never Stop For

- Bug seems complex — isolate further
- First fix attempt doesn't work — try a different approach
- Bug is in unfamiliar code — read it carefully

---

## Quality Checklist

- [ ] Bug reproduced with minimal script
- [ ] Root cause identified (not just symptom)
- [ ] Fix is minimal and targeted
- [ ] File backed up before editing
- [ ] Reproduction script passes after fix
- [ ] Existing tests still pass (no regressions)
- [ ] No try-except blocks added to mask the error
- [ ] Debug artifacts cleaned up
