# Installation

ricet supports three installation methods: uv/pip (recommended), Docker, and from source.

---

## Prerequisites

All installation methods require:

- **Python 3.11+**
- **Node.js 20+** (for Claude Code CLI and context-hub)
- **Git**

Install Claude Code globally before proceeding:

```bash
npm install -g @anthropic-ai/claude-code
```

A Claude subscription (Pro or Team) is required and recommended. Authenticate
with Claude via browser login -- no API key needed:

```bash
claude auth login
```

For CI/headless environments only, you may optionally set an API key as a
fallback (billed separately, expensive):

```bash
# Optional fallback for CI/headless only:
export ANTHROPIC_API_KEY="your-key-here"
```

---

## Method 1: uv Install (Recommended)

ricet uses [uv](https://github.com/astral-sh/uv) for fast, reproducible package management. uv is auto-installed during `ricet init`.

### Basic install

```bash
# Install uv first (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

uv pip install ricet
```

This installs the core CLI with minimal dependencies: `typer`, `rich`, `pyyaml`, and `python-dotenv`.

### With ML extras

```bash
uv pip install "ricet[ml]"
```

Adds `numpy`, `pandas`, `scipy`, `scikit-learn`, `matplotlib`, and `seaborn`.

### With slides extras

```bash
uv pip install "ricet[slides]"
```

Adds `python-pptx`, `google-genai` (for Nano Banana Pro schematics), and `Pillow`.

### Full install

```bash
pip install -e ".[all]"
```

Adds everything in `ml`, `slides`, and `data` extras.

### Development install

```bash
pip install -e ".[dev]"
```

Adds `pytest`, `pytest-cov`, `black`, `isort`, and `mypy`.

### Verify installation

```bash
ricet --version
```

Expected output:

```
ricet 0.3.0
```

---

## Method 2: Docker

Docker provides a fully isolated environment with all system dependencies pre-installed, including LaTeX, ffmpeg, and GPU support.

### Build the image

```bash
cd docker
docker compose build
```

### Configure volumes

Create a `.env` file in the `docker/` directory:

```bash
PROJECT_PATH=/path/to/your/project
REFERENCE_PATH=/path/to/reference/papers
OUTPUTS_PATH=/path/to/outputs
SECRETS_PATH=/path/to/secrets
SHARED_PATH=/path/to/shared/knowledge
# ANTHROPIC_API_KEY is NOT needed if you use `claude auth login` (recommended).
# Optional fallback for CI/headless only:
# ANTHROPIC_API_KEY=your-key-here
GITHUB_TOKEN=your-token-here
```

### Run

```bash
docker compose up -d
docker compose exec research bash
```

Inside the container, the `ricet` command is available and the workspace is mounted at `/workspace`.

### What is included in the Docker image

| Package | Purpose |
|---------|---------|
| Python 3.11 | Runtime |
| Node.js + npm | Claude Code CLI |
| texlive-full + biber + latexmk | LaTeX compilation |
| ffmpeg + libsndfile1 | Audio processing (voice input) |
| numpy, pandas, scipy, scikit-learn | Scientific computing |
| torch, torchvision, torchaudio | Deep learning |
| matplotlib, seaborn, plotly | Visualization |
| chromadb, sentence-transformers | Vector search |
| jupyter, notebook | Interactive computing |
| typer, rich, tqdm | CLI and display |

---

## Method 3: From Source

### Clone and install

```bash
git clone https://github.com/lucafusarbassini/research-automation
cd research-automation
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

### Project layout

```
research-automation/
├── cli/                 # CLI entry point (ricet command)
├── core/                # Python modules (50+ modules)
├── templates/           # Copied into new projects
│   ├── .claude/         # Agent prompts, hooks, skills
│   ├── config/          # MCP config, settings
│   ├── knowledge/       # Encyclopedia, goals
│   ├── paper/           # LaTeX template
│   ├── sandbox/         # Dockerfile, docker-compose, martinprompt
│   └── slides/          # slide_utils.py, slides_task.md, example
├── defaults/            # Default prompts, philosophy, code style
├── docker/              # Dockerfile, docker-compose
├── scripts/             # Setup, overnight, interactive
├── tests/               # Test suite
├── docs/                # Documentation
└── pyproject.toml       # Package configuration
```

---

## Optional: claude-flow Integration

ricet optionally integrates with [claude-flow v3](https://github.com/ruvnet/claude-flow) for enhanced orchestration, HNSW vector memory, and 3-tier model routing. When claude-flow is not installed, every module gracefully falls back to its built-in implementation.

### Install claude-flow

```bash
# Automatic setup
bash scripts/setup_claude_flow.sh

# Or manual
npx claude-flow@v3alpha --version
```

### Verify integration

```bash
ricet metrics
```

If claude-flow is available, metrics will report actual token counts and cost data. Otherwise, character-based estimates are used.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| Claude subscription (Pro/Team) | Yes | `claude auth login` (required and recommended). `ANTHROPIC_API_KEY` is an optional fallback for CI/headless only |
| `GITHUB_TOKEN` | No | GitHub access for PRs, issues, Actions |
| `GOOGLE_API_KEY` | No | Nano Banana Pro for slide schematics (`ricet slides build`) |
| `NOTIFICATION_WEBHOOK` | No | Slack/webhook URL for notifications |
| `SMTP_USER` / `SMTP_PASSWORD` | No | Email notification credentials |

Credentials can also be stored in the global credential store at `~/.ricet/credentials.env` (managed by `ricet init`).

---

## Troubleshooting

### `ricet` command not found

Make sure the package is installed in your active Python environment:

```bash
pip install -e .
which ricet
```

### Claude Code not found

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

### Docker build fails

Ensure Docker and Docker Compose v2 are installed:

```bash
docker --version
docker compose version
```

### Permission denied on scripts

```bash
chmod +x scripts/*.sh
chmod +x templates/.claude/hooks/*.sh
```
