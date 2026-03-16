# ricet Demo Walkthrough

A realistic end-to-end workflow from project creation to publication.

## 1. Initialize a project

```bash
$ ricet init learning-rate-study

Step 0: Checking Python packages...
  All required packages available

Step 1: Detecting system...
  OS:      Linux 6.8.0
  Python:  3.12.3
  CPU:     x86_64
  RAM:     32.0 GB
  GPU:     NVIDIA RTX 4090
  Compute: local-gpu (auto-detected)
  Docker:  Available

Step 2: Project configuration
  Notification method [none]: slack
  Slack webhook URL: https://hooks.slack.com/services/T.../B.../xxx
  Target journal or conference (or 'skip') [skip]: NeurIPS
  Do you need a web dashboard? (yes/no) [no]: no
  Do you need mobile access? (yes/no) [no]: no

Step 2b: API credentials
  Press Enter to skip any credential you don't have yet.
  Anthropic API key [OPTIONAL FALLBACK for CI/headless only] (ANTHROPIC_API_KEY) []:
  GitHub token (GITHUB_PERSONAL_ACCESS_TOKEN) []: ghp_...
  HuggingFace access token (HUGGINGFACE_TOKEN) []:
  Weights & Biases API key (WANDB_API_KEY) []: ...
  ...
  2 credential(s) collected

Step 3: Creating project...
Step 4: GitHub repository
Step 5: Initializing git...

Project created at ./learning-rate-study

  Project folder guide:
    ./learning-rate-study/
    ├── .claude/skills/       ← research slash commands (/lit-review, /falsify, etc.)
    ├── reference/papers/     ← background papers (PDF, etc.)
    ├── reference/code/       ← reference code, scripts, notebooks
    ├── uploads/data/         ← datasets (large files auto-gitignored)
    ├── uploads/personal/     ← your papers, CV, writing samples
    ├── knowledge/GOAL.md     ← your research description (EDIT THIS)
    ├── knowledge/RULES.md    ← behavioral rules (auto-populated)
    ├── lab/                  ← experimental scripts (chaotic, WIP)
    ├── stable/               ← validated code (promoted from lab/)
    ├── secrets/.env          ← credentials (never committed)
    └── config/settings.yml   ← project configuration

Next steps:
  1. cd ./learning-rate-study
  2. Edit knowledge/GOAL.md with your detailed project description
  3. Add reference papers to reference/papers/
  4. ricet start
```

## 2. Prepare your project

```bash
$ cd learning-rate-study

# Write your research description (at least 200 characters)
$ $EDITOR knowledge/GOAL.md

# Add background papers
$ cp ~/papers/attention-is-all-you-need.pdf reference/papers/
$ cp ~/papers/cosine-annealing.pdf reference/papers/

# Add your own papers for style imprinting
$ cp ~/publications/my-icml-2025.pdf uploads/personal/

# Add dataset
$ cp ~/data/convergence-runs.csv uploads/data/
```

**knowledge/GOAL.md** should contain a detailed description of your research:

```markdown
# Project Goal

We investigate the effect of learning rate schedules on transformer
convergence speed and final loss across model scales (125M to 1.3B
parameters). Specifically, we compare constant learning rate, cosine
annealing, linear warmup + cosine decay, and the WSD schedule
proposed by Hu et al. (2024).

## Success Criteria

- [ ] Reproduce baseline convergence curves from Chinchilla paper
- [ ] Compare 4 LR schedules across 3 model scales
- [ ] Statistical significance tests (paired t-test, p < 0.05)
- [ ] Publication-ready figures and LaTeX paper

## Timeline

8 weeks
```

## 3. Start a research session

```bash
$ ricet start
  Session started: 20260115_143022 (a1b2c3d4...)
```

This launches Claude Code with your project context loaded. Claude reads GOAL.md and your research skills (`.claude/skills/`) are available as slash commands.

## 4. Interact with the system

Inside the Claude Code session, you can use natural language instructions or invoke research skills directly:

```
> Search for recent papers on learning rate schedules for transformers

  Found 12 relevant papers. Key findings stored in
  knowledge/ENCYCLOPEDIA.md. Top references added to paper/references.bib.

> /reproduce lab/train.py

  Running reproducibility check (STANDARD mode):
  - 5 seeds x 4 schedules = 20 runs
  - CV < 0.05 for all metrics
  Verdict: REPRODUCIBLE

> /falsify

  Falsification audit (STANDARD mode):
  - Leakage check: PASSED
  - Statistical rigor: 1 WARNING (multiple comparisons — apply Bonferroni)
  - Code correctness: PASSED
  Verdict: 4/5 attacks survived

> /style-transfer

  Analyzing style from uploads/personal/my-icml-2025.pdf...
  Identified 8 stylistic dimensions.
  Ready to rewrite — paste your draft section.

> /paper-draft methods

  Drafted paper/sections/methodology.tex (478 words).
  Style-matched to your lab's conventions.
  Missing citations: 2 (marked as [TBD]).
```

## 5. Run overnight

For longer experiments, use autonomous mode:

```bash
$ ricet overnight --iterations 30
  Starting overnight mode
  Iteration 1/30: Scaling to 350M model...
  Iteration 2/30: Running LR schedule comparison...
  ...
  Task completed!
```

## 6. Check results and promote

```bash
$ ricet status
  TODO:
  - [x] Reproduce baseline convergence curves
  - [x] Compare 4 LR schedules across 3 model scales
  - [ ] Statistical significance tests
  - [ ] Publication-ready figures

  Progress:
  Completed 125M and 350M experiments. 1.3B in progress.

# Promote validated analysis from lab/ to stable/
$ ricet promote lab/analysis.py
  Falsification checkpoint: PASSED
  Copied to stable/analysis.py with provenance metadata.

$ ricet paper check
  All figure references resolved.
  Citations: 24
```

## 7. Verify and build

```bash
# Fact-check a claim from the paper
$ ricet verify "Cosine annealing achieves 12% lower final loss than constant LR"
  [87%] Cosine annealing achieves 12% lower final loss than constant LR
  Extracted 1 claim for review.

# Build the paper
$ ricet paper build
  Paper compiled successfully.
```

## Available research skills

| Slash command | What it does |
|---|---|
| `/lit-review` | Search PubMed/arXiv, synthesize findings, generate BibTeX |
| `/experiment-review` | Six-dimension experiment audit with traffic-light scoring |
| `/falsify` | Adversarial validation (Popperian approach) |
| `/reproduce` | Reproducibility stress-test with multiple seeds/splits |
| `/paper-draft` | Draft paper sections with lab style conventions |
| `/style-transfer` | Match writing style to reference papers |
| `/add-citations` | Find, verify, and insert citations |
| `/figure-audit` | Audit figures for publication readiness |
| `/research-retro` | Session retrospective with knowledge extraction |
| `/overnight` | Autonomous overnight research session |
| `/slides` | Generate presentation decks |

## Folder structure after a session

```
learning-rate-study/
├── .claude/
│   ├── CLAUDE.md              ← project instructions for Claude
│   └── skills/                ← research slash commands
├── config/settings.yml
├── knowledge/
│   ├── GOAL.md                ← research description
│   ├── RULES.md               ← behavioral rules (auto-populated)
│   ├── ENCYCLOPEDIA.md        ← accumulated insights
│   ├── DECISION_LOG.md        ← project decisions
│   └── CONSTRAINTS.md         ← known limitations
├── reference/
│   ├── papers/                ← background PDFs
│   └── code/                  ← reference implementations
├── uploads/
│   ├── data/                  ← datasets
│   └── personal/              ← your papers, CV
├── lab/                       ← experimental scripts (WIP)
├── stable/                    ← validated code (promoted)
├── paper/
│   ├── main.tex               ← generated paper
│   ├── references.bib         ← citations
│   └── figures/               ← experiment plots
├── src/                       ← experiment code
├── output/                    ← raw results
├── secrets/.env               ← credentials (gitignored)
└── state/
    ├── TODO.md
    ├── PROGRESS.md
    └── sessions/              ← session history
```
