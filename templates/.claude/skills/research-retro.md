---
name: research-retro
description: Session retrospective — what worked, what failed, update Encyclopedia
---

# Research Retrospective

You are now in **retrospective mode**. Your job is to review the current session or recent work and extract lasting value.

## Workflow

1. **Gather evidence** — Read:
   - `state/PROGRESS.md` — what was attempted
   - `state/TODO.md` — what's done vs remaining
   - Recent git log (`git log --oneline -20`)
   - `knowledge/GOAL.md` — are we closer to the goal?

2. **Analyze the session**:

   ### What Worked
   - Which approaches produced good results?
   - What tools or techniques were effective?
   - What configurations or hyperparameters performed well?

   ### What Didn't Work
   - Which approaches failed? Why?
   - What took longer than expected?
   - What assumptions turned out wrong?

   ### Surprises
   - Anything unexpected (positive or negative)?
   - New insights about the problem domain?

   ### Next Steps
   - What should the next session focus on?
   - Are there blocked tasks that need external input?
   - Should any TODO items be reprioritized?

3. **Update persistent knowledge**:
   - Append working approaches to `knowledge/ENCYCLOPEDIA.md` → "What Works"
   - Append failed approaches to `knowledge/ENCYCLOPEDIA.md` → "What Doesn't Work"
   - If any new behavioral rules emerged, note them for RULES.md
   - Update `state/TODO.md` with reprioritized items

4. **Output** — Present a concise retrospective summary (max 1 page). Focus on actionable takeaways, not narrative.

## When to Use

- End of a work session
- After overnight mode completes
- After a major experiment finishes
- Weekly review of project progress
