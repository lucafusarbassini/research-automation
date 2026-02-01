# Tutorial 2: Docker Setup

This tutorial covers installing Docker on your system and running ricet
inside a container. The Docker setup provides a fully isolated
environment with Python 3.12, Node.js 20, LaTeX, and all required dependencies
pre-installed.

**Time:** ~20 minutes

**Prerequisites:** [Tutorial 1: Getting API Keys](getting-api-keys.md) completed
(you need Claude authentication via `claude auth login` or an Anthropic API key).

---

## Table of Contents

1. [Install Docker](#1-install-docker)
2. [Verify Docker Installation](#2-verify-docker-installation)
3. [Clone the Repository](#3-clone-the-repository)
4. [Configure Environment Variables](#4-configure-environment-variables)
5. [Build the Docker Image](#5-build-the-docker-image)
6. [Run the Container](#6-run-the-container)
7. [Understanding the Volume Mounts](#7-understanding-the-volume-mounts)
8. [Stopping and Restarting](#8-stopping-and-restarting)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Install Docker

### Linux (Ubuntu/Debian)

```bash
# Remove old versions
$ sudo apt-get remove docker docker-engine docker.io containerd runc

# Install prerequisites
$ sudo apt-get update
$ sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
$ sudo install -m 0755 -d /etc/apt/keyrings
$ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
$ sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
$ echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
$ sudo apt-get update
$ sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add your user to the docker group (avoids needing sudo)
$ sudo usermod -aG docker $USER
```

**Log out and log back in** for the group change to take effect.

### macOS

1. Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/).
2. Open the `.dmg` file and drag Docker to Applications.
3. Launch Docker Desktop from Applications.
4. Wait for the whale icon in the menu bar to show "Docker Desktop is running".

> **Screenshot:** macOS Applications folder with Docker icon, and the menu bar
> showing the Docker whale icon indicating the engine is running.

### Windows (WSL2)

1. Install WSL2 if you have not already:
   ```powershell
   wsl --install
   ```
2. Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
3. During installation, ensure **Use WSL 2 based engine** is checked.
4. Open Docker Desktop and wait for it to start.
5. Open a WSL2 terminal for all subsequent commands.

---

## 2. Verify Docker Installation

```bash
$ docker --version
Docker version 27.x.x, build xxxxxxx

$ docker compose version
Docker Compose version v2.x.x

$ docker run --rm hello-world
Hello from Docker!
...
```

If all three commands succeed, Docker is ready.

---

## 3. Clone the Repository

```bash
$ git clone https://github.com/YOUR_USERNAME/research-automation.git
$ cd research-automation
```

> **Screenshot:** Terminal showing the git clone output with the repository being
> downloaded and the user inside the research-automation directory.

---

## 4. Configure Environment Variables

If you used `claude auth login` on the host, your credentials in `~/.claude/`
are automatically mounted into the container (see
[Mounting Auth Credentials](#mounting-auth-credentials) below). No `.env`
changes are needed for Claude authentication.

For CI/headless environments or additional keys, create a `.env` file in the
project root:

```bash
$ cat > .env << 'EOF'
# Only needed if NOT using `claude auth login`:
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

GITHUB_TOKEN=github_pat_your-token-here

# Paths for Docker volume mounts
PROJECT_PATH=./workspace
REFERENCE_PATH=./reference
OUTPUTS_PATH=./outputs
SECRETS_PATH=./secrets
SHARED_PATH=./shared
EOF
```

Create the directories that Docker will mount:

```bash
$ mkdir -p workspace reference outputs secrets shared
```

### What each directory does

| Directory | Mount Point | Access | Purpose |
|-----------|-------------|--------|---------|
| `workspace/` | `/workspace` | read-write | Your active project files |
| `reference/` | `/reference` | **read-only** | Papers, datasets, reference code |
| `outputs/` | `/outputs` | read-write | Final deliverables (papers, figures) |
| `secrets/` | `/secrets` | **read-only** | API keys, credentials files |
| `shared/` | `/shared` | read-write | Cross-project knowledge base |

---

## 5. Build the Docker Image

The build takes 10-20 minutes on the first run because it installs a full LaTeX
distribution (`texlive-full`), Python scientific packages, and Node.js tools.
Subsequent builds are much faster due to Docker layer caching.

```bash
$ docker compose -f docker/docker-compose.yml build
```

> **Screenshot:** Terminal showing Docker build progress with layer download
> percentages and package installation output.

### Monitor the build

You will see output like:

```
[+] Building 842.3s (12/12) FINISHED
 => [base 1/3] FROM docker.io/library/ubuntu:24.04
 => [base 2/3] RUN apt-get update && apt-get install -y ...
 => [base 3/3] RUN curl -fsSL https://deb.nodesource.com/setup_20.x ...
 => [app 1/5] RUN npm install -g claude-flow@v3alpha
 => [app 2/5] RUN npm install -g @anthropic-ai/claude-code
 => [app 3/5] COPY pyproject.toml ./
 => [app 4/5] RUN python3 -m venv /opt/venv ...
 => [app 5/5] RUN pip install --no-cache-dir -e ".[all,dev]"
```

---

## 6. Run the Container

### Start the container in the foreground

```bash
$ docker compose -f docker/docker-compose.yml up
```

This starts the container with the default `--web` entrypoint, which exposes:

- Port **7681**: Web terminal (ttyd)
- Port **4000**: Documentation preview

### Start the container with a shell

If you prefer a direct terminal session:

```bash
$ docker compose -f docker/docker-compose.yml run --rm app bash
```

You are now inside the container at `/workspace`:

```bash
root@container:/workspace$ python3 --version
Python 3.12.x

root@container:/workspace$ claude --version
Claude Code vX.X.X

root@container:/workspace$ ricet --version
ricet 0.2.0
```

### Start a research project inside the container

```bash
root@container:/workspace$ ricet init my-first-project
```

Follow the interactive prompts (covered in detail in [Tutorial 3](first-project.md)).

---

## 7. Understanding the Volume Mounts

The `docker-compose.yml` maps host directories into the container:

```yaml
volumes:
  - ${PROJECT_PATH}:/workspace:rw      # Your project files (read-write)
  - ${REFERENCE_PATH}:/reference:ro    # Reference papers (read-only)
  - ${OUTPUTS_PATH}:/outputs:rw        # Deliverables (read-write)
  - ${SECRETS_PATH}:/secrets:ro        # API keys (read-only)
  - ${SHARED_PATH}:/shared:rw          # Shared knowledge (read-write)
```

Key points:

- Files you edit on the host appear instantly in the container and vice versa.
- The `:ro` (read-only) mounts prevent the container from modifying your
  reference papers or secret files.
- Resource limits are set to 8 CPUs and 32 GB RAM by default. Edit
  `docker/docker-compose.yml` to adjust.

---

## Mounting Auth Credentials

The `docker-compose.yml` automatically mounts your host `~/.claude/` directory
into the container so that browser-based authentication works without any extra
configuration:

```yaml
volumes:
  - ${CLAUDE_AUTH_DIR:-~/.claude}:/root/.claude:ro
```

This means if you have already run `claude auth login` on your host machine,
the container will pick up those credentials automatically.

### How it works

1. Run `claude auth login` on the **host** (outside Docker).
2. The credentials are saved to `~/.claude/` on the host.
3. When the container starts, the directory is mounted read-only at `/root/.claude`.
4. Claude Code inside the container uses the mounted credentials.

### Custom auth directory

If your Claude credentials are stored somewhere other than `~/.claude/`, set
the `CLAUDE_AUTH_DIR` environment variable:

```bash
$ CLAUDE_AUTH_DIR=/path/to/custom/.claude docker compose -f docker/docker-compose.yml up
```

### Fallback: API key

If you cannot use browser login (CI pipelines, headless servers), set
`ANTHROPIC_API_KEY` in your `.env` file or pass it directly:

```bash
$ ANTHROPIC_API_KEY=sk-ant-... docker compose -f docker/docker-compose.yml up
```

The entrypoint script detects both authentication methods and reports which one
is active.

---

## 8. Stopping and Restarting

### Stop the container

```bash
# If running in foreground, press Ctrl+C, then:
$ docker compose -f docker/docker-compose.yml down
```

### Restart

```bash
$ docker compose -f docker/docker-compose.yml up -d    # -d for detached (background)
```

### Rebuild after code changes

```bash
$ docker compose -f docker/docker-compose.yml build --no-cache
$ docker compose -f docker/docker-compose.yml up -d
```

### View logs

```bash
$ docker compose -f docker/docker-compose.yml logs -f
```

---

## 9. Troubleshooting

### Docker daemon not running

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

**Fix:**
```bash
$ sudo systemctl start docker     # Linux
# or launch Docker Desktop         # macOS / Windows
```

### Permission denied on Docker socket

```
Got permission denied while trying to connect to the Docker daemon socket
```

**Fix:**
```bash
$ sudo usermod -aG docker $USER
# Then log out and log back in
```

### Build fails at texlive-full

This package is large (~4 GB). Common causes:

- **Disk space:** Ensure at least 15 GB free for the image.
- **Network timeout:** Retry the build; Docker will resume from the last cached layer.
- **Mirror issues:** Add `--network=host` to the build command.

```bash
$ docker compose -f docker/docker-compose.yml build --network=host
```

### Container runs out of memory

If you see `Killed` or `OOMKilled`:

Edit `docker/docker-compose.yml` and increase the memory limit:

```yaml
deploy:
  resources:
    limits:
      memory: 64G    # increase from 32G
```

### Port already in use

```
Bind for 0.0.0.0:7681 failed: port is already allocated
```

**Fix:** Either stop the other service using that port, or change the port
mapping in `docker-compose.yml`:

```yaml
ports:
  - "7682:7681"    # map to a different host port
```

### Environment variables not visible inside container

**Fix:** Ensure your `.env` file is in the same directory as the
`docker-compose.yml` file, or pass variables explicitly:

```bash
$ ANTHROPIC_API_KEY=sk-ant-... docker compose -f docker/docker-compose.yml up
```

Or run `claude auth login` on the host and restart the container (the
`~/.claude/` mount will provide credentials automatically).

---

## Quick Reference

| Action | Command |
|--------|---------|
| Build image | `docker compose -f docker/docker-compose.yml build` |
| Start (foreground) | `docker compose -f docker/docker-compose.yml up` |
| Start (background) | `docker compose -f docker/docker-compose.yml up -d` |
| Stop | `docker compose -f docker/docker-compose.yml down` |
| Shell into running container | `docker compose -f docker/docker-compose.yml exec app bash` |
| View logs | `docker compose -f docker/docker-compose.yml logs -f` |
| Rebuild from scratch | `docker compose -f docker/docker-compose.yml build --no-cache` |

---

**Next:** [Tutorial 3: Your First Project](first-project.md)
