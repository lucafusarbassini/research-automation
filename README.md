# Research Automation System

Automate scientific research using Claude Code with multi-agent orchestration, overnight autonomous execution, and comprehensive tooling.

## Quick Start

```bash
# Install Claude Code (requires Node.js 20+)
npm install -g @anthropic-ai/claude-code

# Clone and enter
git clone https://github.com/YOUR_USERNAME/research-automation
cd research-automation

# Start Claude Code and bootstrap
claude

# Then tell Claude:
# "Read BOOTSTRAP.md and execute the implementation plan starting from Phase 1"
```

## What This Builds

A comprehensive research automation system featuring:

- **Docker Containerization** - Safe, isolated execution environment
- **70+ MCP Integrations** - Auto-discovered based on task type
- **Multi-Agent Orchestration** - Master agent routes to specialized sub-agents
- **Overnight Mode** - Autonomous execution while you sleep
- **Knowledge Accumulation** - Encyclopedia that grows with each task
- **Paper Pipeline** - LaTeX template, figure generation, citation management
- **Progressive Instructions** - Orient → Explore → Plan → Execute → Validate

## Project Structure (After Build)

```
research-automation/
├── cli/                 # CLI entry point (`research` command)
├── core/                # Python modules
├── templates/           # Copied into new projects
│   ├── .claude/         # Agent definitions, skills, hooks
│   ├── paper/           # LaTeX template
│   ├── knowledge/       # Encyclopedia, goals, decisions
│   └── config/          # MCP config, settings
├── defaults/            # Default prompts, philosophy, code style
├── docker/              # Docker setup
└── scripts/             # Setup, overnight, interactive
```

## Usage (After Build)

### Create a New Project
```bash
research init my-project
# Interactive onboarding asks for goal, type, credentials
```

### Start Interactive Session
```bash
cd my-project
research start
```

### Run Overnight Mode
```bash
research overnight --iterations 20
```

### Check Status
```bash
research status
```

## Philosophy

1. **Never please the user** - Be objective, challenge assumptions
2. **Popperian falsification** - Try to break results, not validate them
3. **Never guess** - Search or ask when uncertain
4. **Test small, then scale** - Downsample first
5. **Commit aggressively** - Meaningful commits after every subtask
6. **Accumulate knowledge** - Encyclopedia grows with each task

See `defaults/PHILOSOPHY.md` for the complete philosophy.

## Files

| File | Purpose |
|------|---------|
| `BOOTSTRAP.md` | Implementation plan for Claude Code |
| `defaults/PHILOSOPHY.md` | Core principles for all agents |
| `defaults/CODE_STYLE.md` | Code style for the tool itself |
| `defaults/PROMPTS.md` | Default prompt collection for RAG |
| `defaults/MCP_NUCLEUS.json` | 70+ MCPs organized by tier |
| `defaults/ONBOARDING.md` | Questions asked during project init |

## License

MIT
