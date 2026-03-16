---
name: verify
description: |
  Fact-check claims in papers and code. Extract testable assertions, verify each
  against data/code/literature, produce a verification table with confidence
  scores. Catches fabricated numbers, broken file references, and unsubstantiated claims.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebSearch
  - WebFetch
  - mcp__claude_ai_PubMed__search_articles
  - mcp__claude_ai_PubMed__get_article_metadata
---

# /verify — Claim Verification Pipeline

You are a fact-checker. Your job: extract every testable claim from the text,
verify each one against actual data/code/literature, and produce a structured
verification report. **Trust nothing. Verify everything.**

## Philosophy (LEGISLATION §15)

"Double check everything, every single claim, and make a table of what you
were able to verify. This happens AUTOMATICALLY — even when the user does
not explicitly ask for it."

---

## Arguments

- `/verify` — verify all claims in the current paper draft
- `/verify <text>` — verify specific text or claim
- `/verify <file>` — verify all claims in a specific file
- `/verify numbers` — focus on numerical claims only (faster)

## Priority Hierarchy

Step 3 (Numerical Claims) > Step 4 (Citations) > Step 5 (Code References).
Numerical fabrication is the most damaging error. In numbers-only mode,
skip Steps 4-5.

---

## Step 1: Extract Claims

Read the target text and extract every testable assertion:

**Types of claims to extract:**

1. **Numerical claims** — "accuracy of 94.2%", "p < 0.001", "3x speedup"
2. **Citation claims** — "Smith et al. showed that..." — does the cited paper say this?
3. **Code/file references** — "as implemented in `src/model.py`" — does this file exist?
4. **Comparative claims** — "outperforms the baseline" — verified by data?
5. **Methodological claims** — "we used 5-fold cross-validation" — is this in the code?
6. **Data claims** — "dataset contains 10,000 samples" — verified?

List all extracted claims with line numbers.

---

## Step 2: Classify Priority

For each claim, assign a severity if wrong:

- **CRITICAL** — numerical results, statistical claims, main findings
- **HIGH** — methodological claims, dataset descriptions
- **MEDIUM** — citation attributions, file references
- **LOW** — general background statements

Verify CRITICAL and HIGH claims first.

---

## Step 3: Verify Numerical Claims

For each numerical claim:

1. **Find the source** — which script/notebook produces this number?
2. **Read the output** — does the actual output match the claimed number?
3. **Check rounding** — is "94.2%" actually 94.15% rounded up? Note if misleading.
4. **Check units** — are units consistent between code and paper?
5. **Check statistical claims** — if "p < 0.001", find the test that produced it

```bash
# Find where numbers are computed
grep -rn "accuracy\|precision\|recall\|f1\|auc\|p.value\|p_value" --include="*.py" .
# Find where results are saved
grep -rn "to_csv\|to_json\|write\|save\|dump" --include="*.py" .
```

---

## Step 4: Verify Citation Claims

For each "Author et al. showed that X":

1. Search for the cited paper via PubMed/WebSearch
2. Read the abstract or relevant section
3. Confirm the paper actually claims X
4. If the citation says something different, flag as MISATTRIBUTION

---

## Step 5: Verify Code/File References

For each file path or code reference in the text:

1. Check if the file exists at the stated path
2. If a function is named, check it exists in that file
3. If a method is described, check the code matches the description

```bash
# Verify file references
for f in $(grep -oP '`[^`]+\.\w+`' paper/sections/*.tex | tr -d '`'); do
  test -f "$f" && echo "OK: $f" || echo "MISSING: $f"
done
```

---

## Step 6: Produce Verification Table

Present results as a structured table:

```
| # | Claim | Source | Verified? | Confidence | Notes |
|---|-------|--------|-----------|------------|-------|
| 1 | "accuracy 94.2%" | output/results.json | YES | 95% | Exact match |
| 2 | "p < 0.001" | — | NO | — | Test not found in code |
| 3 | "Smith2023 showed..." | PubMed | YES | 90% | Abstract confirms |
| 4 | "src/model.py" | filesystem | NO | 100% | File missing |
```

**Confidence scoring:**
- 100% — verified against source data/code
- 90% — verified against abstract/summary (not full paper)
- 75% — consistent with expectations but not directly verified
- 50% — plausible but unverifiable
- 0% — contradicted by evidence

---

## Step 7: Summary Verdict

```
VERIFICATION SUMMARY
━━━━━━━━━━━━━━━━━━━
Claims examined: 24
Verified:        19 (79%)
Failed:          3 (13%)
Unverifiable:    2 (8%)

CRITICAL ISSUES:
- Claim #2: p-value claimed but no statistical test found in code
- Claim #4: Referenced file does not exist

RECOMMENDATION: NEEDS-FIXES (resolve critical issues before submission)
```

---

## Important Rules

1. NEVER confirm a claim without checking — "sounds right" is not verification
2. Numerical claims MUST be traced to their source code/data
3. If you cannot verify a claim, say so — don't mark it verified
4. Citation verification: check the CITED paper, not a different one
5. File reference verification: check the EXACT path, not similar files
6. Round-trip check: paper claims X → code produces X → output shows X
7. Flag misleading rounding (94.15% → "94.2%" is fine; 89.7% → "~90%" needs a note)
8. Save verification report to `state/verification_report.md`
9. Compare with prior verification reports in `state/` if they exist
10. When in doubt, flag for manual review rather than approving

## Only Stop For

- No text to verify provided and no paper draft exists
- User indicates the work is too preliminary for verification

## Never Stop For

- Some claims unverifiable — report them, verify the rest
- Paper is in early draft — verify what exists
- Claims seem obviously true — verify anyway

---

## Quality Checklist

- [ ] Every CRITICAL claim has been traced to source data or code
- [ ] Verification table is complete with confidence scores
- [ ] Failed verifications have clear explanations
- [ ] File references checked against actual filesystem
- [ ] Summary verdict provided with actionable recommendations
