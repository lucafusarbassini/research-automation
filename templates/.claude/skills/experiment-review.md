---
name: experiment-review
description: Audit experiment results for statistical issues, leakage, and reproducibility
---

# Experiment Review

You are now in **analyst + falsifier mode**. Your job is to rigorously audit experiment results before they are trusted or published.

## Workflow

1. **Identify the experiment** — Ask the user which results to review, or look at the most recent outputs in `outputs/`, `figures/`, or `lab/`.

2. **Check data integrity**:
   - Is there train/test leakage? (same samples in both sets, temporal leakage, feature leakage)
   - Are splits reproducible? (fixed random seeds, stratification)
   - Is the dataset balanced? If not, are metrics appropriate (F1, AUROC vs accuracy)?
   - Missing data handling: imputation method, percentage missing

3. **Check statistical validity**:
   - Sample size: is it adequate for the claims?
   - Multiple comparisons: are p-values corrected (Bonferroni, FDR)?
   - Effect sizes: are they reported alongside significance?
   - Confidence intervals or standard errors across runs
   - Is the variance across random seeds reported?

4. **Check code correctness**:
   - Read the analysis code. Look for off-by-one errors, wrong axis operations, transposed matrices.
   - Verify that the metric computation matches the metric name (e.g., "accuracy" is not actually F1)
   - Check that preprocessing is identical for train and test

5. **Check reproducibility**:
   - Are random seeds set?
   - Are package versions pinned?
   - Can the analysis be re-run from raw data to final figure?

6. **Report** — Write a structured review:
   - **CRITICAL**: Issues that invalidate results
   - **WARNING**: Issues that weaken confidence
   - **SUGGESTION**: Improvements for robustness
   - For each issue: what's wrong, where in the code, how to fix it

7. **Update records** — If issues are found, note them in `knowledge/ENCYCLOPEDIA.md` under "What Doesn't Work" to prevent repetition.
