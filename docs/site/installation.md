# Installation

Research Automation supports three installation methods: pip (recommended), Docker, and from source.

---

## Prerequisites

All installation methods require:

- **Python 3.11+**
- **Node.js 20+** (for Claude Code CLI)
- **Git**

Install Claude Code globally before proceeding:

```bash
npm install -g @anthropic-ai/claude-code
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

---

## Method 1: pip Install (Recommended)

### Basic install

```bash
pip install -e .
```

This installs the core CLI with minimal dependencies: `typer`, `rich`, `pyyaml`, and `python-dotenv`.

### With ML extras

```bash
pip install -e ".[ml]"
```

Adds `numpy`, `pandas`, `scipy`, `scikit-learn`, `matplotlib`, and `seaborn`.

### Full install

```bash
pip install -e ".[all]"
```

Adds everything in `ml` plus `chromadb`, `sentence-transformers`, `torch`, and `jupyter`.

### Development install

```bash
pip install -e ".[dev]"
```

Adds `pytest`, `pytest-cov`, `black`, `isort`, and `mypy`.

### Verify installation

```bash
research --version
```

Expected output:

```
research-automation 0.1.0
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
ANTHROPIC_API_KEY=your-key-here
GITHUB_TOKEN=your-token-here
```

### Run

```bash
docker compose up -d
docker compose exec research bash
```

Inside the container, the `research` command is available and the workspace is mounted at `/workspace`.

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
git clone https://github.com/YOUR_USERNAME/research-automation
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
├── cli/                 # CLI entry point (research command)
├── core/                # Python modules (20+ modules)
├── templates/           # Copied into new projects
│   ├── config/          # MCP config, settings
│   ├── knowledge/       # Encyclopedia, goals
│   └── paper/           # LaTeX template
├── defaults/            # Default prompts, philosophy, code style
├── docker/              # Dockerfile, docker-compose
├── scripts/             # Setup, overnight, interactive
├── tests/               # Test suite
├── docs/                # Documentation
└── pyproject.toml       # Package configuration
```

---

## Optional: claude-flow Integration

Research Automation optionally integrates with [claude-flow v3](https://github.com/ruvnet/claude-flow) for enhanced orchestration, HNSW vector memory, and 3-tier model routing. When claude-flow is not installed, every module gracefully falls back to its built-in implementation.

### Install claude-flow

```bash
# Automatic setup
bash scripts/setup_claude_flow.sh

# Or manual
npx claude-flow@v3alpha --version
```

### Verify integration

```bash
research metrics
```

If claude-flow is available, metrics will report actual token counts and cost data. Otherwise, character-based estimates are used.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | API key for Claude |
| `GITHUB_TOKEN` | No | GitHub access for PRs, issues, Actions |
| `NOTIFICATION_WEBHOOK` | No | Slack/webhook URL for notifications |
| `SMTP_USER` / `SMTP_PASSWORD` | No | Email notification credentials |

---

## Troubleshooting

### `research` command not found

Make sure the package is installed in your active Python environment:

```bash
pip install -e .
which research
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
