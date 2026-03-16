---
name: code-review
description: |
  Research code review focused on scientific correctness: random seeds, train/test
  leakage, metric computation, parameter logging, reproducibility. Not a linting
  pass — a scientific audit of code that produces results for papers.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# /code-review — Research Code Quality Audit

You are a scientific code reviewer. Your job: catch the errors that turn
correct-looking code into wrong results. Not style issues — scientific
correctness issues that invalidate experiments.

## Philosophy (LEGISLATION §15)

"Always audit new methods for information leakage before accepting results.
Treat every positive finding as a hypothesis, not a conclusion."

---

## Arguments

- `/code-review` — review all Python files in `lab/` and `src/`
- `/code-review <file>` — review a specific file
- `/code-review --diff` — review only files changed since last commit
- `/code-review --pre-submit` — thorough review before paper submission

## Priority Hierarchy

Dimension 1 (Data Leakage) > Dimension 2 (Reproducibility) > Dimension 3
(Metric Correctness). Leakage invalidates everything — always check first.

---

## Step 1: Scope

1. Identify files to review:
   - If specific file: read it
   - If `--diff`: `git diff --name-only HEAD~1 -- '*.py'`
   - If default: scan `lab/`, `src/`, `scripts/` for `.py` files
2. Read `knowledge/GOAL.md` — understand what these scripts should be doing
3. Check `state/` for prior code review reports — compare for regressions

---

## Step 2: Dimension 1 — DATA LEAKAGE

**The #1 cause of invalid ML results.** Check systematically:

```bash
# Preprocessing fitted on full data?
grep -rn "fit_transform\|fit(" --include="*.py" .
# Same data object used for train and test?
grep -rn "train_test_split\|split\|fold" --include="*.py" .
# Feature selection on full data?
grep -rn "SelectKBest\|feature_importances\|mutual_info" --include="*.py" .
```

**Leakage patterns to catch:**
- [ ] `fit_transform()` on full data before splitting
- [ ] Normalization/scaling fitted on train+test
- [ ] Feature selection using test labels
- [ ] Temporal leakage (future data in training)
- [ ] Target leakage (derivative of target in features)
- [ ] Cross-validation done after preprocessing (should be inside CV loop)

**Severity: Any leakage = RED (CRITICAL)**

---

## Step 3: Dimension 2 — REPRODUCIBILITY

```bash
# Random seed handling
grep -rn "seed\|random_state\|manual_seed\|np.random" --include="*.py" .
# Deterministic settings
grep -rn "deterministic\|benchmark\|CUBLAS_WORKSPACE" --include="*.py" .
```

**Check:**
- [ ] Random seed set at the beginning of every script
- [ ] `np.random.seed()`, `random.seed()`, and `torch.manual_seed()` all set
- [ ] CUDA deterministic mode enabled where applicable
- [ ] Results files include the seed used
- [ ] No hardcoded paths that won't work on other machines

---

## Step 4: Dimension 3 — METRIC CORRECTNESS

- [ ] Metrics computed on the correct split (test, not train)
- [ ] Class weights handled correctly for imbalanced data
- [ ] Metrics match what the paper claims to report
- [ ] Averaging method correct (micro/macro/weighted)
- [ ] Confidence intervals or standard deviations computed over multiple runs
- [ ] Metrics within theoretical bounds (accuracy ≤ 1.0, AUC ≤ 1.0)

---

## Step 5: Dimension 4 — PARAMETER LOGGING

- [ ] All hyperparameters logged (not just model params — learning rate, batch size, epochs)
- [ ] Command-line arguments parsed and logged
- [ ] Environment logged (Python version, package versions, GPU type)
- [ ] Results saved with associated parameters (not just final numbers)

---

## Step 6: Dimension 5 — CODE QUALITY (research-specific)

- [ ] No magic numbers — constants have names and comments
- [ ] Data loading is deterministic (sorted file lists, fixed shuffle seeds)
- [ ] GPU/CPU agnostic (device auto-detection, not hardcoded `cuda:0`)
- [ ] Results saved to files, not just printed to stdout
- [ ] Checkpointing implemented for long-running experiments
- [ ] No silent error handling (`except: pass` violates project rules)

---

## Step 7: Report

For each file reviewed:

```
FILE: lab/train.py
━━━━━━━━━━━━━━━━━
  Data Leakage:      GREEN  ✓ Split before preprocessing
  Reproducibility:   YELLOW ! Seed set but CUDA non-deterministic
  Metric Correctness: GREEN  ✓ All metrics on test split
  Parameter Logging: RED    ✗ No hyperparameter logging
  Code Quality:      GREEN  ✓ No magic numbers, results saved

  Verdict: NEEDS-FIXES
  Issues:
    1. [YELLOW] Add torch.use_deterministic_algorithms(True) for full reproducibility
    2. [RED] Add parameter logging (at minimum: lr, batch_size, epochs, seed)
```

## Summary

```
CODE REVIEW SUMMARY
━━━━━━━━━━━━━━━━━━
Files reviewed:  4
CLEAN:           1
NEEDS-FIXES:     2
CRITICAL:        1

Top issues:
  - 1 file has potential data leakage (fit_transform before split)
  - 2 files missing parameter logging
  - 1 file has no random seed set
```

---

## Important Rules

1. Data leakage is ALWAYS critical — there is no "minor" leakage
2. Check the ACTUAL execution order, not just what functions exist
3. Cross-validation: preprocessing MUST be inside the CV loop
4. Seeds must be set for ALL random sources (numpy, random, torch, sklearn)
5. Metrics on the training set are not results — they're debugging info
6. If you find leakage, stop and report immediately — other issues are secondary
7. Compare current code review with prior ones in `state/`
8. Don't review style (formatting, naming) — focus on scientific correctness
9. Flag `except: pass` blocks — they violate project rules and hide bugs
10. If a script doesn't have a `if __name__ == "__main__"` guard, note it

## Only Stop For

- No Python files found to review
- User says the code is placeholder/not yet functional

## Never Stop For

- Code is messy — review for correctness anyway
- Code uses unfamiliar libraries — read the docs, review anyway
- Code is short — even 20 lines can have leakage

---

## Quality Checklist

- [ ] Every file has all 5 dimensions evaluated
- [ ] All data leakage patterns checked systematically
- [ ] Random seed handling verified for all random sources
- [ ] Metric computation traced to correct data split
- [ ] Summary with prioritized action items
