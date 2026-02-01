# Research Automation Demo Suite

Exercises 100% of the public API across 9 phases, simulating a complete
research project lifecycle from initialization to deployment.

## Quick Start

### Run locally

```bash
pip install -e ".[dev]"
python -m pytest demo/ -v
```

### Run in Docker

```bash
bash demo/scripts/run_in_docker.sh
```

### Run a single phase

```bash
python -m pytest demo/test_phase1_init.py -v
```

## Phases

| Phase | File | What it tests |
|-------|------|---------------|
| 1 | `test_phase1_init.py` | Project creation, onboarding, environment, security |
| 2 | `test_phase2_session.py` | Sessions, agents, model routing, tokens, prompt suggestions |
| 3 | `test_phase3_voice_mobile.py` | Voice pipeline (5 languages), mobile HTTP API, auth |
| 4 | `test_phase4_overnight.py` | Auto-debug loop, task spooler, autonomous routines, resources |
| 5 | `test_phase5_paper.py` | LaTeX pipeline, style transfer, verification, citations |
| 6 | `test_phase6_deploy.py` | Website build/deploy, social media, notifications |
| 7 | `test_phase7_multi_project.py` | Project registry, git worktrees, cross-repo |
| 8 | `test_phase8_advanced.py` | DevOps, reproducibility, browser, RAG, security, MCP |
| 9 | `test_phase9_integration.py` | Full lifecycle, all 17 CLI commands via CliRunner |

## What's Automated vs Human-Only

Everything in the `demo/` directory runs without network access, API keys,
or external tools. External calls are mocked.

For features requiring real hardware or credentials, see
`human_testing_checklist.md`.

| Automated | Human testing required |
|-----------|----------------------|
| All 38 core module APIs | Voice transcription (Whisper + real audio) |
| All 17 CLI commands | Physical mobile phone connection |
| Mobile HTTP server (localhost) | Real social media posting |
| Website build/deploy (filesystem) | Real email/Slack delivery |
| Git worktrees (mocked git) | LaTeX with Nature template |
| Docker health (mocked) | End-to-end overnight with Claude API |

## Running with Coverage

```bash
python -m pytest demo/ --cov=core --cov=cli --cov-report=term-missing
```

## Docker Demo

The `docker-compose.demo.yml` file runs the full suite inside a container:

```bash
# Quick demo (no LaTeX)
docker compose -f demo/docker-compose.demo.yml run --rm demo

# Full demo (with LaTeX)
docker compose -f demo/docker-compose.demo.yml --profile full run --rm demo-with-latex
```
