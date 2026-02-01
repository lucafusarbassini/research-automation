# Tutorial 4: Paper Writing

This tutorial covers the complete paper pipeline: working with the LaTeX
template, managing citations, generating publication-quality figures, running
style analysis, and compiling your manuscript.

**Time:** ~30 minutes

**Prerequisites:**
- A project created with `research init` ([Tutorial 3](first-project.md))
- LaTeX installed (included in the Docker image; on host, install `texlive-full`)

---

## Table of Contents

1. [The Paper Directory Structure](#1-the-paper-directory-structure)
2. [Editing the LaTeX Template](#2-editing-the-latex-template)
3. [Managing Citations](#3-managing-citations)
4. [Generating Figures](#4-generating-figures)
5. [Compiling the Paper](#5-compiling-the-paper)
6. [Style Analysis and Transfer](#6-style-analysis-and-transfer)
7. [Plagiarism Checking](#7-plagiarism-checking)
8. [Full Workflow Example](#8-full-workflow-example)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. The Paper Directory Structure

Every project created with `research init` includes a `paper/` directory:

```
paper/
├── main.tex           # Main LaTeX source file
├── references.bib     # BibTeX bibliography
└── Makefile           # Build automation (make all, make clean, make watch)

figures/               # Generated figures (separate from paper/)
```

The template uses standard academic packages: `amsmath`, `graphicx`, `hyperref`,
`natbib`, `booktabs`, and `microtype`.

---

## 2. Editing the LaTeX Template

Open `paper/main.tex` in your editor. The template provides the standard
structure:

```latex
\documentclass[11pt,a4paper]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue]{hyperref}
\usepackage{natbib}
\usepackage{booktabs}
\usepackage{microtype}

\title{[Title]}
\author{[Authors]}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
[Abstract goes here - 150-250 words]
\end{abstract}

\section{Introduction}
\label{sec:intro}

\section{Methods}
\label{sec:methods}

\section{Results}
\label{sec:results}

\section{Discussion}
\label{sec:discussion}

\section{Conclusion}
\label{sec:conclusion}

\bibliographystyle{plainnat}
\bibliography{references}

\end{document}
```

### Using Claude to write sections

During an interactive session, you can ask Claude to draft sections:

```
You: Write a first draft of the Methods section. We used a 3-layer CNN with
     batch normalization, trained on 50,000 samples with Adam optimizer
     (lr=0.001). Use the paper-writing skill for style guidelines.
```

Claude reads `.claude/skills/paper-writing.md` for style rules:

- Active voice preferred
- Past tense for methods and results
- Present tense for established facts
- One idea per paragraph
- First sentence of each paragraph is the topic sentence

### Adapting for conference formats

To switch to a conference format (e.g., NeurIPS, ICML), replace the
`\documentclass` line and add the conference style file:

```latex
% Example: NeurIPS format
\documentclass{article}
\usepackage{neurips_2026}
```

Place the style file (`neurips_2026.sty`) in the `paper/` directory.

---

## 3. Managing Citations

### Add a citation from the command line

Citations are managed through `core/paper.py`. You can add them programmatically
or ask Claude to do it:

```
You: Add a citation for "Attention Is All You Need" by Vaswani et al., 2017,
     published in NeurIPS.
```

Claude will call `add_citation()` which appends to `paper/references.bib`:

```bibtex
@article{Vaswani2017,
  author = {Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and Uszkoreit, Jakob and Jones, Llion and Gomez, Aidan N. and Kaiser, Lukasz and Polosukhin, Illia},
  title = {Attention Is All You Need},
  year = {2017},
  journal = {Advances in Neural Information Processing Systems},
  doi = {10.48550/arXiv.1706.03762},
}
```

### Add citations manually

Edit `paper/references.bib` directly:

```bibtex
@article{AuthorYear,
  author = {Last, First and Last2, First2},
  title = {Paper Title},
  journal = {Journal Name},
  year = {2024},
  doi = {10.xxxx/xxxxx},
}
```

### Cite in your paper

In `main.tex`, use natbib citation commands:

```latex
\citet{Vaswani2017} showed that...       % Vaswani et al. (2017) showed that...
\citep{Vaswani2017}                      % (Vaswani et al., 2017)
\citep[see][]{Vaswani2017}               % (see Vaswani et al., 2017)
```

### List all citations

```bash
$ research paper check
Checking paper...
All figure references resolved.

Citations: 12
```

### Using the researcher agent

For automated literature search:

```
You: Use the researcher agent to find the top 5 most-cited papers on
     graph neural networks for molecular property prediction. Add them
     to references.bib.
```

The researcher agent uses paper-search MCP servers (arXiv, Semantic Scholar,
PubMed) to find papers and formats BibTeX entries automatically.

---

## 4. Generating Figures

### Publication-quality settings

The paper module provides pre-configured matplotlib settings. In your Python
code:

```python
from core.paper import apply_rcparams, save_figure, COLORS
import matplotlib.pyplot as plt

# Apply publication settings (Arial font, 300 DPI, clean axes)
apply_rcparams()

# Use the colorblind-safe palette
fig, ax = plt.subplots()
ax.plot(x, y1, color=COLORS["blue"], label="Method A")
ax.plot(x, y2, color=COLORS["orange"], label="Method B")
ax.set_xlabel("Training Epochs")
ax.set_ylabel("Accuracy (%)")
ax.legend()

# Save as PDF (vector format)
save_figure(fig, "accuracy_comparison")
# Saved to: figures/accuracy_comparison.pdf
```

### The colorblind-safe palette

| Name | Hex | Use for |
|------|-----|---------|
| blue | `#0077BB` | Primary results |
| orange | `#EE7733` | Secondary/comparison |
| green | `#009988` | Tertiary |
| red | `#CC3311` | Errors/negative |
| purple | `#AA3377` | Additional |
| grey | `#BBBBBB` | Background/reference |

### Figure sizing

| Context | Width | Code |
|---------|-------|------|
| Single column | 3.5 inches | `figsize=(3.5, 2.5)` |
| Double column | 7.0 inches | `figsize=(7.0, 4.0)` |
| Full page | 7.0 inches | `figsize=(7.0, 9.0)` |

### Include figures in LaTeX

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\columnwidth]{../figures/accuracy_comparison.pdf}
  \caption{Comparison of accuracy between Method A and Method B over 100
           training epochs. Method A converges faster due to...}
  \label{fig:accuracy}
\end{figure}
```

### Check for missing figures

```bash
$ research paper check
```

This scans `main.tex` for `\includegraphics` commands and reports any files
that do not exist on disk.

---

## 5. Compiling the Paper

### Using the CLI

```bash
$ research paper build
Compiling paper...
Paper compiled successfully.
```

This runs `make all` in the `paper/` directory, which executes:
1. `pdflatex main`
2. `biber main` (bibliography)
3. `pdflatex main` (resolve references)
4. `pdflatex main` (final pass)

### Manual compilation

```bash
$ cd paper
$ make all          # full build
$ make clean        # remove build artifacts
$ make watch        # auto-rebuild on file changes (requires inotifywait)
```

### View the output

The compiled PDF is at `paper/main.pdf`. Open it with your PDF viewer:

```bash
$ xdg-open paper/main.pdf      # Linux
$ open paper/main.pdf           # macOS
```

> **Screenshot:** A PDF viewer showing the compiled paper with title, abstract,
> section headings, and a properly formatted bibliography.

---

## 6. Style Analysis and Transfer

The style transfer module (`core/style_transfer.py`) analyzes writing style
metrics and can generate transformation prompts to match a target style.

### Analyze your paper's style

```bash
$ research paper modernize
Style analysis...
  Avg sentence length: 18.3 words
  Passive voice ratio: 0.35
  Hedging ratio: 0.012
  Vocabulary richness: 0.68
  Tense: mixed
```

### What the metrics mean

| Metric | Good Range | Meaning |
|--------|-----------|---------|
| Avg sentence length | 15-25 words | Too short = choppy; too long = hard to follow |
| Passive voice ratio | 0.1-0.3 | Lower = more active voice (generally preferred) |
| Hedging ratio | 0.005-0.015 | Some hedging is appropriate in science |
| Vocabulary richness | 0.5-0.8 | Higher = more diverse word choice |
| Tense | varies by section | Methods = past; Discussion = present |

### Style transfer between papers

If you want your paper to match the style of a published paper you admire:

```
You: Analyze the style of reference/target_paper.txt, then analyze our
     paper/main.tex, and generate a transformation prompt to match the
     target style.
```

Claude uses `analyze_paper_style()` on both texts and `generate_transformation_prompt()`
to produce specific instructions like:

```
Transform the following text to match the target writing style:
- Use shorter, more concise sentences
- Prefer active voice over passive voice
- Be more assertive, reduce hedging words
- Use past tense
```

---

## 7. Plagiarism Checking

The `verify_no_plagiarism()` function performs a basic n-gram overlap check
against reference texts.

### Run a check during a session

```
You: Check the Methods section of our paper against the reference papers in
     reference/ for potential plagiarism.
```

Claude calls `verify_no_plagiarism()` with `threshold=6` (6-word n-grams) and
reports any overlapping phrases.

### What the check covers

- Detects verbatim 6-word (or longer) phrases that appear in both your text and
  reference texts
- This is a lightweight local check, not a full plagiarism detection service
- Use it as a first pass; for submission, use a proper service like Turnitin or
  iThenticate

### Interpret the results

- **0 matches:** Good. No detected overlap.
- **A few matches on common phrases:** Likely false positives (e.g., "in this
  paper we propose", "as shown in Figure"). Review and rephrase if needed.
- **Many matches from one source:** Rewrite those sections in your own words.

---

## 8. Full Workflow Example

Here is a complete paper-writing workflow in a single session:

```
You: Let's work on the paper. Start by reading knowledge/GOAL.md and the
     current state of paper/main.tex.

Claude: [reads files, summarizes current state]

You: Write a first draft of the Introduction. The key points are:
     1. Single-cell RNA-seq is transforming biology
     2. Current classification methods struggle with rare cell types
     3. We propose a contrastive learning approach
     4. Our method achieves 94% accuracy on the benchmark

Claude: [drafts Introduction, writes to paper/main.tex]

You: Now add citations for the papers we discussed in the literature review.

Claude: [adds BibTeX entries to references.bib, inserts \cite commands]

You: Generate Figure 1: a UMAP visualization of the cell clusters.

Claude: [writes Python script using apply_rcparams() and COLORS, saves figure]

You: Compile the paper and check for any issues.

Claude: [runs research paper build, reports success or errors]

You: Run style analysis on what we have so far.

Claude: [runs analyze_paper_style(), reports metrics]

You: The passive voice ratio is too high. Rewrite the Introduction using
     active voice.

Claude: [rewrites, reducing passive constructions]
```

---

## 9. Troubleshooting

### LaTeX compilation errors

**Undefined citation:**
```
LaTeX Warning: Citation 'AuthorYear' on page 2 undefined
```
Fix: Make sure the citation key in `\cite{AuthorYear}` matches a key in
`references.bib` exactly. Run `make all` twice to resolve references.

**Missing package:**
```
! LaTeX Error: File 'somepackage.sty' not found.
```
Fix: Install the package. In Docker, `texlive-full` includes everything.
On host: `sudo apt-get install texlive-full` or `tlmgr install somepackage`.

**Biber errors:**
```
ERROR - Cannot find 'main.bcf'
```
Fix: The template uses `natbib` (not `biblatex`), so the Makefile uses `biber`
as a placeholder. If you see this error, change the Makefile to use `bibtex`:

```makefile
BIBTEX = bibtex     # change from biber
```

### Figures not showing

- Check the path in `\includegraphics` is relative to `paper/`, not the project root
- Verify the figure file exists: `ls figures/`
- Run `research paper check` to see which figures are missing

### Style analysis returns all zeros

The text might be too short or contain mostly LaTeX commands. The analyzer works
on plain text. For best results, extract text sections without LaTeX markup.

### Citations not appearing in bibliography

1. Make sure you cite them in the text with `\cite{key}`
2. Run `make all` (needs multiple passes to resolve)
3. Check that `\bibliography{references}` points to the correct file

---

**Next:** [Tutorial 5: Website Setup](website-setup.md)
