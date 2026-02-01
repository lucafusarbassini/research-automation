# Tutorial 6: Overnight Mode

This tutorial explains how to use the autonomous overnight mode to run research
tasks while you sleep. Overnight mode iterates through your TODO list
unattended, auto-debugs failures, monitors system resources, and sends
notifications when done.

**Time:** ~20 minutes

**Prerequisites:**
- A project created with `research init` ([Tutorial 3](first-project.md))
- A well-defined `state/TODO.md` with clear, specific tasks
- Optional: Slack webhook for notifications ([Tutorial 1](getting-api-keys.md))

---

## Table of Contents

1. [How Overnight Mode Works](#1-how-overnight-mode-works)
2. [Preparing Your TODO List](#2-preparing-your-todo-list)
3. [Running Overnight Mode](#3-running-overnight-mode)
4. [Monitoring Progress](#4-monitoring-progress)
5. [Safety and Permissions](#5-safety-and-permissions)
6. [Enhanced Mode with Auto-Debug](#6-enhanced-mode-with-auto-debug)
7. [Notifications](#7-notifications)
8. [Reviewing Results in the Morning](#8-reviewing-results-in-the-morning)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. How Overnight Mode Works

Overnight mode runs a loop:

```
for each iteration (up to max):
    1. Read state/TODO.md
    2. Send contents to Claude with --dangerously-skip-permissions
    3. Claude executes the next uncompleted task
    4. Check for state/DONE file (completion signal)
    5. If error, snapshot state for debugging
    6. Brief pause, then next iteration
```

Each iteration is an independent Claude session that reads the current project
state, picks the next task, and works on it. The `--dangerously-skip-permissions`
flag allows Claude to read/write files and run commands without asking for
confirmation on each action.

> **Important:** Overnight mode runs with elevated permissions inside the
> project directory. Review the safety section below before your first run.

---

## 2. Preparing Your TODO List

The quality of your overnight run depends entirely on how well you write your
TODO list. Each task should be:

- **Specific**: "Train the ResNet-18 model on CIFAR-10 for 50 epochs with batch
  size 128" not "train the model"
- **Self-contained**: Claude should be able to complete it without asking
  questions
- **Verifiable**: Include expected outputs or success criteria
- **Ordered**: Put tasks in dependency order (earlier tasks first)

### Good TODO example

```markdown
# TODO

## Data Pipeline
- [ ] Download CIFAR-10 dataset to data/ directory using torchvision
- [ ] Write data/loader.py with train/val/test splits (80/10/10)
- [ ] Verify data loading: print shapes and a sample batch, commit output

## Baseline Model
- [ ] Implement models/resnet18.py using torchvision pretrained=False
- [ ] Write train.py with: Adam optimizer, lr=0.001, CrossEntropyLoss, 50 epochs
- [ ] Run training on a 1000-sample subset first, verify loss decreases
- [ ] Run full training, save model to checkpoints/baseline.pt
- [ ] Evaluate on test set, save metrics to results/baseline_metrics.json

## Analysis
- [ ] Generate figures/training_curves.pdf (loss and accuracy vs epoch)
- [ ] Generate figures/confusion_matrix.pdf for test predictions
- [ ] Write a summary of results in state/PROGRESS.md

## Signal completion
- [ ] Create state/DONE file when all above tasks are checked off
```

### Bad TODO example (too vague)

```markdown
# TODO
- [ ] Do the data stuff
- [ ] Build model
- [ ] Get results
- [ ] Write paper
```

---

## 3. Running Overnight Mode

### Using the CLI

```bash
$ cd ~/projects/my-first-project
$ research overnight --iterations 20
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--task-file` | `state/TODO.md` | Path to the task file |
| `--iterations` | 20 | Maximum number of iterations |

### Using the shell script directly

For more control, use the enhanced script:

```bash
$ bash scripts/overnight-enhanced.sh 20 state/TODO.md
```

### Running in the background

To keep it running after you close your terminal:

```bash
# Option 1: nohup
$ nohup research overnight --iterations 30 > overnight.log 2>&1 &
$ echo $!    # note the process ID

# Option 2: tmux (recommended)
$ tmux new -s overnight
$ research overnight --iterations 30
# Press Ctrl+B then D to detach
# Reconnect later: tmux attach -t overnight

# Option 3: screen
$ screen -S overnight
$ research overnight --iterations 30
# Press Ctrl+A then D to detach
# Reconnect later: screen -r overnight
```

> **Screenshot:** Terminal showing tmux with the overnight mode running,
> displaying iteration progress and task completion messages.

### Running in Docker

```bash
$ docker compose -f docker/docker-compose.yml run --rm research \
    bash -c "cd /workspace/my-project && research overnight --iterations 20"
```

---

## 4. Monitoring Progress

### From another terminal

While overnight mode runs, you can check progress:

```bash
$ cd ~/projects/my-first-project
$ research status
```

### Watch the log file

```bash
# The enhanced script writes to state/sessions/overnight_YYYYMMDD_HHMMSS.log
$ tail -f state/sessions/overnight_*.log
```

Example log output:

```
[2026-02-01T23:15:00+00:00] === Enhanced Overnight Mode ===
[2026-02-01T23:15:00+00:00] Max iterations: 20
[2026-02-01T23:15:00+00:00] Task file: state/TODO.md
[2026-02-01T23:15:00+00:00] Max retries per iteration: 3
[2026-02-01T23:15:01+00:00] --- Iteration 1/20 ---
[2026-02-01T23:17:42+00:00] Iteration 1: SUCCESS
[2026-02-01T23:17:47+00:00] --- Iteration 2/20 ---
[2026-02-01T23:20:15+00:00] Iteration 2: SUCCESS
```

### Check git history

Each completed task results in a commit (via the post-task hook):

```bash
$ git log --oneline -10
a1b2c3d Auto-commit after: Generate training curves figure
d4e5f6g Auto-commit after: Run full training
7890abc Auto-commit after: Verify data loading
```

---

## 5. Safety and Permissions

Overnight mode uses `--dangerously-skip-permissions`, which means Claude can
execute any command without asking. This is necessary for unattended operation
but requires precautions.

### What the Docker container restricts

When running inside Docker (recommended for overnight mode), the container
provides isolation:

| Resource | Restriction |
|----------|------------|
| File system | Only `/workspace`, `/outputs`, `/shared` are writable |
| Reference files | `/reference` is read-only |
| Secrets | `/secrets` is read-only |
| CPU | Limited to 8 cores (configurable) |
| Memory | Limited to 32 GB (configurable) |
| Network | Bridged network, no host network access |

### Permission levels (from `docker/permissions.md`)

| Level | Actions | Overnight Behavior |
|-------|---------|-------------------|
| SAFE | Read files, write to workspace, run Python, git ops | Auto-approved |
| MODERATE | Network requests, create directories | Logged, proceed |
| ELEVATED | Delete files, modify config, push to git | Proceed (logged) |
| DANGEROUS | sudo, modify secrets, spend money | **Always blocked** |

### Best practices for safe overnight runs

1. **Use Docker.** The container isolates the environment.
2. **Start with fewer iterations.** Try `--iterations 3` first, review results,
   then increase.
3. **Pin dependencies.** Make sure `requirements.txt` or `conda.yml` is locked
   so overnight runs do not install unexpected versions.
4. **Set cost limits.** If using cloud APIs, set spending caps in your cloud
   provider's console.
5. **Review TODO carefully.** Every task in the TODO will be attempted. Remove
   anything you do not want automated.
6. **Use the DONE signal.** End your TODO with a task that creates `state/DONE`
   so the loop stops when work is complete.

---

## 6. Enhanced Mode with Auto-Debug

The enhanced overnight script (`scripts/overnight-enhanced.sh`) adds features
beyond the basic loop:

### Auto-debug on failure

When an iteration fails, the enhanced script:

1. Captures the last 20 lines of error output
2. Sends them to Claude with a debug prompt
3. Claude attempts to diagnose and fix the issue
4. Retries the original task (up to 3 times)

```
[2026-02-02T02:15:00+00:00] Attempt 1/3 failed
[2026-02-02T02:15:05+00:00] Auto-debugging...
[2026-02-02T02:16:30+00:00] Attempt 2/3: SUCCESS
```

### Resource monitoring

Before each iteration, the script checks:

- **Disk usage:** Pauses if > 90% full
- **Available memory:** Pauses if < 512 MB free

If resources remain insufficient after a 60-second pause, the script stops
gracefully.

### State snapshots on error

On every failure, the script copies `state/*.md` to a timestamped snapshot
directory:

```
state/snapshots/error_20260202_021500_iter5/
├── TODO.md
├── PROGRESS.md
└── overnight_20260201_231500.log
```

This lets you investigate what went wrong even if subsequent iterations modify
the state files.

### Metrics file

At the end of the run, a JSON metrics file is written:

```json
{
  "started": "20260201_231500",
  "ended": "2026-02-02T06:30:00+00:00",
  "iterations": 15,
  "successes": 13,
  "failures": 2,
  "task_file": "state/TODO.md"
}
```

---

## 7. Notifications

### Slack notifications

If you set the `NOTIFICATION_WEBHOOK` environment variable, the enhanced script
sends a summary when the run completes:

```bash
$ export NOTIFICATION_WEBHOOK="https://hooks.slack.com/services/T00/B00/XXX"
```

You will receive a message like:

```
Overnight run complete: 13/15 succeeded
```

### Email notifications

Configure email in your project:

```bash
$ research config notifications
Notification method (email, slack, none) [none]: email
Email address: you@example.com
```

The notification system (`core/notifications.py`) includes throttling (default:
5 minutes between notifications of the same type) to prevent flooding.

### Desktop notifications

On Linux, `notify-send` is used automatically when `desktop_enabled` is true in
the notification config. This is useful for short runs where you are nearby but
not watching the terminal.

---

## 8. Reviewing Results in the Morning

When you wake up, here is your checklist:

### 1. Check the summary

```bash
$ cd ~/projects/my-first-project
$ research status
```

### 2. Read the metrics

```bash
$ cat state/sessions/overnight_*_metrics.json
{
  "started": "20260201_231500",
  "ended": "2026-02-02T06:30:00+00:00",
  "iterations": 15,
  "successes": 13,
  "failures": 2,
  "task_file": "state/TODO.md"
}
```

### 3. Review git history

```bash
$ git log --oneline -20
```

### 4. Check for error snapshots

```bash
$ ls state/snapshots/
error_20260202_021500_iter5/
```

Review the snapshot to understand what went wrong.

### 5. Validate results

Start an interactive session and use the falsifier:

```bash
$ research start --session-name "morning-review"
```

```
You: Run the falsifier agent on all results produced overnight. Check for
     data leakage, statistical validity, and code correctness.
```

### 6. Check the DONE signal

```bash
$ ls state/DONE
```

If the file exists, all tasks completed. If not, check `state/TODO.md` to see
which tasks remain.

---

## 9. Troubleshooting

### Overnight mode stops immediately

**Cause:** `state/TODO.md` does not exist.

```bash
$ cat state/TODO.md    # verify it exists and has content
```

### All iterations fail

Check the log:

```bash
$ tail -100 state/sessions/overnight_*.log
```

Common causes:
- `ANTHROPIC_API_KEY` not set or expired
- Network issues (if running in Docker, check connectivity)
- TODO tasks reference files that do not exist yet

### DONE file created too early

If a previous run left `state/DONE`, the new run will stop after the first
iteration.

```bash
$ rm state/DONE
$ research overnight --iterations 20
```

### High API costs

Each iteration is a separate Claude session. With 20 iterations of complex
tasks, costs can add up. To control costs:

- Use fewer iterations
- Use simpler tasks that require less reasoning
- Monitor costs at [console.anthropic.com](https://console.anthropic.com/)
- Set daily spending limits in your Anthropic account

### Auto-debug loops

If the auto-debugger itself fails, the enhanced script moves on after 3
retries. Check snapshots to understand persistent failures.

### Resource exhaustion

If disk fills up during training or large data processing:

1. The enhanced script detects this and pauses
2. Free up space: `rm -rf __pycache__ *.pyc .pytest_cache`
3. Move old checkpoints: `mv checkpoints/old_* /outputs/archive/`
4. Restart the run

---

**Next:** [Tutorial 7: Mobile Access](mobile-access.md)
