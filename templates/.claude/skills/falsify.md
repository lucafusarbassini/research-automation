---
name: falsify
description: |
  Popperian adversarial validation — try to break current results. Three modes:
  QUICK (after code changes), STANDARD (after results), DEEP (before submission).
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebSearch
---

# /falsify — Adversarial Validation (Popper Mode)

You are the adversary. Your job is DESTRUCTION, not validation.
A result is only trustworthy if it survives serious attempts to disprove it.

## Philosophy (LEGISLATION §15)

"Treat every positive finding as a hypothesis, not a conclusion. Actively attempt to falsify
it: construct adversarial baselines, test edge cases, look for confounders, and check whether
a simpler explanation fits. A result survives only if it withstands serious attempts to
disprove it."

**You MUST try to break the results.** If everything passes, you haven't tried hard enough.

---

## Arguments

- `/falsify` — STANDARD mode (default): full adversarial review after results
- `/falsify quick` — QUICK: scan recent code changes for showstoppers (5 min)
- `/falsify deep` — DEEP: exhaustive audit before paper submission (30+ min)
- `/falsify <path>` — target a specific script/results file

## Priority Hierarchy

Step 2 (Leakage) > Step 3 (Statistics) > Step 4 (Code Correctness). Never skip the
leakage check — it is the single most common cause of invalid results. In QUICK mode,
run Steps 2 and 4 only.

---

## Step 1: Orient

1. Read `knowledge/GOAL.md` — what claims are being made?
2. Read `state/TODO.md` — what was the intent?
3. Check `state/` for prior falsification reports on this target — verify old issues are fixed.
4. Identify the target:
   - If path given: read that file
   - If QUICK mode: run `git diff HEAD~3 --name-only` to find recently changed files
   - If STANDARD/DEEP: find the main analysis script and its outputs

4. **Catalog the claims.** What does the code/results assert? Write them as testable hypotheses.
   Example: "Claim: Model A outperforms Model B (accuracy 94.2% vs 86.1%)"

**STOP if you cannot identify concrete claims to test.** Ask what to falsify.

---

## Step 2: Attack Vector 1 — DATA LEAKAGE

**The single most common cause of invalid results.** (LEGISLATION §15: "Always audit new
methods for information leakage before accepting results.")

Check systematically:

```bash
# Find train/test split code
grep -rn "train_test_split\|split\|fold\|cv\|cross_val" --include="*.py" .
# Find preprocessing that might leak
grep -rn "fit_transform\|fit(\|StandardScaler\|normalize" --include="*.py" .
# Find data loading — is the same data used for train and eval?
grep -rn "load_data\|read_csv\|Dataset\|DataLoader" --include="*.py" .
```

**Attack checklist:**
- [ ] Is preprocessing (scaling, normalization, imputation) fit on ALL data including test?
  If `scaler.fit_transform(X)` is called on the full dataset before splitting → **CRITICAL**.
- [ ] Is the validation set used for model selection AND reported as final performance?
  (Must be separate held-out test set for final numbers.)
- [ ] Are features that encode the target present? (Temporal leakage, look-ahead bias.)
- [ ] Is future information leaking into past predictions? (Check index ordering.)
- [ ] Are there shared samples between train and test? (`set(train_ids) & set(test_ids)` must be empty.)

**For each issue found:**
```
LEAKAGE FOUND: <description>
  Location: <file:line>
  Evidence: <code snippet>
  Severity: CRITICAL
  Impact: Results are invalid because <explanation>
  Fix: <specific code change>
```

---

## Step 3: Attack Vector 2 — STATISTICAL VALIDITY

**Run the actual tests, don't just inspect code.**

### 3A. Permutation test (the nuclear option)

If feasible, shuffle the labels and rerun. If the "result" still holds with random labels,
the metric is broken or there's leakage.

```python
# Conceptual — adapt to the actual code
import numpy as np
np.random.seed(42)
y_shuffled = np.random.permutation(y)
# Rerun the evaluation with y_shuffled instead of y
```

"For randomized baselines, verify the output is actually different from the original.
Plot and inspect. Use true label shuffling, not shortcuts." (LEGISLATION §15)

### 3B. Multiple comparisons

- How many metrics/tests were run? If >1, was correction applied (Bonferroni, FDR)?
- Is the "best" result cherry-picked from many runs? Report best vs average.

### 3C. Effect size

- Is the effect size meaningful, or just statistically significant with huge N?
- Compute Cohen's d or equivalent if not already reported.

### 3D. Confidence intervals

- Are they reported? Are they narrow enough to be meaningful?
- Would the conclusion change with bootstrap 95% CI?

---

## Step 4: Attack Vector 3 — CODE CORRECTNESS

**Read every line that computes a metric.** (LEGISLATION §15: "Confirm that written
descriptions match the actual code — not guessing or improvising.")

```bash
# Find metric computation
grep -rn "accuracy\|precision\|recall\|f1\|auc\|loss\|mse\|r2\|score" --include="*.py" .
```

**Attack checklist:**
- [ ] Are axes correct? (`axis=0` vs `axis=1` is the most common silent error.)
- [ ] Are indices correct? Off-by-one in data splits?
- [ ] Are there silent NaN propagations? (`np.nanmean` might be hiding broken data.)
- [ ] Does "accuracy" actually measure accuracy? (Read the formula, not the variable name.)
- [ ] Are random seeds set? Different runs should give the same result.
- [ ] Is the metric computed on the right data? (Not accidentally on training data.)

**If a metric should by construction score high for a certain input, verify that it does.
If not, something is wrong.** (LEGISLATION §15)

---

## Step 5: Attack Vector 4 — METHODOLOGY

- [ ] **Baseline fairness**: Does the baseline get the same preprocessing, same data,
  same evaluation protocol? An unfair baseline makes any method look good.
- [ ] **Simpler alternative**: Could a simpler model (linear regression, majority vote)
  achieve similar performance? If yes, the "complex" method isn't adding value.
- [ ] **Cherry-picking**: Is the best run reported or the average? How many runs were done?
  "When results look 'too good to be true,' suspect a bug." (LEGISLATION §15)
- [ ] **Confounders**: Could something other than the proposed method explain the results?
  (Batch effects, class imbalance, data ordering.)

---

## Step 6: Attack Vector 5 — REPRODUCIBILITY

Only in STANDARD and DEEP modes.

- [ ] **Seed sensitivity**: Change random seed (42 → 123). Does performance drop >5%?
  If yes, the result is unstable.
- [ ] **Data sensitivity**: Remove 10% of the data. Does the conclusion hold?
- [ ] **Environment**: Are all dependencies pinned? Can someone else run this?
  `pip freeze > /dev/null` — does the code run without manual intervention?

---

## Step 7: Generate Report

Output the Falsification Report:

```markdown
## Falsification Report

**Target**: <script/results path>
**Mode**: QUICK / STANDARD / DEEP
**Date**: <today>
**Claims tested**: <list of hypotheses from Step 1>

### CRITICAL Issues (must fix before any further work)
1. **[LEAKAGE/STATS/CODE/METHOD/REPRO]**: <description>
   - Evidence: <what you found — code, numbers, output>
   - Impact: <why this invalidates the results>
   - Fix: <specific, actionable fix>

### WARNINGS (should investigate)
1. ...

### PASSED Checks
1. ...

### Falsification Verdict
**X / Y attacks survived.**
<one paragraph: overall assessment, confidence level, recommendation>
```

---

## Step 8: After Falsification

1. **If results FAIL** (any CRITICAL issue):
   - Document clearly in the report what broke and why
   - Update `knowledge/ENCYCLOPEDIA.md` under `## What Doesn't Work`
   - Do NOT recommend promotion to stable/

2. **If results SURVIVE all attacks**:
   - Recommend `ricet promote <path>` to move to `stable/`
   - Update `knowledge/ENCYCLOPEDIA.md` under `## What Works`
   - Note which attacks were run so future sessions know the evidence bar

3. **Save report** to `state/falsification-<target>-<date>.md`

---

## Depth by Mode

| Check | QUICK | STANDARD | DEEP |
|-------|-------|----------|------|
| Data leakage scan | grep only | grep + trace | grep + trace + test |
| Permutation test | skip | if feasible | mandatory |
| Code line-by-line | changed lines only | metric code | everything |
| Baseline fairness | skip | check | check + run alternative |
| Seed sensitivity | skip | 1 alternative seed | 5 seeds + stats |
| Data sensitivity | skip | skip | remove 10%, rerun |

---

## Important Rules

1. Your job is DESTRUCTION, not validation. If everything passes, you haven't tried hard enough.
2. Read every line that computes a metric — don't just grep.
3. A result that only works with one seed is not a result.
4. If leakage is found, stop and report immediately — nothing else matters.
5. Never modify the code you're auditing — only read and test.
6. Check `state/` for prior falsification reports — verify old issues are fixed.
7. Report every finding with file:line, concrete evidence, and specific actionable fix.
8. When results look too good to be true, suspect a bug first (LEGISLATION §3).
9. At end: re-read user's request, verify all aspects addressed.

---

## Quality Checklist

- [ ] Every claim from Step 1 was tested against at least one attack
- [ ] Leakage check covered preprocessing, splitting, and feature construction
- [ ] Code that computes metrics was actually READ line by line, not just grepped
- [ ] Report distinguishes CRITICAL (invalidates results) from WARNING (needs investigation)
- [ ] Each finding has concrete evidence (code snippet, number, file:line)
- [ ] Each finding has a specific actionable fix, not vague advice
- [ ] Verdict states how many attacks survived out of total
- [ ] ENCYCLOPEDIA.md updated with what was learned
- [ ] At end: re-read user's request, verify all aspects addressed (LEGISLATION §1)
