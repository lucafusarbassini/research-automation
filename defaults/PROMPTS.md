# Default Prompts Collection

These prompts are indexed for RAG. When users speak naturally, the system finds relevant prompts to structure their request.

---

## Literature Review

### PROMPT: deep-literature-review
**Tags**: papers, research, literature, review, survey
**Use when**: User wants to understand the state of a field

```
Conduct a comprehensive literature review on [TOPIC].

1. Search across: arXiv, PubMed, Semantic Scholar, bioRxiv
2. Find seminal papers (highly cited)
3. Find recent papers (last 2 years)
4. Identify key themes and debates
5. Identify gaps in the literature
6. For each key paper, extract:
   - Main contribution
   - Methods used
   - Key results
   - Limitations
   - BibTeX entry

Output: Structured literature review with citations.
```

### PROMPT: find-related-work
**Tags**: papers, related, similar, citations
**Use when**: User has a paper/idea and wants related work

```
Find papers related to: [DESCRIPTION]

Search strategy:
1. Direct keyword search
2. Citation tracking (papers that cite similar work)
3. Author tracking (what else have key authors written)

For each paper found:
- Relevance score (1-5)
- How it relates to the query
- BibTeX entry
```

---

## Code Writing

### PROMPT: implement-algorithm
**Tags**: code, implement, algorithm, write
**Use when**: User wants to implement something

```
Implement [ALGORITHM/FEATURE].

Before coding:
1. Check if implementation exists in reference/
2. Check if similar code exists in workspace/
3. Search for existing implementations online

Implementation requirements:
- Type hints on all functions
- Docstrings with examples
- Unit tests
- Handle edge cases
- Vectorize where possible

After coding:
1. Run on small synthetic data
2. Verify output makes sense
3. Run tests
4. Commit with meaningful message
```

### PROMPT: debug-issue
**Tags**: debug, fix, error, bug, crash
**Use when**: Something is broken

```
Debug the following issue: [ERROR/DESCRIPTION]

Debugging protocol:
1. Reproduce the error
2. Isolate: find minimal failing case
3. Hypothesize: what could cause this?
4. Test hypotheses one at a time
5. Fix and verify
6. Add test to prevent regression

Do NOT:
- Make multiple changes at once
- Guess without testing
- Ignore the actual error message
```

### PROMPT: optimize-code
**Tags**: optimize, speed, performance, slow
**Use when**: Code is too slow

```
Optimize the following code for performance: [CODE/FILE]

Optimization checklist:
1. Profile first - identify actual bottleneck
2. Vectorize loops (numpy/pandas)
3. Use appropriate data structures
4. Consider caching/memoization
5. Parallelize if appropriate

Constraints:
- Behavior must remain identical (test before/after)
- Readability should not suffer dramatically
- Document any non-obvious optimizations
```

---

## Data Analysis

### PROMPT: explore-dataset
**Tags**: data, explore, analysis, EDA
**Use when**: User has data and wants to understand it

```
Explore the dataset at [PATH].

Analysis steps:
1. Load and inspect shape, dtypes
2. Check for missing values
3. Compute summary statistics
4. Visualize distributions
5. Check for outliers
6. Identify potential issues

Output:
- Summary report
- Key visualizations
- Recommendations for preprocessing
```

### PROMPT: preprocess-data
**Tags**: preprocess, clean, data, prepare
**Use when**: Data needs cleaning

```
Preprocess the dataset for [PURPOSE].

Standard preprocessing:
1. Handle missing values (document strategy)
2. Handle outliers (document threshold)
3. Normalize/standardize if needed
4. Encode categoricals if needed
5. Create train/test split

Critical:
- Log all transformations
- Save preprocessing parameters for test data
- Ensure no data leakage between train/test
```

---

## Machine Learning

### PROMPT: train-model
**Tags**: train, model, ML, deep learning
**Use when**: User wants to train a model

```
Train a model for [TASK].

Protocol:
1. Start with simple baseline
2. Run 1 epoch first to verify pipeline
3. Check losses are decreasing
4. Run full training
5. Evaluate on held-out test set
6. Log all hyperparameters

Requirements:
- Set random seed
- Log to MLflow/W&B
- Save best checkpoint
- Document any tricks used
```

### PROMPT: evaluate-model
**Tags**: evaluate, test, metrics, results
**Use when**: User wants to assess model performance

```
Evaluate the model on [DATASET].

Evaluation checklist:
1. Use held-out test set (NEVER train set)
2. Compute appropriate metrics for task
3. Compute confidence intervals
4. Compare to baseline
5. Analyze failure cases

Report:
- Metrics with confidence intervals
- Comparison table
- Visualizations (confusion matrix, ROC, etc.)
- Failure case analysis
```

---

## Paper Writing

### PROMPT: write-section
**Tags**: write, paper, section, text
**Use when**: User wants to write part of paper

```
Write the [SECTION] section of the paper.

Section-specific guidance:
- Introduction: Problem → Gap → Contribution
- Methods: Reproducible detail, equations where needed
- Results: Findings with figure references
- Discussion: Interpretation, limitations, implications

Style:
- Active voice preferred
- Past tense for methods/results
- One idea per paragraph
- Every claim needs support
```

### PROMPT: improve-writing
**Tags**: edit, improve, writing, revise
**Use when**: User wants to improve text

```
Improve the following text: [TEXT]

Improvements:
1. Clarity: Is meaning unambiguous?
2. Concision: Remove unnecessary words
3. Flow: Do paragraphs connect?
4. Grammar: Fix any errors
5. Style: Match academic tone

Show both original and improved version.
Explain key changes.
```

### PROMPT: generate-figure
**Tags**: figure, plot, visualization, chart
**Use when**: User wants to create a figure

```
Create a figure showing [WHAT].

Requirements:
- Publication quality (see skills/figure-making.md)
- Colorblind-safe palette
- Clear labels and legend
- Appropriate figure size
- Export as PDF

After creating:
- Save to paper/figures/
- Provide LaTeX include code
- Describe in caption format
```

---

## Project Management

### PROMPT: plan-project
**Tags**: plan, roadmap, tasks, breakdown
**Use when**: User has a goal and needs a plan

```
Create a project plan for: [GOAL]

Planning steps:
1. Break goal into milestones
2. Break milestones into tasks
3. Estimate effort for each task
4. Identify dependencies
5. Identify risks

Output:
- Milestone list with deadlines
- Task list in TODO.md format
- Risk register
```

### PROMPT: status-report
**Tags**: status, progress, report, summary
**Use when**: User wants project status

```
Generate a status report.

Include:
1. What was accomplished since last report
2. Current blockers
3. Next steps
4. Token usage summary
5. Any decisions that need user input

Format: Concise bullet points, no fluff.
```

---

## Validation

### PROMPT: validate-results
**Tags**: validate, check, verify, falsify
**Use when**: User has results that need verification

```
Validate the following results: [RESULTS/CLAIM]

Validation protocol:
1. Check for data leakage
2. Check statistical validity
3. Check reproducibility
4. Check methodology
5. Compare to baselines
6. Look for confounders

Output: Falsification report (see falsifier agent template).
```

### PROMPT: review-code
**Tags**: review, code, quality, check
**Use when**: User wants code reviewed

```
Review the following code: [CODE/FILE]

Review checklist:
1. Correctness: Does it do what it claims?
2. Edge cases: Are they handled?
3. Efficiency: Any obvious inefficiencies?
4. Readability: Is it clear?
5. Documentation: Are comments adequate?
6. Tests: Are there tests?

Output: List of issues by severity (critical/major/minor/suggestion).
Be constructive but thorough.
```

---

## Maintenance

### PROMPT: clean-code
**Tags**: clean, refactor, tidy, organize
**Use when**: User wants code cleaned up

```
Clean up the code in [FILE/DIRECTORY].

Cleaning protocol:
1. Run tests, save expected output
2. Remove dead code
3. Improve naming
4. Add/improve docstrings
5. Split large functions
6. Run tests, verify same output
7. Commit

CRITICAL: Behavior must not change. Test before and after.
```

### PROMPT: update-docs
**Tags**: docs, documentation, readme, update
**Use when**: Documentation needs updating

```
Update documentation for [COMPONENT].

Documentation should include:
1. What it does (brief)
2. How to use it (with examples)
3. API reference (if applicable)
4. Known limitations

Sync with current code. Remove outdated info.
```
