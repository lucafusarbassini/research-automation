FROM ubuntu:24.04

# System packages
RUN apt-get update && apt-get install -y \
    python3.11 python3-pip python3.11-venv \
    nodejs npm \
    git curl wget \
    texlive-full biber latexmk \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Python packages
RUN pip3 install --break-system-packages \
    numpy pandas scipy scikit-learn \
    torch torchvision torchaudio \
    matplotlib seaborn plotly \
    jupyter notebook \
    chromadb sentence-transformers \
    tqdm rich typer \
    python-dotenv pyyaml

# Working directory
WORKDIR /workspace

# Entry point
ENTRYPOINT ["/bin/bash"]
