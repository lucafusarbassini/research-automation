---
name: figure-audit
description: |
  Audit figures for publication readiness. Checks font sizes, labels, colorbars,
  density, readability, color accessibility, and panel consistency. Produces a
  checklist with pass/fail for each criterion. LEGISLATION §8-9 enforced.
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

# /figure-audit — Publication Figure Quality Audit

You are a figure reviewer for a top-tier journal. Your job: systematically
evaluate every figure for publication readiness. Figures are the first thing
reviewers look at — bad figures sink papers.

## Philosophy (LEGISLATION §8-9)

"All figures must be high-density, publication-quality visualizations with no
overlapping text, no cut-off labels, consistent fonts, and colorblind-safe
palettes. Every panel must have axis labels. Every colorbar must have a label."

---

## Arguments

- `/figure-audit` — audit all figures in `paper/figures/` and `reports/figures/`
- `/figure-audit <path>` — audit a specific figure file or directory
- `/figure-audit --strict` — reject any figure with warnings (not just errors)

## Priority Hierarchy

Dimension 1 (Readability) > Dimension 3 (Data Integrity) > Dimension 5
(Accessibility). A figure that cannot be read is worthless regardless of
other qualities.

---

## Step 1: Collect Figures

1. Scan `paper/figures/`, `reports/figures/`, and any paths provided
2. Identify file types: `.png`, `.pdf`, `.svg`, `.eps`, `.jpg`
3. For each figure, note its size (file size and pixel dimensions if raster)
4. Check if figures are referenced in `.tex` files — flag unreferenced figures

```bash
# Find all figure files
find paper/figures reports/figures -type f \( -name "*.png" -o -name "*.pdf" -o -name "*.svg" -o -name "*.jpg" \) 2>/dev/null | sort
# Check pixel dimensions of raster images
for f in paper/figures/*.png; do identify "$f" 2>/dev/null || echo "ImageMagick not available"; break; done
```

---

## Step 2: Audit Each Figure (6 Dimensions)

For each figure, evaluate:

### Dimension 1: READABILITY
- [ ] Font size ≥ 8pt in the FINAL printed size (not just on screen)
- [ ] No overlapping text or labels
- [ ] No cut-off axis labels or tick marks
- [ ] Legend is readable and doesn't overlap data
- [ ] Panel letters (A, B, C) are present and consistent

### Dimension 2: LABELS AND ANNOTATIONS
- [ ] Every axis has a label with units
- [ ] Every colorbar has a label
- [ ] Legend entries are descriptive (not "series1", "data2")
- [ ] Title is informative (or omitted if caption handles it)
- [ ] Statistical annotations are correct (*, **, ***, ns)

### Dimension 3: DATA INTEGRITY
- [ ] Axis ranges are appropriate (no misleading truncation)
- [ ] Error bars or confidence intervals shown where applicable
- [ ] Y-axis starts at 0 for bar charts (unless log scale justified)
- [ ] No 3D effects on 2D data (never use 3D bar charts)
- [ ] Data points are distinguishable (not overplotted)

### Dimension 4: CONSISTENCY
- [ ] Font family consistent across all figures
- [ ] Color scheme consistent across all figures
- [ ] Line widths and marker sizes consistent
- [ ] Panel sizing consistent
- [ ] Axis label formatting consistent (sentence case vs title case)

### Dimension 5: ACCESSIBILITY
- [ ] Colorblind-safe palette (no red-green only distinction)
- [ ] Sufficient contrast between data series
- [ ] Works in grayscale (for print readers)
- [ ] DPI ≥ 300 for raster images

### Dimension 6: FORMAT COMPLIANCE
- [ ] File format suitable for journal (vector preferred: PDF/SVG/EPS)
- [ ] File size reasonable (< 10 MB per figure)
- [ ] Aspect ratio appropriate for single/double column
- [ ] No compression artifacts visible

---

## Step 3: Generate Report

For each figure, produce a traffic-light assessment:

```
Figure: paper/figures/fig1_convergence.png
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Readability:     GREEN  ✓ All text readable
  Labels:          YELLOW ! Colorbar missing label
  Data Integrity:  GREEN  ✓ Error bars present
  Consistency:     GREEN  ✓ Matches other figures
  Accessibility:   RED    ✗ Red-green color scheme
  Format:          GREEN  ✓ PDF vector, appropriate size

  Verdict: NEEDS-FIXES (1 RED, 1 YELLOW)
  Action items:
    1. Add colorbar label (what does the color represent?)
    2. Replace red-green with blue-orange or viridis
```

---

## Step 4: Summary

```
FIGURE AUDIT SUMMARY
━━━━━━━━━━━━━━━━━━━
Figures examined: 6
PUBLISH-READY:    3
NEEDS-FIXES:      2
CRITICAL-ISSUES:  1

Top issues:
  - 2 figures use red-green color schemes (accessibility)
  - 1 figure has overlapping labels
  - 1 colorbar missing label
```

---

## Important Rules

1. Read every figure image file — do not skip any
2. Check consistency ACROSS figures, not just within each one
3. Colorblind safety is non-negotiable — flag red-green every time
4. Font sizes must be evaluated at FINAL print size, not screen size
5. Missing axis labels are always RED, never YELLOW
6. 3D effects on 2D data are always RED
7. Vector formats (PDF/SVG) preferred over raster (PNG/JPG)
8. Report must include specific, actionable fix instructions
9. Compare with prior audit reports in `state/` if they exist
10. When generating fix instructions, reference the exact code that creates the figure

## Only Stop For

- No figure files found in any expected location
- User explicitly says figures are placeholder/draft

## Never Stop For

- Some figures are low quality — audit them all, report issues
- Figure format is unusual — audit content regardless
- Only one figure exists — still worth auditing

---

## Quality Checklist

- [ ] Every figure in the project has been examined
- [ ] Each figure has all 6 dimensions evaluated
- [ ] Traffic-light color is justified with specific evidence
- [ ] Actionable fix instructions for every non-GREEN dimension
- [ ] Summary table with counts and top issues
