# =============================================================================
# ricet: production Docker image
# Python 3.12 + Node.js 20 + LaTeX + claude-flow + ricet CLI
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — base system with Python, Node, and LaTeX
# ---------------------------------------------------------------------------
FROM ubuntu:24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_MAJOR=20

# System packages (single layer, cache-friendly ordering)
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Python 3.12 (default in 24.04)
        python3 python3-pip python3-venv python3-dev \
        # Build essentials
        build-essential git curl wget ca-certificates gnupg \
        # LaTeX (scheme-full for academic papers)
        texlive-full biber latexmk \
        # Media libs (for audio/image processing)
        ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20 via NodeSource (more reliable than Ubuntu's default)
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Verify runtimes
RUN python3 --version && node --version && npm --version

# ---------------------------------------------------------------------------
# Stage 2 — application layer
# ---------------------------------------------------------------------------
FROM base AS app

WORKDIR /opt/research-automation

# Install claude-flow globally
RUN npm install -g claude-flow@v3alpha

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Copy dependency specification first (better layer caching)
COPY pyproject.toml ./

# Create venv and install the package with all optional deps
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install the package itself (editable) and all extras
COPY . .
RUN pip install --no-cache-dir -e ".[all,dev]"

# Copy and prepare entrypoint
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && chmod +x scripts/*.sh 2>/dev/null || true

# Working directory for user projects
WORKDIR /workspace

# Expose ports: 7681 (ttyd web terminal), 4000 (docs preview)
EXPOSE 7681 4000

# Health check — verify Python and Node are functional
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import typer; print('ok')" && node -e "console.log('ok')"

ENTRYPOINT ["entrypoint.sh"]
CMD ["--web"]
