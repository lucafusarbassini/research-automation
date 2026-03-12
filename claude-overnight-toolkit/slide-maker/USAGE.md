# Slide Maker Toolkit

Generates polished presentation decks from a codebase or website using Claude +
Nano Banana Pro (Google Gemini 3 Pro) for full-slide schematic diagrams.

## How It Works

```
  Your Project                   Claude Agent                    Output
  ───────────                    ───────────                     ──────
  codebase/ OR website    →    reads slideprompt.md        →    make_slides.py
  slides_task.md          →    analyzes project content     →    slides_output/
                               designs narrative                  ├── schematic_01.png
                               engineers schematic prompts        ├── schematic_02.png
                               writes make_slides.py              ├── schematic_03.png
                                        │                         ├── schematic_04.png
                                        ▼                         └── presentation.pptx
                               python make_slides.py
                               (calls Nano Banana Pro API
                                for N=4 schematics, builds
                                full .pptx deck)
```

## What's Included

| File | Purpose |
|------|---------|
| `slide_utils.py` | Python module: pptx helpers + Nano Banana Pro API integration |
| `slideprompt.md` | Agent instructions: how to analyze a project and build slides |
| `slides_task.md` | Template: you fill in what to present and to whom |
| `make_slides_example.py` | Working example showing the pattern |
| `requirements.txt` | Python dependencies |
| `setup-slides.sh` | One-command setup for a new project |

## Quick Start

### 1. Install dependencies

```bash
pip install python-pptx google-genai Pillow
```

### 2. Set your Google API key

```bash
export GOOGLE_API_KEY=your-gemini-api-key
```

### 3. Copy into your project

```bash
./setup-slides.sh /path/to/your/project
```

### 4. Edit `slides_task.md`

Tell the agent what to present:

```markdown
**Codebase path**: /home/me/my-project

**Audience**: Technical peers at a lab meeting
**Duration**: 15 minutes
**Key message**: Our pipeline achieves 95% accuracy with zero manual annotation

## Schematics (N=4)
1. High-level system architecture
2. Data pipeline from raw input to predictions
3. Results comparison with baselines
4. Model architecture detail
```

### 5. Run the agent

```bash
cd /path/to/your/project/slides
claude -p "$(cat slideprompt.md)"
```

The agent will:
1. Read `slides_task.md` to understand the task
2. Analyze your codebase (or fetch the website)
3. Design a 15-25 slide narrative
4. Engineer 4 detailed prompts for Nano Banana Pro schematics
5. Write `make_slides.py` with all content

### 6. Generate the deck

```bash
python make_slides.py
```

This calls Nano Banana Pro for schematics and builds the `.pptx`.

### 7. Open `slides_output/presentation.pptx`

## Nano Banana Pro Integration

The toolkit uses **Nano Banana Pro** (`gemini-3-pro-image-preview`) — Google's
latest image generation model — to create schematic diagrams.

### Why Nano Banana Pro?
- Excellent at technical diagrams and schematics
- 16:9 aspect ratio matches slides perfectly
- 2K/4K resolution for crisp presentations
- Thinking mode produces better compositional layouts
- ~$0.02-0.12 per image

### Schematic Design
- Images are **full-slide** — the schematic IS the slide, not a decoration
- `slide_utils.generate_schematic()` automatically wraps prompts with style
  instructions (dark background, teal/blue/gold palette, flat technical style)
- You (or the agent) provide the CONTENT prompt; styling is handled
- Default N=4 schematics. Change by setting the number in `slides_task.md`

### Prompt Engineering Tips
The agent is instructed to write sophisticated prompts, but if you want to
customize, good schematic prompts include:

1. **What it shows** (architecture, pipeline, comparison, model)
2. **Layout direction** (left-to-right flow, top-down hierarchy, radial)
3. **Specific elements** (named boxes, labeled arrows, layers)
4. **Abstraction level** (high-level overview vs detailed component)

## Slide Templates Available

`slide_utils.py` provides these ready-made slide types:

| Function | Description |
|----------|-------------|
| `add_title_slide()` | Dark title with accent bar, subtitle, author |
| `add_section_slide()` | Section divider with number and title |
| `add_content_slide()` | Title + bullet points (dark or light) |
| `add_two_column_slide()` | Side-by-side comparison |
| `add_key_metrics_slide()` | Big numbers in a row |
| `add_image_slide()` | Full-slide image (for schematics) |
| `add_closing_slide()` | Thank-you slide |

All slides use a consistent dark theme with teal/blue/gold accents.

## Customization

### Change the number of schematics
Edit `slides_task.md` and change the Schematics section. Also tell the agent
in the task description: "Generate 6 schematics instead of 4."

### Change the color palette
Edit `PALETTE` in `slide_utils.py`. All slides reference the palette.

### Change slide dimensions
Edit `SLIDE_WIDTH` and `SLIDE_HEIGHT` in `slide_utils.py`. Default is 16:9
widescreen (13.333" x 7.5").

### Run without schematics (no API key)
The example script gracefully handles missing API keys — it skips image
slides. Useful for testing the deck structure before burning API credits.

## Integration with Overnight Toolkit

You can combine this with the overnight sandbox:

```bash
# In slides_task.md, point to the workspace codebase
**Codebase path**: /workspace

# Run via the sandbox
docker exec -it my-sandbox gosu agent bash -c '
  cd /workspace/slides
  claude --dangerously-skip-permissions -p "$(cat slideprompt.md)"
  python make_slides.py
'

# Extract the deck
docker cp my-sandbox:/workspace/slides/slides_output/presentation.pptx .
```
