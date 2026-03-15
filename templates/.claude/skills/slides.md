---
name: slides
description: |
  Generate a polished presentation (.pptx) from a codebase or website.
  Produces a narrative-driven slide deck with AI-generated schematic diagrams.
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - WebFetch
---

# /slides — Presentation Generator

You are a presentation architect. Analyze the project and produce a polished, narrative-driven
slide deck as a `.pptx` file using the `slide_utils.py` module, with AI-generated schematic
diagrams as full-slide visuals.

## Arguments

- `/slides` — auto-detect from project (reads `slides/slides_task.md` or `knowledge/GOAL.md`)
- `/slides <path>` — analyze a specific codebase directory
- `/slides <url>` — analyze a website

## Priority Hierarchy

Step 2 (Narrative) > Step 3 (Schematics) > Step 5 (Run & Verify). Never skip narrative
design — a bad narrative with polished slides is still a bad talk. If time is limited,
reduce to 10-15 slides but keep all 4 schematics.

---

## Step 1: Gather Context

Read ALL of these (skip any that don't exist):

```
knowledge/GOAL.md              # Research objectives
state/PROGRESS.md              # Current progress
paper/main.tex                 # Paper content (if writing up)
slides/slides_task.md          # Explicit presentation brief (if provided)
README.md                      # Project overview
```

If a codebase path was given, also read key source files, configs, and docs.
If a URL was given, fetch and extract content.

**Identify these five things before proceeding:**
1. The core problem/need
2. The approach/solution
3. Key results/value
4. Technical architecture
5. What makes it interesting/novel

---

## Step 2: Narrative Design

Design a 15-25 slide deck following this structure:

```
TITLE SLIDE (1)
  - Project name, one-line value proposition, author/date

CONTEXT / PROBLEM (2-3 slides)
  - What problem exists? Why does it matter? Who cares?
  - [SCHEMATIC 1: Problem landscape / domain overview]

APPROACH / METHOD (3-5 slides)
  - How does this work? What's the key insight?
  - Architecture / pipeline / data flow
  - [SCHEMATIC 2: System architecture or pipeline diagram]

KEY RESULTS / VALUE (2-4 slides)
  - What was achieved? Metrics, comparisons, demos
  - Key metrics slide (big numbers, nothing else)
  - [SCHEMATIC 3: Results visualization or comparison diagram]

TECHNICAL DEPTH (2-4 slides)
  - Deeper dive into the most interesting technical aspect
  - Two-column comparisons (before/after, baseline/method, etc.)
  - [SCHEMATIC 4: Technical detail — model architecture, data flow, etc.]

LIMITATIONS & FUTURE (1-2 slides)
  - Honest about what doesn't work yet
  - What's next

CLOSING (1 slide)
  - Summary, call to action, contact
```

---

## Step 3: Schematic Prompt Engineering

For each of the 4 schematics, write a SOPHISTICATED prompt (3-6 sentences):

- **Subject**: What the diagram shows
- **Visual structure**: Layout direction (left-to-right, top-down, radial)
- **Key elements**: Named boxes, arrows, layers — be SPECIFIC
- **Abstraction level**: High-level overview vs detailed component view
- **Style cue**: "clean technical schematic", "system architecture diagram"

**GOOD prompt example:**
> "A system architecture diagram showing a 3-stage data pipeline flowing left to right.
> Stage 1 'Ingest' shows multiple data source icons (database, API, file) feeding into
> a central queue. Stage 2 'Process' shows parallel worker nodes with a shared model
> component. Stage 3 'Output' branches into a dashboard, an API endpoint, and a storage
> layer. Use labeled arrows between stages. Clean flat design, dark background."

**BAD prompt example:**
> "Architecture diagram" (too vague — will produce garbage)

---

## Step 4: Generate Script

Write `slides/make_slides.py`:

```python
#!/usr/bin/env python3
"""Auto-generated slide deck for [PROJECT NAME]."""
from pathlib import Path
from slide_utils import *

OUTPUT_DIR = Path('slides_output')
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Schematics ──────────────────────────────────────────
schematics = [
    ("detailed prompt 1...", OUTPUT_DIR / "schematic_01_overview.png"),
    ("detailed prompt 2...", OUTPUT_DIR / "schematic_02_architecture.png"),
    ("detailed prompt 3...", OUTPUT_DIR / "schematic_03_results.png"),
    ("detailed prompt 4...", OUTPUT_DIR / "schematic_04_technical.png"),
]

print("Generating schematics...")
generate_schematics_batch(schematics)

# ── Build Deck ──────────────────────────────────────────
prs = create_presentation()
add_title_slide(prs, "Title", "Subtitle", "Author")
# ... all slides ...
add_closing_slide(prs, "Thank You")

prs.save(str(OUTPUT_DIR / 'presentation.pptx'))
print(f"Saved: {OUTPUT_DIR / 'presentation.pptx'}")
```

---

## Step 5: Run and Verify

```bash
cd slides && python make_slides.py
```

If the script fails, fix and retry. Do not present a broken script.

---

## Slide Design Rules

1. **One idea per slide.** If you need "and", it's two slides.
2. **5 words or fewer per bullet.** Slides are visual aids, not documents.
3. **Every 3-4 slides, break with a schematic.** The schematics ARE the presentation.
4. **Section dividers** between major sections. Breathing room.
5. **Key metrics get their own slide.** Big numbers, no clutter.
6. **Dark theme throughout.** Professional, high-contrast.
7. **Consistent visual language.** Teal = primary, blue = secondary, gold = highlight.

## Important Rules

1. One idea per slide — if you need "and", it's two slides.
2. 5 words or fewer per bullet. Slides are visual aids, not documents.
3. Schematics ARE the presentation — invest in their prompts (3+ sentences each).
4. Check `slides/` for existing presentations before creating new ones.
5. Script must run end-to-end without errors before presenting to user.
6. Every 3-4 slides, break with a schematic for visual breathing room.
7. Dark theme, consistent colors (teal primary, blue secondary, gold highlight).
8. Key metrics get their own slide — big numbers, nothing else.
9. At end: re-read user's request, verify all aspects addressed.

---

## Quality Checklist (verify before finishing)

- [ ] Narrative flows: problem → approach → results → depth → future
- [ ] Exactly 4 schematics generated and inserted as full-slide images
- [ ] Every schematic prompt is 3+ sentences with specific visual structure
- [ ] No slide has more than 6 bullet points
- [ ] No bullet point is longer than ~10 words
- [ ] Section dividers separate major sections
- [ ] Key metrics have their own slide with big numbers
- [ ] Title slide has project name, value proposition, author
- [ ] Closing slide exists
- [ ] Script runs end-to-end with `python make_slides.py`
- [ ] Output path printed: `slides/slides_output/presentation.pptx`
