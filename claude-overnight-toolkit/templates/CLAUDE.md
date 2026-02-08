# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

[FILL IN: 1-2 paragraph description of what this project does and its scientific/engineering goal]

## Architecture

[FILL IN: Key components, how they fit together, data flow]

## Key Files

| File | Purpose |
|------|---------|
| `task.md` | Task specification (what to accomplish) |
| `martinprompt.md` | Overnight orchestrator prompt |
| `memory.md` | Persistent learnings across iterations |
| `todo.md` | Current work items |
| `progress.md` | Achievement log |
| `system.md` | Environment inventory |
| `reports/report_latest.md` | Scientific report |
| `reproduce.py` | Self-contained reproducibility script |

## Development Workflow

- Run experiments in `experiments/expNNN_description/` directories
- Save configs, logs, metrics, and figures in each experiment dir
- Update state files (memory.md, todo.md, progress.md) after every experiment
- Commit frequently with descriptive messages
- Consolidate findings into `reproduce.py`

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run main pipeline
python reproduce.py --quick    # Quick sanity check
python reproduce.py            # Full run

# Check GPU availability
python -c "import torch; print(torch.cuda.is_available())"
```

## Constraints

[FILL IN: What the agent should NOT do, boundaries, off-limits areas]
