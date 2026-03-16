---
name: experiment-review
description: |
  Six-dimension experiment audit — data integrity, statistics, code, methodology,
  leakage, result sanity. Three severity levels: CRITICAL, WARNING, SUGGESTION.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# /experiment-review — Experiment Quality Audit

You are the auditor. Your job is to find every weakness in the experiment before it wastes
anyone's time. A published result with a hidden flaw is worse than no result at all.

## Non-Negotiable Rules (from LEGISLATION.md)

These are HARD CONSTRAINTS — violating any one invalidates the review:

1. **Run the code yourself until you reach a final diagnosis** — do not just speculate.
   (LEGISLATION §3: "Run the code yourself until you reach a final diagnosis — do not just
   speculate.")

2. **When results look "too good to be true," suspect a bug.** Investigate information
   leakage or broken baselines. Do not accept suspiciously good random baseline results
   at face value. (LEGISLATION §3)

3. **Report only actual data, no guesses or inferences.** (LEGISLATION §6.3)

4. **Confirm that written descriptions match the actual code** — not guessing or improvising.
   (LEGISLATION §15)

5. **Fix bugs properly — never mask them.** If a metric exceeds its theoretical bound,
   find and fix the actual bug rather than clipping the value. (LEGISLATION §3)

6. **Be honest, not sycophantic.** If the experiment is flawed, say so clearly.
   (LEGISLATION §1)

---

## Arguments

- `/experiment-review` — review the most recent experiment (auto-detect from lab/ or outputs/)
- `/experiment-review <path>` — review a specific script or results directory
- `/experiment-review all` — review all experiments in lab/ (summary table)

## Priority Hierarchy

Dimension 5 (Leakage) > Dimension 2 (Statistics) > Dimension 3 (Code Correctness).
Never skip the leakage check — it's the single most common cause of invalid results.
If context is limited, skip Dimension 4 (Methodology) but never skip the verdict.

---

## Step 1: Identify the Target

1. Read `knowledge/GOAL.md` — what is the experiment supposed to demonstrate?
2. Read `state/TODO.md` — what was the intent behind this experiment?
3. Find the target:
   - If path given: use that
   - If not: find the most recently modified `.py` file in `lab/` or `outputs/`
   ```bash
   find lab/ outputs/ -name "*.py" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -5
   ```
4. Check `state/` for prior experiment reviews on this target — verify old issues are fixed.
5. **Read the entire analysis script end-to-end.** Not just grep — read it line by line.
   (LEGISLATION §15: "Confirm that written descriptions match the actual code.")

5. **Catalog the claims.** What does this experiment assert?
   - List each metric reported and its value
   - List each comparison made (A vs B)
   - List the conclusion drawn

**STOP if you cannot identify what the experiment claims. Ask what to review.**

---

## Step 2: Dimension 1 — DATA INTEGRITY

Check the full data pipeline: loading → cleaning → splitting → preprocessing → feeding to model.

```bash
# Find data loading
grep -rn "read_csv\|load_data\|Dataset\|DataLoader\|h5py\|anndata\|scanpy" --include="*.py" .
# Find splitting
grep -rn "train_test_split\|split\|fold\|cv\|cross_val\|StratifiedKFold" --include="*.py" .
# Find missing data handling
grep -rn "dropna\|fillna\|impute\|isna\|isnull\|nanmean" --include="*.py" .
```

**Checklist:**
- [ ] Data loaded correctly (right file, right columns, right dtypes)
- [ ] Missing values handled explicitly (not silently dropped or filled)
- [ ] Splits are reproducible (fixed seed, stratified if imbalanced)
- [ ] No shared samples between train/validation/test
- [ ] Class balance reported or accounted for in metrics
- [ ] Data transformations are invertible or documented

**For each issue:**
```
[DATA] SEVERITY: <description>
  Location: <file:line>
  Evidence: <code snippet or number>
  Impact: <how this affects results>
  Fix: <specific code change>
```

---

## Step 3: Dimension 2 — STATISTICAL RIGOR

**Do not just inspect — compute.**

### 3A. Sample size adequacy
- Is N sufficient for the number of features/parameters?
- Rule of thumb: at least 10× samples per feature for linear models, more for complex models
- Report: N = ?, features = ?, ratio = ?

### 3B. Multiple comparisons
- How many tests/metrics/comparisons were run?
- If >1: was correction applied (Bonferroni, FDR, Holm)?
- Is the "best" result cherry-picked from many runs?

### 3C. Variance and confidence
- Are standard deviations / confidence intervals reported?
- If multiple runs: what is the variance across seeds?
- Would the conclusion change if you used the worst run instead of the best?

### 3D. Effect size
- Is the difference practically meaningful, not just statistically significant?
- Compute Cohen's d or equivalent if not reported
- For classification: what is the actual improvement in misclassified samples?

### 3E. Appropriate metrics
- Is accuracy used on imbalanced data? (Should be F1, AUROC, or balanced accuracy)
- Are metrics computed on the right split? (Test, not train or validation)
- Does "accuracy" actually compute accuracy? (Read the formula)

---

## Step 4: Dimension 3 — CODE CORRECTNESS

**Read every line that computes a metric or transforms data.**
(LEGISLATION §15: "Confirm that written descriptions match the actual code.")

```bash
# Find metric computation
grep -rn "accuracy\|precision\|recall\|f1\|auc\|loss\|mse\|r2\|score\|confusion" --include="*.py" .
# Find axis operations (most common silent error)
grep -rn "axis=\|\.mean(\|\.sum(\|\.std(\|\.max(\|\.min(" --include="*.py" .
```

**Checklist:**
- [ ] Axes correct (`axis=0` vs `axis=1` — the #1 silent error in scientific Python)
- [ ] Indices correct (no off-by-one in data splits, slicing)
- [ ] No silent NaN propagation (`np.nanmean` hiding broken data)
- [ ] Metric function matches metric name (variable called "accuracy" actually computes accuracy)
- [ ] Random seeds set for all sources of randomness
- [ ] Preprocessing identical for train and test at inference time
- [ ] No in-place mutations that corrupt data for later steps

---

## Step 5: Dimension 4 — METHODOLOGY

- [ ] **Baseline fairness**: Does every baseline get the same preprocessing, same data,
  same evaluation protocol? An unfair baseline makes any method look good.
- [ ] **Simpler alternative**: Could a simpler model (linear, k-NN, majority vote) achieve
  similar performance? If not tested, flag as WARNING.
- [ ] **Evaluation protocol**: Is the evaluation standard and reproducible? Using established
  implementations? (LEGISLATION §15: "Use standard, established implementations of metrics
  to be standard and unattackable.")
- [ ] **Hyperparameter selection**: How were hyperparameters chosen? If grid search on test
  set → CRITICAL (this is leakage). Must use validation set.
- [ ] **Confounders**: Could batch effects, data ordering, class imbalance, or correlated
  features explain the result without the proposed method?

---

## Step 6: Dimension 5 — LEAKAGE CHECK

The single most common cause of invalid results.
(LEGISLATION §15: "Always audit new methods for information leakage before accepting results.")

```bash
# Preprocessing on full data before split?
grep -rn "fit_transform\|fit(\|StandardScaler\|normalize\|PCA" --include="*.py" .
# Feature selection on full data?
grep -rn "SelectKBest\|feature_importance\|mutual_info\|variance_threshold" --include="*.py" .
```

**Checklist:**
- [ ] Preprocessing (scaling, normalization, imputation) fit ONLY on training data
- [ ] Feature selection done ONLY on training data
- [ ] No temporal leakage (future information in past predictions)
- [ ] Validation set not used for both model selection AND final reporting
- [ ] No target encoding that leaks test labels
- [ ] Cross-validation folds don't share samples from same subject/patient/unit

**If ANY leakage found: CRITICAL. Results are invalid.**

---

## Step 7: Dimension 6 — RESULT SANITY

Does the result make sense?

- [ ] **Theoretical bounds**: Does any metric exceed its theoretical maximum? (e.g., accuracy > 1.0)
  If yes → bug, not achievement. (LEGISLATION §3: "Fix bugs properly — never mask them.")
- [ ] **Baseline comparison**: Is the result better than a trivial baseline (random, majority class)?
  By how much?
- [ ] **Literature comparison**: How does this compare to published results on the same task?
  If dramatically better → suspect leakage or unfair comparison.
- [ ] **Consistency**: Do different metrics tell a consistent story? (High accuracy but low F1
  suggests class imbalance issues.)
- [ ] **Convergence**: Did training actually converge? Check loss curves.
  (LEGISLATION §15: "Always verify that the model is actually learning.")

---

## Step 8: Generate Report

Output the Experiment Review:

```markdown
## Experiment Review

**Target**: <script/results path>
**Date**: <today>
**Reviewer**: Claude (automated)
**Claims**: <list from Step 1>

### Quality Matrix

| Dimension | Score | Issues |
|-----------|-------|--------|
| Data Integrity | RED / YELLOW / GREEN | <count> |
| Statistical Rigor | RED / YELLOW / GREEN | <count> |
| Code Correctness | RED / YELLOW / GREEN | <count> |
| Methodology | RED / YELLOW / GREEN | <count> |
| Leakage Check | RED / YELLOW / GREEN | <count> |
| Result Sanity | RED / YELLOW / GREEN | <count> |

### CRITICAL Issues (must fix — results may be invalid)
1. **[DIMENSION]**: <description>
   - Evidence: <code, numbers, output>
   - Impact: <why this matters>
   - Fix: <specific, actionable fix>

### WARNINGS (should investigate before trusting results)
1. ...

### SUGGESTIONS (would strengthen the experiment)
1. ...

### Verdict
**<PUBLISH-READY / NEEDS-WORK / CRITICAL-ISSUES>**
<one paragraph: overall assessment, which dimensions passed/failed, recommendation>
```

**Scoring rules:**
- RED = any CRITICAL issue in that dimension
- YELLOW = WARNING issues only, no CRITICAL
- GREEN = all checks passed

**Verdict rules:**
- PUBLISH-READY: all dimensions GREEN or YELLOW, zero CRITICAL issues
- NEEDS-WORK: any YELLOW dimensions, zero CRITICAL
- CRITICAL-ISSUES: any RED dimension — results cannot be trusted

---

## Step 9: After Review

1. **If CRITICAL-ISSUES**: document in the report. Update `knowledge/ENCYCLOPEDIA.md` under
   `## What Doesn't Work` with the specific failure mode.

2. **If PUBLISH-READY**: recommend `ricet promote <path>` to move to `stable/`.
   Update `knowledge/ENCYCLOPEDIA.md` under `## What Works`.

3. **Save report** to `state/experiment-review-<target>-<date>.md`

---

## Important Rules

1. Run the code yourself — never speculate about what it does (LEGISLATION §3).
2. Read metric code line by line — don't just grep for keywords.
3. Any leakage finding = CRITICAL, full stop. Results are invalid.
4. If results look too good, suspect a bug first, not an achievement.
5. Check `state/` for prior reviews of this experiment — verify old issues are fixed.
6. Every finding needs file:line, evidence, and a specific actionable fix.
7. Traffic-light scoring follows strict rules — no subjective verdicts.
8. Never modify the code being reviewed — audit only.
9. If the experiment has no configurable seed, that alone is a CRITICAL finding.
10. At end: re-read user's request, verify all aspects addressed.

---

## Quality Checklist (verify every item before finishing)

- [ ] Analysis script was read LINE BY LINE, not just grepped
- [ ] Every claim from Step 1 was tested against at least one dimension
- [ ] Leakage check covered preprocessing, splitting, feature selection, and cross-validation
- [ ] Metric computation code was actually read and verified
- [ ] Each finding has concrete evidence (code snippet, number, file:line)
- [ ] Each finding has a specific actionable fix, not vague advice
- [ ] Report uses traffic-light scoring (RED/YELLOW/GREEN) for each dimension
- [ ] Verdict follows the scoring rules (not subjective)
- [ ] ENCYCLOPEDIA.md updated with what was learned
- [ ] At end: re-read user's request, verify all aspects addressed (LEGISLATION §1)
