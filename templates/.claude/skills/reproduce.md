---
name: reproduce
description: |
  Reproducibility stress-test — re-run analysis with different seeds, splits,
  and subsets. Produces a stability matrix and verdict (Reproducible/Fragile/Broken).
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# /reproduce — Reproducibility Stress Test

You are the reproducibility auditor. Your job is to determine whether results survive
variation in random state, data splits, and sample size. A result that depends on a
specific seed is not a result — it's an accident.

## Non-Negotiable Rules (from LEGISLATION.md)

These are HARD CONSTRAINTS:

1. **Set random seeds for all sources of randomness.** Every run must be fully deterministic
   given its seed. (PHILOSOPHY §10: "Reproducibility is non-negotiable.")

2. **Run the code yourself** — do not speculate about what would happen.
   (LEGISLATION §3: "Run the code yourself until you reach a final diagnosis.")

3. **Report only actual data, no guesses or inferences.** (LEGISLATION §6.3)

4. **Before scaling up, run a small end-to-end smoke test.** (LEGISLATION §3)

5. **Log all parameters.** Every run's configuration must be recorded.
   (PHILOSOPHY §10: "Pin all dependencies. Set random seeds. Log all parameters.")

6. **Each variant should output to its own folder.** (LEGISLATION §5: "Never overwrite
   existing outputs.")

---

## Arguments

- `/reproduce` — reproduce the most recent experiment (auto-detect from lab/)
- `/reproduce <path>` — reproduce a specific script
- `/reproduce quick` — 3 seeds only (fast check)
- `/reproduce deep` — 5 seeds + data sensitivity + feature ablation

## Priority Hierarchy

Step 3A (Smoke test) > Step 5 (Analyze) > Step 6 (Verdict). Never skip the smoke test —
if the original doesn't reproduce exactly, everything else is meaningless. If context is
limited, run only seed variation (skip split and subsample) but always produce the verdict.

---

## Step 1: Identify and Understand

1. Read `knowledge/GOAL.md` — context for what matters.
2. Check `state/` for prior reproduction reports on this target — compare with previous findings.
3. Find the target:
   - If path given: use that
   - If not: find the most recently modified `.py` file in `lab/`
3. **Read the entire script end-to-end.** Understand:
   - Data loading → preprocessing → model/analysis → evaluation → output
   - Every source of randomness (seeds, shuffling, initialization, dropout, sampling)
   - The key metrics being reported
   - The baseline/reference numbers to compare against

4. **Record the original results** as the reference point.
   ```
   Original run:
     Seed: <original>
     Metric 1: <value>
     Metric 2: <value>
     ...
   ```

**STOP if the script doesn't have a configurable seed. Flag this as a CRITICAL issue —
the experiment is not reproducible by construction.**

---

## Step 2: Design Reproduction Matrix

### Standard mode (default)
| Variation | Seeds/Configs | Purpose |
|-----------|---------------|---------|
| Seed variation | 42, 123, 7, 2024, 31415 | Initialization sensitivity |
| Different split | 3 random split seeds | Data partition sensitivity |
| 90% subsample | 3 runs with random 90% | Sample size sensitivity |

### Quick mode
| Variation | Seeds/Configs | Purpose |
|-----------|---------------|---------|
| Seed variation | 42, 123, 7 | Basic stability check |

### Deep mode
All of Standard, plus:
| Variation | Seeds/Configs | Purpose |
|-----------|---------------|---------|
| 80% subsample | 3 runs | Stronger size sensitivity |
| Feature ablation | Remove each top-5 feature | Feature dependence |
| Different optimizer/init | 2 alternatives | Architecture sensitivity |

---

## Step 3: Prepare the Runs

### 3A. Smoke test first

Before running the full matrix:
1. Verify the script runs end-to-end with the original seed
2. Verify it produces the same numbers as the original (exact reproduction)
3. If it doesn't match → STOP. The experiment is already not reproducible.

(LEGISLATION §3: "Before scaling up, run a small end-to-end smoke test.")

### 3B. Create output directory

```bash
mkdir -p lab/reproduce_$(date +%Y%m%d_%H%M%S)
```

### 3C. Modify script for parameterized runs

If the script doesn't accept seed as argument, create a wrapper:

```python
# Do NOT modify the original script — create a wrapper
# reproduce_wrapper.py
import sys
import subprocess

seeds = [42, 123, 7, 2024, 31415]
for seed in seeds:
    print(f"\n{'='*60}")
    print(f"Running with seed={seed}")
    print(f"{'='*60}")
    subprocess.run([sys.executable, "original_script.py", "--seed", str(seed)],
                   check=True)
```

**Rules for modification:**
- NEVER modify the original script. Duplicate or wrap.
  (LEGISLATION §4.2: "When reusing an evaluation script, duplicate it rather than
  modifying the original.")
- Each run outputs to `lab/reproduce_<timestamp>/seed_<N>/`
  (LEGISLATION §5: "Each variant should output to its own folder.")
- Log the full configuration for each run
- If one run fails, others must continue
  (LEGISLATION §4.3: "Handle missing or optional components gracefully.")

---

## Step 4: Execute

Run each variation. For each run, capture:

1. **Configuration**: seed, split, subsample fraction, any modified parameters
2. **All key metrics**: same metrics as the original, exact values
3. **Runtime**: wall-clock time
4. **Convergence**: final loss value, number of epochs/iterations
5. **Any warnings or errors**

```bash
# Example: run and capture output
python reproduce_wrapper.py 2>&1 | tee lab/reproduce_<timestamp>/log.txt
```

**Monitor actively.** If a run is clearly failing or stuck, don't wait — investigate.
(LEGISLATION §7.3: "If something seems stuck or slow, identify the bottleneck.")

---

## Step 5: Analyze and Compare

### 5A. Build the stability matrix

```markdown
| Variation | Config | Metric_1 | Metric_2 | Δ from Original |
|-----------|--------|----------|----------|-----------------|
| Original  | seed=42 | 0.920 | 0.850 | — |
| Seed | seed=123 | 0.915 | 0.843 | -0.5% / -0.8% |
| Seed | seed=7 | 0.908 | 0.838 | -1.3% / -1.4% |
| Seed | seed=2024 | 0.921 | 0.852 | +0.1% / +0.2% |
| Seed | seed=31415 | 0.912 | 0.841 | -0.9% / -1.1% |
| Split | split_seed=1 | 0.895 | 0.823 | -2.7% / -3.2% |
| Split | split_seed=2 | 0.903 | 0.831 | -1.8% / -2.2% |
| Split | split_seed=3 | 0.911 | 0.842 | -1.0% / -0.9% |
| Subsample | 90%, run 1 | 0.907 | 0.835 | -1.4% / -1.8% |
| Subsample | 90%, run 2 | 0.899 | 0.828 | -2.3% / -2.6% |
| Subsample | 90%, run 3 | 0.910 | 0.839 | -1.1% / -1.3% |
```

### 5B. Compute statistics

For each variation type:
- Mean ± std across runs
- Coefficient of variation (CV = std/mean)
- Min and max
- Range (max - min)

### 5C. Check for outliers

If any single run deviates >10% from the mean, investigate:
- Is there a data-dependent failure mode?
- Does a specific seed trigger an edge case?
- Is training not converging for some initializations?

---

## Step 6: Verdict

### Scoring criteria

| Category | Seed CV | Split Δ | Subsample Δ |
|----------|---------|---------|-------------|
| **REPRODUCIBLE** | < 2% | < 5% | < 5% |
| **FRAGILE** | 2-5% | 5-10% | 5-10% |
| **NOT REPRODUCIBLE** | > 5% | > 10% | > 10% |

**Overall verdict = worst category across all variation types.**

- **REPRODUCIBLE**: Results are stable. Recommend `ricet promote` to `stable/`.
- **FRAGILE**: Results depend on specific conditions. Investigate which variation
  causes instability. Report mean ± std instead of single-run numbers.
- **NOT REPRODUCIBLE**: Results are unreliable. Do NOT trust or publish single-run numbers.
  Must fix the underlying instability before proceeding.

---

## Step 7: Generate Report

Save report to `state/reproduce-<target>-<date>.md` AND save JSON snapshot to
`state/retros/reproduce-<target>-<date>.json` for trend tracking:

```json
{
  "date": "<today>",
  "target": "<script>",
  "mode": "QUICK/STANDARD/DEEP",
  "original_metric": 0.920,
  "seed_cv": 0.012,
  "split_delta_max": 0.032,
  "subsample_delta_max": 0.026,
  "verdict": "REPRODUCIBLE/FRAGILE/NOT_REPRODUCIBLE",
  "runs": 11,
  "failures": 0
}
```

Report format — save to `state/reproduce-<target>-<date>.md`:

```markdown
## Reproducibility Report

**Target**: <script path>
**Date**: <today>
**Mode**: QUICK / STANDARD / DEEP
**Original result**: <metric = value>

### Stability Matrix
<table from Step 5A>

### Statistics
| Variation Type | Mean | Std | CV | Min | Max |
|----------------|------|-----|-----|-----|-----|
| Seed | ... | ... | ...% | ... | ... |
| Split | ... | ... | ...% | ... | ... |
| Subsample | ... | ... | ...% | ... | ... |

### Issues Found
1. <any anomalies, outliers, failures>

### Verdict
**<REPRODUCIBLE / FRAGILE / NOT REPRODUCIBLE>**
<one paragraph: what is stable, what is fragile, recommended actions>

### Recommended Reporting
If publishing, report: <metric> = <mean> ± <std> (N=<runs>, seeds: <list>)
```

---

## Step 8: After Reproduction

1. **If REPRODUCIBLE**: update `knowledge/ENCYCLOPEDIA.md` under `## What Works` with
   the stability evidence. Recommend promotion to `stable/`.

2. **If FRAGILE**: document which variation causes instability. Suggest fixes:
   - Ensemble across seeds
   - Larger training set
   - More robust architecture/algorithm
   - Report mean ± std, not single run

3. **If NOT REPRODUCIBLE**: document in `knowledge/ENCYCLOPEDIA.md` under
   `## What Doesn't Work`. Do NOT promote. Investigate root cause.

4. Update `state/TODO.md` if follow-up work is needed.

---

## Important Rules

1. Smoke test first — if original doesn't reproduce exactly, STOP.
2. Never modify the original script — duplicate or wrap (LEGISLATION §4.2).
3. Each run gets its own output directory (LEGISLATION §5).
4. Log the full configuration for every run — seeds, parameters, environment.
5. Report mean ± std, not single-run numbers.
6. Check `state/` for prior reproduction reports — compare with previous findings.
7. Verdict follows the scoring table strictly — no subjective judgment.
8. If any run crashes, investigate the cause — don't just skip it.
9. Save JSON snapshot for trend tracking across multiple reproduce runs.
10. At end: re-read user's request, verify all aspects addressed.

---

## Quality Checklist (verify every item before finishing)

- [ ] Original result exactly reproduced first (smoke test passed)
- [ ] All seeds/variations actually ran (no silently skipped runs)
- [ ] Each run's output saved to its own directory
- [ ] Full configuration logged for every run
- [ ] Statistics computed correctly (mean, std, CV, range)
- [ ] Verdict follows the scoring criteria table (not subjective)
- [ ] Report includes recommended reporting format (mean ± std)
- [ ] Any outlier runs investigated and explained
- [ ] ENCYCLOPEDIA.md updated with stability findings
- [ ] Original script NOT modified (wrapper used instead)
- [ ] At end: re-read user's request, verify all aspects addressed (LEGISLATION §1)
