---
name: reproduce
description: Re-run analysis with different seeds/splits and compare results
---

# Reproduce

You are now in **experimenter mode**. Your job is to test whether results are reproducible by re-running the analysis with variations.

## Workflow

1. **Identify what to reproduce** — Ask the user, or look at the most recent experiment in `lab/` or `outputs/`.

2. **Understand the pipeline** — Read the code end-to-end:
   - Data loading → preprocessing → model/analysis → evaluation → output
   - Identify all sources of randomness (seeds, shuffling, initialization, dropout)

3. **Design reproduction matrix**:
   | Variation | Why |
   |-----------|-----|
   | 3 different random seeds | Test initialization sensitivity |
   | Different train/test split | Test data sensitivity |
   | Subsample (80% of data) | Test sample size sensitivity |
   | Remove one feature/variable | Test feature importance |

4. **Execute** — Run each variation:
   - Log the configuration for each run
   - Capture the key metrics (same ones as original)
   - Save outputs to `lab/reproduce_<timestamp>/`

5. **Compare** — Build a comparison table:
   ```
   | Variation      | Metric_1 | Metric_2 | Status |
   |----------------|----------|----------|--------|
   | Original       | 0.92     | 0.85     | -      |
   | Seed 42        | 0.91     | 0.84     | OK     |
   | Seed 123       | 0.90     | 0.83     | OK     |
   | Different split| 0.78     | 0.72     | WARN   |
   ```

6. **Verdict**:
   - **Reproducible**: <2% variation across seeds, <5% across splits
   - **Fragile**: >5% variation — investigate why
   - **Not reproducible**: Results depend heavily on specific random state

7. **Record** — Update `knowledge/ENCYCLOPEDIA.md` with findings. If reproducible, this is a candidate for `ricet promote` to `stable/`.
