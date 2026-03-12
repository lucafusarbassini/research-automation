#!/usr/bin/env python3
"""
Example: Auto-generated slide deck.

This shows the pattern the agent should follow. The agent writes a REAL version
of this file with project-specific content after analyzing the codebase/website.

Usage:
    export GOOGLE_API_KEY=your-key-here
    python make_slides_example.py
"""
from pathlib import Path
from slide_utils import *

OUTPUT_DIR = Path('slides_output')
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Step 1: Generate schematics with Nano Banana Pro ────────────

schematics = [
    (
        "A high-level system architecture diagram showing three layers stacked vertically. "
        "Top layer labeled 'Frontend' contains web and mobile client icons connected to an "
        "API Gateway. Middle layer labeled 'Services' shows four microservice boxes "
        "(Auth, Data, ML, Notification) interconnected with arrows. Bottom layer labeled "
        "'Infrastructure' shows a database cluster, message queue, and object storage. "
        "Clean technical schematic with labeled arrows showing request flow.",
        OUTPUT_DIR / "schematic_01_architecture.png"
    ),
    (
        "A data processing pipeline flowing left to right through four stages. "
        "Stage 1 'Collect': multiple data source icons (sensor, API, file upload) converge "
        "into a central ingestion queue. Stage 2 'Transform': parallel processing nodes "
        "with a shared configuration store above them. Stage 3 'Analyze': ML model box "
        "receiving features and outputting predictions, with a feedback loop arrow. "
        "Stage 4 'Serve': branches into dashboard, API, and alert system. "
        "Each stage separated by a vertical dotted line. Data flow arrows labeled with formats.",
        OUTPUT_DIR / "schematic_02_pipeline.png"
    ),
    (
        "A comparison infographic showing two approaches side by side. Left side labeled "
        "'Traditional Approach' shows a linear chain of manual steps with clock icons "
        "indicating slow processing (crossed out with red). Right side labeled 'Our Approach' "
        "shows a streamlined automated pipeline with checkmark icons indicating success. "
        "Bottom section shows a horizontal bar chart comparing: latency, accuracy, and cost "
        "between the two approaches, with our approach clearly winning on all metrics.",
        OUTPUT_DIR / "schematic_03_comparison.png"
    ),
    (
        "A neural network architecture diagram showing the model's internal structure. "
        "Left: input layer with labeled feature groups (spectral, spatial, temporal). "
        "Middle: encoder tower with residual connections, attention mechanism highlighted "
        "in a separate zoom-in box. An embedding bottleneck layer in the center with "
        "dimension label. Right: decoder splitting into two heads — classification head "
        "and regression head, each with their loss function labeled. "
        "Skip connections shown as curved arrows. Layer dimensions annotated.",
        OUTPUT_DIR / "schematic_04_model.png"
    ),
]

print("Generating schematics with Nano Banana Pro...")
print("(This requires GOOGLE_API_KEY to be set)")

try:
    generate_schematics_batch(schematics)
    has_schematics = True
except Exception as e:
    print(f"Schematic generation failed: {e}")
    print("Building deck without schematics (image slides will be skipped).")
    has_schematics = False


# ── Step 2: Build the slide deck ────────────────────────────────

prs = create_presentation()

# --- Title ---
add_title_slide(
    prs,
    title="Project Alpha",
    subtitle="Automated Intelligence for Real-Time Decision Systems",
    author="Research Team  |  February 2026"
)

# --- Section 1: Problem ---
add_section_slide(prs, 1, "The Problem", "Why current approaches fall short")

add_content_slide(prs, "Current State of Affairs", [
    "Manual processing takes 4+ hours per cycle",
    "Error rates exceed 15% on complex inputs",
    "No real-time capability — batch-only",
    "Scaling requires linear headcount growth",
])

if has_schematics:
    add_image_slide(prs, OUTPUT_DIR / "schematic_01_architecture.png",
                    title="System Architecture Overview")

# --- Section 2: Approach ---
add_section_slide(prs, 2, "Our Approach", "End-to-end automated pipeline")

add_content_slide(prs, "Key Insight", [
    "Treat each input as a structured bag-of-features",
    "Learn hierarchical representations automatically",
    "Multi-task training captures related signals",
    "Curriculum learning for stable convergence",
])

if has_schematics:
    add_image_slide(prs, OUTPUT_DIR / "schematic_02_pipeline.png",
                    title="Processing Pipeline")

add_two_column_slide(
    prs,
    title="Design Decisions",
    left_title="What We Use",
    left_bullets=[
        "Transformer encoder backbone",
        "Prototype-based classification",
        "Cosine annealing schedule",
        "Embryo-level train/test split",
    ],
    right_title="What We Avoid",
    right_bullets=[
        "No spatial context (isolation principle)",
        "No cell shape features (confounder)",
        "No cross-sample leakage",
        "No hand-engineered features",
    ],
)

# --- Section 3: Results ---
add_section_slide(prs, 3, "Results", "Quantitative evaluation")

add_key_metrics_slide(prs, "Key Results", [
    ("95.2%", "Leaf Accuracy"),
    ("167x", "vs Random Baseline"),
    ("0.82", "Spearman Correlation"),
    ("< 1s", "Inference Time"),
])

if has_schematics:
    add_image_slide(prs, OUTPUT_DIR / "schematic_03_comparison.png",
                    title="Comparison with Baselines")

add_content_slide(prs, "Negative Controls Confirm Signal", [
    "Radius-only model: 0.2% (at random)",
    "Shuffled spectra: 0.3% (at random)",
    "Shuffled labels: 0.2% (at random)",
    "Full model: 95.2% — signal is genuine",
])

# --- Section 4: Technical Depth ---
add_section_slide(prs, 4, "Technical Depth", "Model architecture and training")

if has_schematics:
    add_image_slide(prs, OUTPUT_DIR / "schematic_04_model.png",
                    title="Model Architecture")

add_content_slide(prs, "Training Protocol", [
    "Curriculum: hierarchy loss first, leaf loss later",
    "Multi-task: leaf + 5 ancestor heads + depth regression",
    "Cosine annealing over 100 epochs",
    "Best model selected by validation accuracy",
    "Cross-embryo split — no data leakage",
])

# --- Closing ---
add_section_slide(prs, 5, "Future Work", "What's next")

add_content_slide(prs, "Limitations & Next Steps", [
    "Simulation-only — real data validation needed",
    "Poincare geometry shows promise but needs tuning",
    "Scaling to larger trees (1000+ nodes)",
    "Transfer learning across organisms",
])

add_closing_slide(
    prs,
    title="Thank You",
    message="Questions?",
    contact="team@example.com  |  github.com/project-alpha"
)

# ── Save ────────────────────────────────────────────────────────

output_path = OUTPUT_DIR / 'presentation.pptx'
prs.save(str(output_path))
print(f"\nDone! Saved: {output_path}")
print(f"Schematics: {OUTPUT_DIR}/*.png")
print(f"Slides: {sum(1 for _ in prs.slides)} total")
