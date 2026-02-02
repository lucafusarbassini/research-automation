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

Step 2: Setting up claude-flow...
  claude-flow is ready

Step 3: Project configuration
  Notification method [none]: slack
  Slack webhook URL: https://hooks.slack.com/services/T.../B.../xxx
  Target journal or conference (or 'skip') [skip]: NeurIPS
  Do you need a web dashboard? (yes/no) [no]: no
  Do you need mobile access? (yes/no) [no]: no

Step 3b: API credentials
  Press Enter to skip any credential you don't have yet.
  Anthropic API key (ANTHROPIC_API_KEY) []: sk-ant-...
  GitHub token (GITHUB_PERSONAL_ACCESS_TOKEN) []: ghp_...
  HuggingFace access token (HUGGINGFACE_TOKEN) []:
  Weights & Biases API key (WANDB_API_KEY) []: ...
  ...
  2 credential(s) collected

Step 4: Creating project...
Step 5: GitHub repository
Step 6: Initializing git...

Project created at ./learning-rate-study

  Project folder guide:
    ./learning-rate-study/
    ├── reference/papers/   ← background papers (PDF, etc.)
    ├── reference/code/     ← reference code, scripts, notebooks
    ├── uploads/data/       ← datasets (large files auto-gitignored)
    ├── uploads/personal/   ← your papers, CV, writing samples
    ├── knowledge/GOAL.md   ← your research description (EDIT THIS)
    ├── secrets/.env        ← API keys (never committed)
    └── config/settings.yml ← project configuration

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

This launches Claude Code with your project context loaded. The master agent reads GOAL.md and begins working.

## 4. Interact with the system

Inside the Claude Code session, you can give natural language instructions:

```
> Search for recent papers on learning rate schedules for transformers

  [RESEARCHER] Found 12 relevant papers. Key findings stored in
  knowledge/ENCYCLOPEDIA.md. Top references added to paper/references.bib.

> Implement the experiment comparing 4 LR schedules on a 125M model

  [CODER] Created src/train.py with configurable LR schedules.
  Running 4 training jobs with seeds 0-2...
  Results saved to output/results_125M.json

> Review the training code for correctness

  [REVIEWER] Code review complete. 2 suggestions:
  - Add gradient clipping (missing from cosine schedule)
  - Log per-step loss, not just per-epoch
  Applied fixes.

> Write the methodology section

  [WRITER] Drafted paper/sections/methodology.tex (478 words).
  Uses your style profile from uploads/personal/my-icml-2025.pdf.
```

## 5. Run overnight

For longer experiments, use autonomous mode:

```bash
$ ricet overnight --iterations 30
  Starting overnight mode
  Using claude-flow swarm orchestration
  Iteration 1/30: Scaling to 350M model...
  Iteration 2/30: Running LR schedule comparison...
  ...
  Task completed!
```

## 6. Check results

```bash
$ ricet status
  TODO:
  - [x] Reproduce baseline convergence curves
  - [x] Compare 4 LR schedules across 3 model scales
  - [ ] Statistical significance tests
  - [ ] Publication-ready figures

  Progress:
  Completed 125M and 350M experiments. 1.3B in progress.

$ ricet paper check
  All figure references resolved.
  Citations: 24
```

## 7. Verify and publish

```bash
# Fact-check a claim from the paper
$ ricet verify "Cosine annealing achieves 12% lower final loss than constant LR"
  [87%] Cosine annealing achieves 12% lower final loss than constant LR
  Extracted 1 claim for review.

# Build the paper
$ ricet paper build
  Paper compiled successfully.

# Publish a summary to Medium
$ ricet publish medium
  Post title: Learning Rate Schedules for Transformers: A Systematic Study
  Post body: We compared four learning rate schedules...
  Published successfully.
  URL: https://medium.com/@you/learning-rate-schedules-...
```

## Folder structure after a session

```
learning-rate-study/
├── config/settings.yml
├── knowledge/
│   ├── GOAL.md
│   ├── CONSTRAINTS.md
│   └── ENCYCLOPEDIA.md        ← accumulated insights
├── reference/
│   ├── papers/                ← background PDFs
│   └── code/                  ← reference implementations
├── uploads/
│   ├── data/                  ← datasets
│   └── personal/              ← your papers, CV
├── paper/
│   ├── main.tex               ← generated paper
│   ├── references.bib         ← citations
│   └── figures/               ← experiment plots
├── src/                       ← experiment code
├── output/                    ← raw results
├── secrets/.env               ← API keys (gitignored)
└── state/
    ├── TODO.md
    ├── PROGRESS.md
    └── sessions/              ← session history
```
