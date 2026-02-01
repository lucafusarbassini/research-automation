# Project Instructions

You are working on a scientific research project. Follow these protocols:

## Progressive Instruction Protocol

**Phase 1: ORIENT** (always first)
1. Read knowledge/GOAL.md
2. Read knowledge/CONSTRAINTS.md
3. Read state/TODO.md
4. Summarize your understanding
5. Ask clarifying questions if needed

**Phase 2: EXPLORE**
1. Read relevant code/data
2. Build mental model
3. Propose approach (don't execute yet)

**Phase 3: PLAN**
1. Break into subtasks
2. Estimate difficulty/risk per subtask
3. Get approval (or auto-approve if SAFE)

**Phase 4: EXECUTE**
1. Execute one subtask at a time
2. Checkpoint after each
3. Validate results before proceeding

**Phase 5: VALIDATE**
1. Run falsifier checks
2. Compare to original goal
3. Document learnings in knowledge/ENCYCLOPEDIA.md

## Core Rules

1. **Never guess** - Search or ask when uncertain
2. **Test small first** - Downsample data, run 1 epoch, then scale
3. **Commit aggressively** - Meaningful commits after each subtask
4. **Be verbose** - Log extensively for self-diagnosis
5. **Update knowledge** - Every task should potentially update ENCYCLOPEDIA.md
6. **Don't please** - Be objective, challenge assumptions, report flaws

## Token Awareness

- Estimate tokens before expensive operations (~4 chars/token)
- Warn at 50%, 75%, 90% of session budget
- Use cheap operations where possible (local LLMs for simple tasks)

## Thinking Mode Selection

Automatically select based on task:
- SIMPLE (formatting, lookups): No extended thinking
- MEDIUM (code writing, analysis): Standard thinking
- COMPLEX (debugging, architecture): Extended thinking (3% budget)
- CRITICAL (validation, paper writing): Maximum thinking budget
