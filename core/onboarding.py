"""Full onboarding workflow: questionnaire, credential collection, workspace setup."""

import logging
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

COMPUTE_TYPES = ["local-cpu", "local-gpu", "cloud", "cluster"]
NOTIFICATION_METHODS = ["email", "slack", "none"]
CLAUDE_FLOW_PKG = "claude-flow"

WORKSPACE_DIRS = ["reference", "local", "secrets", "uploads"]

FOLDER_READMES: dict[str, str] = {
    "reference/papers": (
        "# Reference Papers\n\n"
        "Upload background papers (PDF, etc.) for knowledge ingestion.\n\n"
        "The researcher agent will read these to build context for your project.\n"
    ),
    "reference/code": (
        "# Reference Code\n\n"
        "Upload reference code, scripts, and notebooks here.\n\n"
        "Examples: baseline implementations, utility scripts, Jupyter notebooks.\n"
    ),
    "uploads/data": (
        "# Datasets\n\n"
        "Upload datasets here. Large files are auto-gitignored.\n\n"
        "Supported formats: CSV, Parquet, JSON, HDF5, etc.\n"
    ),
    "uploads/personal": (
        "# Personal Materials\n\n"
        "Upload personal materials for style imprinting and context.\n\n"
        "Examples: your published papers, writing portfolio, writing samples, lab notes.\n"
    ),
}

PREREQUISITES = {
    "docker": {
        "check_cmd": "docker --version",
        "install_hint": "Install Docker: https://docs.docker.com/get-docker/",
    },
    "node": {
        "check_cmd": "node --version",
        "install_hint": "Install Node.js (v18+): https://nodejs.org/ or use nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash",
    },
    "git": {
        "check_cmd": "git --version",
        "install_hint": "Install Git: https://git-scm.com/downloads",
    },
    "claude": {
        "check_cmd": "claude --version",
        "install_hint": "Install Claude CLI: npm install -g @anthropic-ai/claude-code",
    },
}

EXPECTED_UPLOAD_DIRS = {
    "paper_examples": "reference",
    "reference_code": "reference",
    "data_files": "uploads",
}


@dataclass
class OnboardingAnswers:
    project_name: str = ""
    goal: str = ""
    project_type: str = "general"
    github_repo: str = ""
    success_criteria: list[str] = field(default_factory=list)
    timeline: str = "flexible"
    compute_type: str = "local-cpu"
    gpu_name: str = ""
    notification_method: str = "none"
    notification_email: str = ""
    slack_webhook: str = ""
    credentials: dict[str, str] = field(default_factory=dict)
    journal_target: str = ""
    paper_type: str = "journal-article"
    needs_website: bool = True
    needs_mobile: bool = True
    # Mobile access
    tunnel_domain: str = ""      # e.g. "ricet.yourdomain.com" — permanent named tunnel
    screen_session: str = "ricet"  # GNU screen session name for live voice injection


def _install_tectonic(system: str, print_fn) -> bool:
    """Download and install tectonic binary."""
    import tarfile
    import tempfile
    import urllib.request

    arch_map = {
        ("Linux", "x86_64"): "x86_64-unknown-linux-gnu",
        ("Linux", "aarch64"): "aarch64-unknown-linux-gnu",
        ("Darwin", "x86_64"): "x86_64-apple-darwin",
        ("Darwin", "arm64"): "aarch64-apple-darwin",
    }
    machine = platform.machine()
    key = (system, machine)
    if key not in arch_map:
        print_fn(f"  tectonic: unsupported platform {system}/{machine}")
        return False

    version = "0.15.0"
    triple = arch_map[key]
    url = (
        f"https://github.com/tectonic-typesetting/tectonic/releases/download/"
        f"tectonic%40{version}/tectonic-{version}-{triple}.tar.gz"
    )
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tgz = Path(tmpdir) / "tectonic.tar.gz"
            urllib.request.urlretrieve(url, tgz)
            with tarfile.open(tgz) as tf:
                tf.extractall(tmpdir)
            binary = Path(tmpdir) / "tectonic"
            # Install to user-local bin or conda bin
            for dest_dir in (
                Path(shutil.which("python3") or shutil.which("python") or "/usr/local/bin").parent,
                Path.home() / ".local" / "bin",
            ):
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / "tectonic"
                shutil.copy2(binary, dest)
                dest.chmod(0o755)
                if shutil.which("tectonic"):
                    print_fn(f"  tectonic: installed to {dest}")
                    return True
    except Exception as e:
        print_fn(f"  tectonic: install failed ({e})")
    return False


def _install_biber(system: str, print_fn) -> bool:
    """Download and install biber binary."""
    import tarfile
    import tempfile
    import urllib.request

    # biber 2.17 is compatible with tectonic's bundled biblatex 3.17
    version = "2.17"
    if system == "Darwin":
        suffix = "OSX_Intel/biber-darwin_x86_64.tar.gz"
    else:
        suffix = "Linux/biber-linux_x86_64.tar.gz"
    url = (
        f"https://sourceforge.net/projects/biblatex-biber/files/"
        f"biblatex-biber/{version}/binaries/{suffix}/download"
    )
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tgz = Path(tmpdir) / "biber.tar.gz"
            urllib.request.urlretrieve(url, tgz)
            with tarfile.open(tgz) as tf:
                tf.extractall(tmpdir)
            binary = Path(tmpdir) / "biber"
            for dest_dir in (
                Path(shutil.which("python3") or shutil.which("python") or "/usr/local/bin").parent,
                Path.home() / ".local" / "bin",
            ):
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / "biber"
                shutil.copy2(binary, dest)
                dest.chmod(0o755)
                if shutil.which("biber"):
                    print_fn(f"  biber: installed to {dest}")
                    return True
    except Exception as e:
        print_fn(f"  biber: install failed ({e})")
    return False


def auto_install_system_deps(*, print_fn=None) -> dict[str, bool]:
    """Auto-install critical system dependencies that ricet needs.

    Installs: texlive (pdflatex), whisper, and checks Docker availability.
    Returns mapping of dependency name -> success boolean.
    """
    if print_fn is None:
        print_fn = print

    results: dict[str, bool] = {}
    system = platform.system()

    # 1. LaTeX - needed for paper pipeline
    #    Strategy: tectonic (single binary, auto-downloads packages) + biber
    if shutil.which("tectonic") and shutil.which("biber"):
        print_fn("  tectonic + biber: already installed")
        results["latex"] = True
    else:
        installed_tectonic = bool(shutil.which("tectonic"))
        installed_biber = bool(shutil.which("biber"))

        if not installed_tectonic:
            print_fn("  tectonic: installing...")
            installed_tectonic = _install_tectonic(system, print_fn)

        if not installed_biber:
            print_fn("  biber: installing...")
            installed_biber = _install_biber(system, print_fn)

        if installed_tectonic and installed_biber:
            print_fn("  tectonic + biber: ready")
        elif installed_tectonic:
            print_fn("  tectonic: ready, biber: not found (bibliography won't resolve)")
        else:
            print_fn("  tectonic: not found (paper compilation unavailable)")
            print_fn("    Manual install: curl -sL https://drop-sh.fullyjustified.net | sh")
        results["latex"] = installed_tectonic

    # 2. Make - needed for paper Makefile
    if shutil.which("make"):
        results["make"] = True
    else:
        installed = False
        for pkg_mgr in ("mamba", "conda"):
            if shutil.which(pkg_mgr):
                try:
                    subprocess.run(
                        [pkg_mgr, "install", "-y", "-c", "conda-forge", "make"],
                        capture_output=True, timeout=60,
                    )
                    if shutil.which("make"):
                        installed = True
                        break
                except Exception:
                    pass
        if not installed:
            print_fn("  make: not found (try: mamba install -c conda-forge make)")
        results["make"] = installed

    # 3. ffmpeg - needed by whisper for audio decoding
    if shutil.which("ffmpeg"):
        results["ffmpeg"] = True
    else:
        for pkg_mgr in ("mamba", "conda"):
            if shutil.which(pkg_mgr):
                try:
                    subprocess.run(
                        [pkg_mgr, "install", "-y", "-c", "conda-forge", "ffmpeg"],
                        capture_output=True, timeout=120,
                    )
                    if shutil.which("ffmpeg"):
                        print_fn("  ffmpeg: installed via " + pkg_mgr)
                        results["ffmpeg"] = True
                        break
                except Exception:
                    pass
        if "ffmpeg" not in results:
            print_fn("  ffmpeg: not found (needed for audio; try: mamba install -c conda-forge ffmpeg)")
            results["ffmpeg"] = False

    # 4. Docker + Docker Compose v2 check
    #    docker-compose v1 (standalone, <=1.29) is incompatible with modern Docker Engine
    #    and causes 'ContainerConfig' KeyError. We require the v2 plugin.
    if shutil.which("docker"):
        print_fn("  docker: available")
        results["docker"] = True

        # Check for docker compose v2 plugin (required)
        _has_v2_plugin = False
        try:
            _cr = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=5,
            )
            if _cr.returncode == 0 and "v2" in _cr.stdout.lower():
                _has_v2_plugin = True
        except Exception:
            pass

        if not _has_v2_plugin:
            # Try installing the plugin automatically
            print_fn("  docker compose v2: NOT found — installing plugin...")
            _installed = False
            has_sudo = subprocess.run(
                ["sudo", "-n", "true"], capture_output=True, timeout=3
            ).returncode == 0
            if has_sudo:
                for _install_cmd in (
                    ["sudo", "apt-get", "install", "-y", "docker-compose-plugin"],
                    ["sudo", "yum", "install", "-y", "docker-compose-plugin"],
                    ["sudo", "dnf", "install", "-y", "docker-compose-plugin"],
                ):
                    try:
                        _ir = subprocess.run(_install_cmd, capture_output=True, timeout=120)
                        if _ir.returncode == 0:
                            _installed = True
                            print_fn("  docker compose v2: installed")
                            break
                    except Exception:
                        pass
            if not _installed:
                print_fn("  docker compose v2: NOT available (required for ricet)")
                print_fn("    Install: sudo apt install docker-compose-plugin")
                print_fn("    WARNING: docker-compose v1 (standalone) is NOT supported")
            results["docker_compose"] = _installed
        else:
            print_fn("  docker compose v2: available")
            results["docker_compose"] = True

        # Tailscale operator hint
        if shutil.which("tailscale"):
            try:
                _ts_serve = subprocess.run(
                    ["tailscale", "serve", "status"],
                    capture_output=True, text=True, timeout=5,
                )
                if _ts_serve.returncode != 0 and "Access denied" in (_ts_serve.stderr or ""):
                    print_fn("  tailscale: needs operator permission for serve")
                    print_fn("    Run once: sudo tailscale set --operator=$USER")
                    has_sudo = subprocess.run(
                        ["sudo", "-n", "true"], capture_output=True, timeout=3
                    ).returncode == 0
                    if has_sudo:
                        subprocess.run(
                            ["sudo", "tailscale", "set", f"--operator={__import__('os').environ.get('USER', 'user')}"],
                            capture_output=True, timeout=5,
                        )
                        print_fn("  tailscale: operator set automatically")
            except Exception:
                pass
    else:
        print_fn("  docker: not installed (needed for ricet up / overnight mode)")
        print_fn("    Install: https://docs.docker.com/get-docker/")
        results["docker"] = False
        results["docker_compose"] = False

    # 5a. uv - fast Python package manager (SOTA replacement for pip)
    if shutil.which("uv"):
        print_fn("  uv: available")
        results["uv"] = True
    else:
        print_fn("  uv: installing...")
        try:
            subprocess.run(
                ["bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
                capture_output=True, timeout=60,
            )
            # uv installs to ~/.local/bin which may not be on PATH yet
            uv_path = Path.home() / ".local" / "bin" / "uv"
            results["uv"] = uv_path.exists() or bool(shutil.which("uv"))
            if results["uv"]:
                print_fn("  uv: installed")
            else:
                print_fn("  uv: install failed (optional; pip will be used instead)")
        except Exception:
            print_fn("  uv: install failed (optional; pip will be used instead)")
            results["uv"] = False

    # 5b. screen - needed for background sessions and remote phone access
    if shutil.which("screen"):
        print_fn("  screen: available")
        results["screen"] = True
    else:
        print_fn("  screen: installing...")
        installed = False
        if system == "Linux":
            for pkg_mgr_cmd in (
                ["sudo", "apt-get", "install", "-y", "screen"],
                ["sudo", "yum", "install", "-y", "screen"],
                ["sudo", "dnf", "install", "-y", "screen"],
            ):
                try:
                    subprocess.run(
                        pkg_mgr_cmd,
                        capture_output=True, timeout=60,
                    )
                    if shutil.which("screen"):
                        print_fn("  screen: installed")
                        installed = True
                        break
                except Exception:
                    pass
        elif system == "Darwin":
            if shutil.which("brew"):
                try:
                    subprocess.run(
                        ["brew", "install", "screen"],
                        capture_output=True, timeout=60,
                    )
                    if shutil.which("screen"):
                        installed = True
                except Exception:
                    pass
        if not installed and not shutil.which("screen"):
            print_fn("  screen: not found (install with your package manager)")
        results["screen"] = installed or bool(shutil.which("screen"))

    # 5. Whisper (speech-to-text) - try pip install
    try:
        import whisper  # noqa: F401
        print_fn("  whisper: already installed")
        results["whisper"] = True
    except ImportError:
        print_fn("  whisper: installing openai-whisper...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "openai-whisper"],
                capture_output=True, timeout=300,
            )
            results["whisper"] = True
            print_fn("  whisper: installed successfully")
        except Exception:
            print_fn("  whisper: could not auto-install (try: pip install openai-whisper)")
            results["whisper"] = False

    # 6. Tailscale — permanent private network for mobile access (no domain needed)
    #    Requires the tailscaled daemon running as root (one-time sysadmin setup).
    #    The CLI itself works for non-root users once the daemon is running.
    if shutil.which("tailscale"):
        # Check if daemon is up and we can auth
        ts_status = subprocess.run(
            ["tailscale", "status"], capture_output=True, text=True, timeout=5
        )
        if ts_status.returncode == 0:
            print_fn("  tailscale: running")
            results["tailscale"] = True
            # Allow non-root users to run tailscale serve (needed for ricet mobile tunnel)
            subprocess.run(
                ["sudo", "-n", "tailscale", "set", f"--operator={__import__('os').environ.get('USER', 'user')}"],
                capture_output=True, timeout=5,
            )
        else:
            # Daemon present but not authenticated — try `tailscale up`
            has_sudo = subprocess.run(
                ["sudo", "-n", "true"], capture_output=True, timeout=3
            ).returncode == 0
            if has_sudo:
                r = subprocess.run(
                    ["sudo", "tailscale", "up", "--accept-routes"],
                    capture_output=True, text=True, timeout=30,
                )
                results["tailscale"] = r.returncode == 0
                if results["tailscale"]:
                    print_fn("  tailscale: activated")
                else:
                    print_fn("  tailscale: installed but could not activate — run: sudo tailscale up")
            else:
                print_fn("  tailscale: installed but not running")
                print_fn("    Ask your sysadmin: sudo tailscale up")
                print_fn("    (needed once; then works without sudo)")
                results["tailscale"] = False
    else:
        # Try to install without sudo via the official script
        has_sudo = subprocess.run(
            ["sudo", "-n", "true"], capture_output=True, timeout=3
        ).returncode == 0
        if has_sudo:
            print_fn("  tailscale: installing...")
            r = subprocess.run(
                ["bash", "-c", "curl -fsSL https://tailscale.com/install.sh | sudo sh"],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode == 0:
                r2 = subprocess.run(
                    ["sudo", "tailscale", "up", "--accept-routes"],
                    capture_output=True, text=True, timeout=30,
                )
                if r2.returncode == 0:
                    print_fn("  tailscale: installed and activated")
                    results["tailscale"] = True
                else:
                    print_fn("  tailscale: installed — run: sudo tailscale up")
                    results["tailscale"] = False
            else:
                print_fn("  tailscale: install failed — manual: curl -fsSL https://tailscale.com/install.sh | sudo sh")
                results["tailscale"] = False
        else:
            print_fn("  tailscale: not available (no sudo)")
            print_fn("    Ask your sysadmin to run once:")
            print_fn("      curl -fsSL https://tailscale.com/install.sh | sudo sh")
            print_fn("      sudo tailscale up")
            print_fn("    After that, ricet mobile works without sudo.")
            print_fn("    Falling back to Cloudflare quick tunnel for now.")
            results["tailscale"] = False

    # 6b. cloudflared - fallback if Tailscale unavailable
    if shutil.which("cloudflared"):
        print_fn("  cloudflared: already installed")
        results["cloudflared"] = True
    else:
        cf_bin = Path.home() / ".local" / "bin" / "cloudflared"
        if cf_bin.exists():
            print_fn(f"  cloudflared: already installed at {cf_bin}")
            results["cloudflared"] = True
        else:
            print_fn("  cloudflared: installing...")
            try:
                import urllib.request

                arch = platform.machine()
                arch_map = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
                arch_slug = arch_map.get(arch, "amd64")
                url = (
                    f"https://github.com/cloudflare/cloudflared/releases/latest"
                    f"/download/cloudflared-linux-{arch_slug}"
                )
                cf_bin.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(url, str(cf_bin))
                import os as _os

                _os.chmod(cf_bin, 0o755)
                print_fn(f"  cloudflared: installed at {cf_bin}")
                results["cloudflared"] = True
            except Exception:
                print_fn("  cloudflared: could not auto-install (needed for ricet mobile tunnel)")
                results["cloudflared"] = False

    # 7. qrcode Python library - needed for mobile QR codes
    try:
        import qrcode  # noqa: F401

        results["qrcode"] = True
    except ImportError:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "qrcode"],
                capture_output=True, timeout=60,
            )
            print_fn("  qrcode: installed")
            results["qrcode"] = True
        except Exception:
            results["qrcode"] = False

    # 8. context-hub (chub) - versioned API docs for coding agents
    #    Requires Node.js >= 18.  Distributed via npm as @aisuite/chub.
    if shutil.which("chub"):
        print_fn("  chub (context-hub): available")
        results["chub"] = True
    else:
        npm = shutil.which("npm")
        if npm:
            print_fn("  chub (context-hub): installing via npm...")
            try:
                r = subprocess.run(
                    [npm, "install", "-g", "@aisuite/chub"],
                    capture_output=True, timeout=120,
                )
                results["chub"] = bool(shutil.which("chub"))
                if results["chub"]:
                    print_fn("  chub: installed")
                else:
                    print_fn("  chub: install may have succeeded; restart shell if 'chub' not found")
                    results["chub"] = True  # npm didn't error; assume OK
            except Exception:
                print_fn("  chub: install failed (run: npm install -g @aisuite/chub)")
                results["chub"] = False
        else:
            print_fn(
                "  chub (context-hub): skipped (Node.js/npm not found; "
                "install Node ≥18 then: npm install -g @aisuite/chub)"
            )
            results["chub"] = False

    return results


def validate_prerequisites(
    *,
    run_cmd=None,
) -> dict:
    """Check that required tools (Docker, Node.js, Git, Claude CLI) are installed.

    Args:
        run_cmd: Optional callable(cmd) -> bool override for testing.

    Returns:
        Dict mapping missing tool names to their install instructions.
        An empty dict means everything is available.
    """
    if run_cmd is None:

        def run_cmd(cmd: str) -> bool:
            try:
                subprocess.run(
                    cmd.split(),
                    capture_output=True,
                    timeout=10,
                )
                return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False

    missing: dict[str, str] = {}
    for tool, info in PREREQUISITES.items():
        if not run_cmd(info["check_cmd"]):
            missing[tool] = info["install_hint"]
    return missing


def auto_install_claude(
    *,
    run_cmd=None,
) -> bool:
    """Attempt to install the Claude CLI via npm if it is not already available.

    Args:
        run_cmd: Optional callable(cmd, check) -> subprocess.CompletedProcess
                 override for testing.

    Returns:
        True if Claude CLI is available after this call (already installed or
        freshly installed), False otherwise.
    """
    if run_cmd is None:

        def run_cmd(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=120,
                check=check,
            )

    # Check if already present
    try:
        result = run_cmd("claude --version")
        if result.returncode == 0:
            logger.info("Claude CLI already installed")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Attempt npm install
    logger.info("Attempting to install Claude CLI via npm...")
    try:
        result = run_cmd("npm install -g @anthropic-ai/claude-code", check=False)
        if result.returncode == 0:
            logger.info("Claude CLI installed successfully")
            return True
        logger.warning("npm install failed (exit %d)", result.returncode)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not run npm: %s", exc)

    return False


def auto_install_claude_flow(
    *,
    run_cmd=None,
) -> bool:
    """Attempt to install claude-flow via npm if not already available.

    Args:
        run_cmd: Optional callable(cmd, check) -> subprocess.CompletedProcess
                 override for testing.

    Returns:
        True if claude-flow is available after this call.
    """
    if run_cmd is None:

        def run_cmd(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=120,
                check=check,
            )

    # Check if already present
    try:
        result = run_cmd("npx claude-flow --version")
        if result.returncode == 0:
            logger.info("claude-flow already available")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Attempt npm install
    logger.info("Installing claude-flow via npm...")
    try:
        result = run_cmd("npm install -g claude-flow", check=False)
        if result.returncode == 0:
            logger.info("claude-flow installed successfully")
            return True
        logger.warning("npm install claude-flow failed (exit %d)", result.returncode)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not run npm: %s", exc)

    return False


def detect_system_for_init() -> dict:
    """Auto-detect system capabilities for init. Returns a summary dict."""
    from core.environment import discover_system

    info = discover_system()
    compute_type = "local-gpu" if info.gpu else "local-cpu"
    result = {
        "os": f"{info.os} {info.os_version}",
        "python": info.python_version,
        "cpu": info.cpu,
        "ram_gb": info.ram_gb,
        "gpu": info.gpu,
        "compute_type": compute_type,
        "conda": info.conda_available,
        "docker": info.docker_available,
    }

    # Log the detected environment decision
    try:
        from core.knowledge import log_decision

        log_decision(
            f"env detected: {compute_type}, conda={info.conda_available}",
            f"system has GPU={bool(info.gpu)}, docker={info.docker_available}",
        )
    except Exception:
        pass  # Never break the main flow for logging

    return result


def _auto_install_gh(*, run_cmd=None) -> bool:
    """Attempt to install the GitHub CLI (gh) if it is not already available.

    Strategy: try conda first (works cross-platform), then brew, then warn.

    Args:
        run_cmd: Optional callable(cmd, check) -> subprocess.CompletedProcess
                 override for testing.

    Returns:
        True if gh is available after this call, False otherwise.
    """
    if run_cmd is None:

        def run_cmd(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=300,
                check=check,
            )

    # Already installed?
    if shutil.which("gh"):
        return True

    # Try conda/mamba install
    for tool in ("mamba", "conda"):
        if shutil.which(tool):
            logger.info("Attempting to install gh via %s...", tool)
            try:
                result = run_cmd(f"{tool} install -c conda-forge gh -y")
                if result.returncode == 0 and shutil.which("gh"):
                    logger.info("gh installed successfully via %s", tool)
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    # Try brew
    if shutil.which("brew"):
        logger.info("Attempting to install gh via brew...")
        try:
            result = run_cmd("brew install gh")
            if result.returncode == 0 and shutil.which("gh"):
                logger.info("gh installed successfully via brew")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    logger.warning(
        "Could not auto-install gh. Install manually: "
        "https://cli.github.com/ or 'conda install -c conda-forge gh'"
    )
    return False


def _gh_auth_with_token(token: str) -> bool:
    """Authenticate gh CLI using a PAT. Returns True on success."""
    try:
        result = subprocess.run(
            ["gh", "auth", "login", "--with-token"],
            input=token,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("gh authenticated with PAT")
            return True
        logger.warning("gh auth --with-token failed: %s", result.stderr.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("gh auth --with-token error: %s", exc)
    return False


def _gh_auth_interactive() -> bool:
    """Run interactive browser-based OAuth login. Gets full repo scopes."""
    try:
        print("  Opening browser for GitHub login (grants full repo access)...")
        result = subprocess.run(
            ["gh", "auth", "login", "-h", "github.com", "-p", "ssh",
             "-w"],  # -w = web/browser flow
            timeout=120,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _gh_is_authenticated() -> bool:
    """Return True if gh can actually reach the API (not just has a token)."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "-q", ".login"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _gh_get_username() -> str:
    """Get the authenticated GitHub username."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "-q", ".login"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def create_github_repo(
    project_name: str,
    *,
    private: bool = True,
    github_token: str = "",
    run_cmd=None,
) -> str:
    """Create a GitHub repository using the gh CLI.

    If the token lacks repo-creation scope, falls back to interactive
    browser-based OAuth which automatically gets the right permissions.
    """
    if run_cmd is None:

        def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

    # Auto-install gh if missing
    if not shutil.which("gh"):
        if _auto_install_gh():
            logger.info("gh CLI now available after auto-install")
        else:
            logger.warning("gh CLI not available. Skipping repo creation.")
            return ""

    # Ensure gh is authenticated — use user's PAT if available
    if not _gh_is_authenticated():
        if github_token:
            logger.info("gh not authenticated — logging in with user's PAT...")
            if not _gh_auth_with_token(github_token):
                logger.warning("PAT auth failed, trying browser login...")
                if not _gh_auth_interactive():
                    return ""
        else:
            logger.info("gh not authenticated — trying browser login...")
            if not _gh_auth_interactive():
                return ""

    # Create repo
    visibility = "--private" if private else "--public"
    try:
        result = run_cmd(
            ["gh", "repo", "create", project_name, visibility]
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            for line in output.splitlines():
                if "github.com" in line:
                    return line.strip()
            username = _gh_get_username()
            if username:
                return f"https://github.com/{username}/{project_name}"
            return output

        err = result.stderr.strip()
        logger.warning("gh repo create failed: %s", err)

        # Token lacks scope — re-auth with browser OAuth (full permissions)
        if "not accessible" in err or "401" in err or "Bad credentials" in err:
            print(f"  Token lacks repo-creation scope — re-authenticating...")
            if _gh_auth_interactive():
                retry = run_cmd(
                    ["gh", "repo", "create", project_name, visibility]
                )
                if retry.returncode == 0:
                    output = retry.stdout.strip()
                    for line in output.splitlines():
                        if "github.com" in line:
                            return line.strip()
                    username = _gh_get_username()
                    if username:
                        return f"https://github.com/{username}/{project_name}"
                    return output

        if "already exists" in err:
            username = _gh_get_username()
            if username:
                return f"https://github.com/{username}/{project_name}"
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not create GitHub repo: %s", exc)

    return ""


def setup_claude_web_access(
    *,
    host: str = "localhost",
    port: int = 7860,
    run_cmd=None,
) -> str:
    """Configure Claude for web-based access and return the URL.

    This writes a small config snippet and returns the URL the user should
    open in a browser to connect to the Claude web interface.

    Args:
        host: Bind address for the web server.
        port: Port number.
        run_cmd: Optional callable(cmd) -> subprocess.CompletedProcess override.

    Returns:
        The URL string where the user can reach Claude's web UI.
    """
    url = f"http://{host}:{port}"
    logger.info("Claude web access configured at %s", url)
    return url


def verify_uploaded_files(
    project_path: Path,
    answers: OnboardingAnswers,
) -> list[str]:
    """Check that files the user said they would provide are actually present.

    Looks in the standard workspace directories (reference/, uploads/) for
    non-empty content.  Returns a list of human-readable warnings for anything
    that appears to be missing.

    Args:
        project_path: Root of the project.
        answers: Collected onboarding answers (used for context on what was
                 promised).

    Returns:
        List of warning strings.  Empty list means everything looks good.
    """
    warnings: list[str] = []

    # Check reference/ for papers and code
    ref_dir = project_path / "reference"
    if ref_dir.exists():
        real_ref = [
            f
            for f in ref_dir.rglob("*")
            if f.is_file() and f.name not in (".gitkeep", "README.md")
        ]
        if not real_ref:
            warnings.append(
                "No reference materials found in reference/. "
                "Add papers, code, or other background materials."
            )
    else:
        warnings.append(
            "reference/ directory does not exist. Run setup_workspace() first."
        )

    # Check uploads/ for data files
    uploads_dir = project_path / "uploads"
    if uploads_dir.exists():
        # Only .gitkeep means effectively empty
        real_files = [f for f in uploads_dir.iterdir() if f.name != ".gitkeep"]
        if not real_files:
            warnings.append(
                "uploads/ directory is empty. "
                "Place any data files or supporting materials there."
            )
    else:
        warnings.append(
            "uploads/ directory does not exist. Run setup_workspace() first."
        )

    # If a github repo was specified, check for reference code
    if answers.github_repo and answers.github_repo != "skip":
        ref_dir = project_path / "reference"
        if ref_dir.exists():
            code_files = [
                f
                for f in ref_dir.iterdir()
                if f.suffix in (".py", ".r", ".R", ".jl", ".m", ".ipynb")
            ]
            if not code_files:
                warnings.append(
                    "No reference code found in reference/. "
                    "Consider adding example scripts from your repository."
                )

    return warnings


def collect_answers(
    project_name: str,
    *,
    prompt_fn=None,
    system_info: dict | None = None,
) -> OnboardingAnswers:
    """Collect onboarding answers interactively.

    The questionnaire is streamlined: GPU, compute type, and system info are
    auto-detected.  The project goal is written to GOAL.md after init (not
    entered as a one-liner).

    Args:
        project_name: The project name.
        prompt_fn: Callable(prompt, default) -> str. Uses input() if None.
        system_info: Pre-detected system info dict (from detect_system_for_init).
                     If None, auto-detection runs inline.

    Returns:
        Filled OnboardingAnswers.
    """
    if prompt_fn is None:
        prompt_fn = (
            lambda prompt, default="": input(f"{prompt} [{default}]: ") or default
        )

    answers = OnboardingAnswers(project_name=project_name)

    # --- Auto-detect system ---
    if system_info is None:
        system_info = detect_system_for_init()

    answers.compute_type = system_info.get("compute_type", "local-cpu")
    answers.gpu_name = system_info.get("gpu", "")

    # --- Goal: tell user to write detailed description in GOAL.md ---
    answers.goal = "(See GOAL.md — edit with your detailed project description)"

    # --- Notification method ---
    answers.notification_method = prompt_fn(
        "Notification method (email, slack, none)", "none"
    )
    if answers.notification_method not in NOTIFICATION_METHODS:
        answers.notification_method = "none"

    if answers.notification_method == "email":
        answers.notification_email = prompt_fn("Notification email", "")
    elif answers.notification_method == "slack":
        answers.slack_webhook = prompt_fn("Slack webhook URL", "")

    # --- Journal / publication target ---
    answers.journal_target = prompt_fn(
        "Target journal or conference (or 'skip')", "skip"
    )
    if answers.journal_target == "skip":
        answers.journal_target = ""

    # Paper type, website, and mobile are always default-enabled
    answers.paper_type = "journal-article"
    answers.needs_website = True
    answers.needs_mobile = True

    # --- Mobile / tunnel access ---
    # Detect what's available to guide the user
    _has_tailscale = bool(shutil.which("tailscale"))
    _has_cf_login = (Path.home() / ".cloudflared" / "cert.pem").exists()

    print_fn = getattr(prompt_fn, "_print", None) or (lambda s: None)  # best-effort print

    mobile_mode = prompt_fn(
        "Remote mobile access mode:\n"
        "  tailscale  — permanent address, no domain needed (recommended, free)\n"
        "  cloudflare — permanent address, needs a domain on Cloudflare\n"
        "  quick      — ephemeral Cloudflare URL (changes on restart)\n"
        "  none       — local network only",
        "tailscale" if _has_tailscale else ("cloudflare" if _has_cf_login else "quick"),
    ).strip().lower()

    if mobile_mode == "cloudflare":
        tunnel_domain = prompt_fn(
            "Cloudflare tunnel subdomain (e.g. ricet.yourdomain.com)", ""
        ).strip()
        answers.tunnel_domain = tunnel_domain
    # tailscale and quick modes need no extra config — tailscale detected at tunnel start

    screen_name = prompt_fn(
        "GNU screen session name for live voice injection", "ricet"
    ).strip()
    answers.screen_session = screen_name or "ricet"

    return answers


def setup_workspace(project_path: Path) -> None:
    """Create workspace directories with guided README files.

    Args:
        project_path: Root of the project.
    """
    for dirname in WORKSPACE_DIRS:
        d = project_path / dirname
        d.mkdir(parents=True, exist_ok=True)
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")

    # Create guided subdirectories with README files
    for subdir, readme_content in FOLDER_READMES.items():
        d = project_path / subdir
        d.mkdir(parents=True, exist_ok=True)
        readme = d / "README.md"
        if not readme.exists():
            readme.write_text(readme_content)

    logger.info("Workspace directories created")


def print_folder_map(project_path: Path) -> list[str]:
    """Return a list of lines showing the folder map for user guidance.

    Args:
        project_path: Root of the project.

    Returns:
        List of formatted lines describing where to put files.
    """
    lines = [
        "Project folder guide:",
        f"  {project_path}/",
        "  ├── reference/papers/   ← background papers (PDF, etc.)",
        "  ├── reference/code/     ← reference code, scripts, notebooks",
        "  ├── uploads/data/       ← datasets (large files auto-gitignored)",
        "  ├── uploads/personal/   ← your papers, writing portfolio, samples",
        "  ├── knowledge/GOAL.md   ← your research description (EDIT THIS)",
        "  ├── secrets/.env        ← credentials (never committed)",
        "  └── config/settings.yml ← project configuration",
    ]
    return lines


def write_settings(project_path: Path, answers: OnboardingAnswers) -> Path:
    """Write the project settings file from onboarding answers.

    Args:
        project_path: Root of the project.
        answers: Collected onboarding answers.

    Returns:
        Path to the written settings file.
    """
    settings = {
        "project": {
            "name": answers.project_name,
            "created": datetime.now().isoformat(),
        },
        "compute": {
            "type": answers.compute_type,
            "gpu": answers.gpu_name,
        },
        "notifications": {
            "enabled": answers.notification_method != "none",
            "method": answers.notification_method,
        },
        "features": {
            "website": answers.needs_website,
            "mobile": answers.needs_mobile,
        },
        "credentials": {},
    }

    if answers.notification_email:
        settings["notifications"]["email"] = answers.notification_email
    if answers.slack_webhook:
        settings["notifications"]["slack_webhook"] = answers.slack_webhook

    if answers.journal_target:
        settings["project"]["journal_target"] = answers.journal_target

    if answers.paper_type:
        settings["project"]["paper_type"] = answers.paper_type

    if answers.github_repo and answers.github_repo != "skip":
        settings["credentials"]["github_repo"] = answers.github_repo

    settings_path = project_path / "config" / "settings.yml"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        yaml.dump(settings, default_flow_style=False, sort_keys=False)
    )

    logger.info("Settings written to %s", settings_path)
    return settings_path


def write_goal_file(project_path: Path, answers: OnboardingAnswers) -> None:
    """Write the GOAL.md file from onboarding answers.

    Args:
        project_path: Root of the project.
        answers: Collected onboarding answers.
    """
    goal_file = project_path / "knowledge" / "GOAL.md"
    if not goal_file.exists():
        return

    content = goal_file.read_text()
    content = content.replace("<!-- User provides during init -->", answers.goal)

    if answers.success_criteria:
        criteria_text = "\n".join(f"- [ ] {c}" for c in answers.success_criteria)
        content = content.replace("- [ ] Criterion 1\n- [ ] Criterion 2", criteria_text)

    if answers.timeline and answers.timeline != "flexible":
        content = content.replace("<!-- e.g., 3 months -->", answers.timeline)

    goal_file.write_text(content)


# Each credential: (env_var, short_description, how_to_get_url, category)
# Categories: "core", "publishing", "ml", "cloud", "integrations", "slack", "email"
#
# Pricing legend in descriptions:
#   [FREE]  = free tier available, no credit card needed
#   [PAID]  = requires a paid subscription or pay-as-you-go
#   [FREE*] = free tier with limits, paid for production use
CREDENTIAL_REGISTRY: list[tuple[str, str, str, str]] = [
    # --- Core (always ask) ---
    (
        "ANTHROPIC_API_KEY",
        "Anthropic API key [OPTIONAL FALLBACK for CI/headless only]",
        "SKIP this — a Claude subscription (Pro or Team) is required and recommended.\n"
        "  Authenticate via: claude auth login\n"
        "  API key is an optional fallback for CI/headless environments only (billed separately, expensive).\n"
        "  If you must use an API key: https://console.anthropic.com/ → API Keys",
        "core",
    ),
    (
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "GitHub PAT [FREE] (only if you want ricet to create repos for you)",
        "Option A (recommended): Skip — use SSH keys (https://github.com/settings/keys)\n"
        "  Option B: https://github.com/settings/tokens?type=beta → 'repo' + 'workflow' scopes",
        "core",
    ),
    (
        "OPENAI_API_KEY",
        "OpenAI API key [PAID, pay-as-you-go] (for embeddings & fallback models)",
        "https://platform.openai.com/api-keys → Create new secret key",
        "core",
    ),
    (
        "GOOGLE_API_KEY",
        "Google Gemini API key [FREE tier: 5-15 RPM, no credit card needed]",
        "https://aistudio.google.com/apikey → sign in with Google account → Create API key.\n"
        "  Free tier: up to 15 req/min. Paid: enable billing in Google Cloud for higher limits.",
        "core",
    ),
    # --- Slack (figure delivery & notifications) ---
    (
        "SLACK_BOT_TOKEN",
        "Slack bot token [FREE] (send plots & alerts to Slack)",
        "Enables ricet to upload figures to Slack automatically.\n"
        "  1. Create a free Slack workspace (or use an existing one)\n"
        "  2. Go to https://api.slack.com/apps → Create New App → From Scratch\n"
        "  3. OAuth & Permissions → Scopes → Bot Token Scopes → Add:\n"
        "       chat:write, files:write, channels:read, groups:read\n"
        "  4. Install App to Workspace → copy the Bot User OAuth Token (starts with xoxb-)\n"
        "  5. Create a channel (e.g. #claude_plots) and invite your bot:\n"
        "       /invite @YourBotName\n"
        "  IMPORTANT: token must start with xoxb- (Bot Token), NOT xapp- (App Token)",
        "core",
    ),
    (
        "SLACK_PLOTS_CHANNEL",
        "Slack channel for figure delivery [FREE] (e.g. claude_plots)",
        "Name of the Slack channel where ricet will post plots and figures.\n"
        "  Default: claude_plots — create this channel in your workspace and\n"
        "  invite your bot with /invite @YourBotName",
        "core",
    ),
    # --- ML / Experiment tracking ---
    (
        "HUGGINGFACE_TOKEN",
        "HuggingFace access token [FREE] (models & datasets)",
        "https://huggingface.co/settings/tokens → New token (read access)",
        "ml",
    ),
    (
        "WANDB_API_KEY",
        "Weights & Biases API key [FREE*] (experiment tracking, free for personal use)",
        "https://wandb.ai/authorize → copy key",
        "ml",
    ),
    # --- Publishing ---
    (
        "PYPI_TOKEN",
        "PyPI API token [FREE] (for publishing pip packages)",
        "https://pypi.org/manage/account/token/ → Add API token",
        "publishing",
    ),
    (
        "ZENODO_TOKEN",
        "Zenodo access token [FREE] (permanent DOI for software, datasets, papers)",
        "https://zenodo.org/account/settings/applications/tokens/new/\n"
        "  Required scopes: deposit:write, deposit:actions\n"
        "  For testing first: https://sandbox.zenodo.org/ → ZENODO_SANDBOX_TOKEN",
        "publishing",
    ),
    (
        "MEDIUM_TOKEN",
        "Medium integration token [FREE] (publishing)",
        "https://medium.com/me/settings/security → Integration tokens → Get token",
        "publishing",
    ),
    (
        "LINKEDIN_CLIENT_ID",
        "LinkedIn app Client ID [FREE]",
        "https://www.linkedin.com/developers/apps → Create App → Auth tab",
        "publishing",
    ),
    (
        "LINKEDIN_CLIENT_SECRET",
        "LinkedIn app Client Secret [FREE]",
        "(same page as Client ID above)",
        "publishing",
    ),
    (
        "LINKEDIN_ACCESS_TOKEN",
        "LinkedIn OAuth2 access token [FREE]",
        "(generate via OAuth2 flow in LinkedIn developer portal)",
        "publishing",
    ),
    # --- Cloud / Infrastructure ---
    (
        "AWS_ACCESS_KEY_ID",
        "AWS access key ID [PAID] (for cloud compute/storage)",
        "https://console.aws.amazon.com/iam → Users → Security credentials",
        "cloud",
    ),
    (
        "AWS_SECRET_ACCESS_KEY",
        "AWS secret access key [PAID]",
        "(same page as AWS access key above)",
        "cloud",
    ),
    (
        "NOTION_API_KEY",
        "Notion integration token [FREE*] (project boards, free for personal use)",
        "https://www.notion.so/my-integrations → New integration → copy secret",
        "cloud",
    ),
    (
        "ZAPIER_NLA_API_KEY",
        "Zapier NLA API key [FREE*] (workflow automation, free tier: 100 tasks/mo)",
        "https://nla.zapier.com/credentials/ → Create API key",
        "cloud",
    ),
    # --- Optional integrations (separate prompt group) ---
    # These services have FREE MCP servers -- prefer MCPs over API keys.
    (
        "GAMMA_API_KEY",
        "Gamma API key [PAID, requires Pro ~$15/mo] (AI presentations)",
        "PREFER FREE MCP: run 'ricet mcp-search gamma' to install the Gamma MCP (no key).\n"
        "  API key only needed for programmatic access outside MCP.\n"
        "  https://developers.gamma.app/docs/get-access → requires Gamma Pro subscription.",
        "integrations",
    ),
    (
        "CANVA_API_KEY",
        "Canva Connect API key [PAID, requires Canva Pro $13/mo]",
        "PREFER FREE MCP: Canva has a FREE MCP server (no API key needed!).\n"
        "  Setup: https://www.canva.dev/docs/apps/mcp-server/ (runs locally, zero auth).\n"
        "  Or in Claude Desktop: Settings → Connectors → Canva (OAuth, no key).\n"
        "  API key only for: https://www.canva.com/developers/ → Canva Pro required.",
        "integrations",
    ),
    (
        "GOOGLE_DRIVE_CREDENTIALS",
        "Google Drive OAuth JSON path [FREE but complex setup]",
        "PREFER FREE MCP: run 'ricet mcp-search google drive' to find Drive MCPs.\n"
        "  Manual setup requires OAuth2 credentials (NOT a simple API key!):\n"
        "  1. https://console.cloud.google.com/ → Create project\n"
        "  2. Enable 'Google Drive API'\n"
        "  3. APIs & Services → Credentials → Create OAuth client ID (Desktop app)\n"
        "  4. Download JSON → enter the file path here.",
        "integrations",
    ),
    # --- Communication: Slack (conditional) ---
    (
        "SLACK_BOT_TOKEN",
        "Slack bot token [FREE]",
        "https://api.slack.com/apps → Create App → OAuth & Permissions → Bot Token",
        "slack",
    ),
    (
        "SLACK_WEBHOOK_URL",
        "Slack incoming webhook URL [FREE]",
        "https://api.slack.com/apps → Incoming Webhooks → Add New Webhook",
        "slack",
    ),
    # --- Communication: Email / SMTP (conditional) ---
    (
        "SMTP_HOST",
        "SMTP host [FREE]",
        "Common hosts: Gmail=smtp.gmail.com | Outlook=smtp.office365.com | Yahoo=smtp.mail.yahoo.com\n"
        "  For institutional email, check with your IT department.",
        "email",
    ),
    (
        "SMTP_PORT",
        "SMTP port (usually 587 for TLS)",
        "587 works for Gmail, Outlook, and most providers. Use 465 for SSL-only.",
        "email",
    ),
    (
        "SMTP_USER",
        "SMTP username (usually your full email address)",
        "e.g. yourname@gmail.com or yourname@university.edu",
        "email",
    ),
    (
        "SMTP_PASSWORD",
        "SMTP password or app password",
        "Gmail: Do NOT use your Gmail password! Create an App Password instead:\n"
        "  https://myaccount.google.com/apppasswords → Select app → Generate.\n"
        "  Requires 2-Step Verification enabled on your Google account.\n"
        "  Outlook: Use your regular password or an app password if 2FA is on.",
        "email",
    ),
]

# Legacy aliases for backwards compatibility
CREDENTIALS_ALWAYS = [
    (var, desc)
    for var, desc, _url, cat in CREDENTIAL_REGISTRY
    if cat in ("core", "ml", "publishing", "cloud")
]
CREDENTIALS_SLACK = [
    (var, desc) for var, desc, _url, cat in CREDENTIAL_REGISTRY if cat == "slack"
]
CREDENTIALS_EMAIL = [
    (var, desc) for var, desc, _url, cat in CREDENTIAL_REGISTRY if cat == "email"
]

# Category display headers for grouped credential prompts
_CATEGORY_HEADERS: dict[str, str] = {
    "core": "Essential credentials (Enter to skip any)",
    "ml": "Machine learning & experiment tracking",
    "publishing": "Publishing platforms",
    "cloud": "Cloud & infrastructure",
    "integrations": "Optional integrations (all paid services, skip if unsure)",
    "slack": "Slack notifications",
    "email": "Email notifications (SMTP)",
}


def collect_credentials(
    answers: OnboardingAnswers,
    *,
    prompt_fn=None,
    print_fn=None,
) -> dict[str, str]:
    """Collect API credentials interactively (Enter to skip any).

    Each credential is prompted one at a time with a URL showing where to
    get it, so the flow is self-contained and guided.

    Args:
        answers: Onboarding answers (used for notification method).
        prompt_fn: Callable(prompt, default) -> str.
        print_fn: Callable(message) -> None for guidance output.

    Returns:
        Dict of env var name to value (only non-empty entries).
    """
    if prompt_fn is None:
        # Fixed: empty input returns "" (not default), so Enter = skip
        def prompt_fn(prompt: str, default: str = "") -> str:
            raw = input(f"{prompt}: ")
            return raw if raw else default

    if print_fn is None:
        print_fn = print

    # Load global credentials for pre-fill
    from core.credential_store import load_global_credentials, mask_value

    global_creds = load_global_credentials()

    credentials: dict[str, str] = {}

    # Determine which categories to ask
    active_cats = {"core", "ml", "publishing", "cloud", "integrations"}
    if answers.notification_method == "slack":
        active_cats.add("slack")
    if answers.notification_method == "email":
        active_cats.add("email")

    if global_creds:
        print_fn("  Global credentials found. Press Enter to keep existing value.")
    print_fn("  Press Enter to skip any credential you don't have yet.")

    last_cat = ""
    for var, description, how_to_url, category in CREDENTIAL_REGISTRY:
        if category not in active_cats:
            continue
        # Print category header on category change
        if category != last_cat:
            header = _CATEGORY_HEADERS.get(category, category)
            print_fn(f"\n  --- {header} ---")
            last_cat = category
        # Show guidance before each prompt
        print_fn(f"  {how_to_url}")
        # Show masked global value if available
        global_val = global_creds.get(var, "")
        if global_val:
            print_fn(f"  [global: {mask_value(global_val)}]")
        value = prompt_fn(f"{description} ({var})", "").strip()
        # Treat "skip" as empty
        if value and value.lower() != "skip":
            credentials[var] = value
        elif global_val:
            # Use global credential when user presses Enter
            credentials[var] = global_val

    return credentials


def setup_named_tunnel(
    domain: str,
    tunnel_name: str = "ricet",
    port: int = 8777,
    *,
    print_fn=None,
) -> dict:
    """Create a named Cloudflare tunnel and write ~/.cloudflared/config.yml.

    Idempotent: if the tunnel already exists it reuses it.
    Returns {"ok": True, "url": "https://<domain>", "tunnel_id": ...}
    or {"ok": False, "error": ...}.
    """
    import json
    import re

    if print_fn is None:
        print_fn = print

    cf = shutil.which("cloudflared")
    if not cf:
        return {"ok": False, "error": "cloudflared not found in PATH"}

    # 1. Create tunnel (or find existing)
    result = subprocess.run(
        [cf, "tunnel", "create", tunnel_name],
        capture_output=True, text=True,
    )
    tunnel_id: str = ""
    if result.returncode == 0:
        m = re.search(r"id\s+([\w-]{36})", result.stdout + result.stderr)
        if m:
            tunnel_id = m.group(1)
        print_fn(f"  Created tunnel '{tunnel_name}' (id: {tunnel_id or '?'})")
    elif "already exist" in (result.stderr + result.stdout).lower():
        # Reuse existing tunnel
        ls = subprocess.run(
            [cf, "tunnel", "list", "--output", "json"],
            capture_output=True, text=True,
        )
        if ls.returncode == 0:
            try:
                for t in json.loads(ls.stdout):
                    if t.get("name") == tunnel_name:
                        tunnel_id = t["id"]
                        break
            except (json.JSONDecodeError, KeyError):
                pass
        print_fn(f"  Reusing existing tunnel '{tunnel_name}' (id: {tunnel_id or '?'})")
    else:
        return {"ok": False, "error": result.stderr.strip() or "cloudflared tunnel create failed"}

    if not tunnel_id:
        return {"ok": False, "error": "Could not determine tunnel ID"}

    # 2. Route DNS
    dns_result = subprocess.run(
        [cf, "tunnel", "route", "dns", tunnel_name, domain],
        capture_output=True, text=True,
    )
    if dns_result.returncode == 0:
        print_fn(f"  DNS routed: {domain} → tunnel")
    else:
        print_fn(f"  DNS routing warning: {dns_result.stderr.strip()[:120]}")

    # 3. Write ~/.cloudflared/config.yml
    config_dir = Path.home() / ".cloudflared"
    config_dir.mkdir(parents=True, exist_ok=True)
    creds_file = config_dir / f"{tunnel_id}.json"
    config_content = (
        f"tunnel: {tunnel_id}\n"
        f"credentials-file: {creds_file}\n"
        "ingress:\n"
        f"  - hostname: {domain}\n"
        f"    service: http://localhost:{port}\n"
        "  - service: http_status:404\n"
    )
    config_path = config_dir / "config.yml"
    config_path.write_text(config_content)
    print_fn(f"  Config written: {config_path}")

    return {"ok": True, "url": f"https://{domain}", "tunnel_id": tunnel_id, "config_path": str(config_path)}


def write_env_file(project_path: Path, credentials: dict[str, str]) -> Path:
    """Write credentials to secrets/.env.

    Args:
        project_path: Root of the project.
        credentials: Dict of env var name to value.

    Returns:
        Path to the written .env file.
    """
    env_path = project_path / "secrets" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in credentials.items()]
    env_path.write_text("\n".join(lines) + "\n" if lines else "")
    logger.info("Credentials written to %s", env_path)
    return env_path


def write_mobile_env(project_path: Path, answers: "OnboardingAnswers") -> None:
    """Append mobile-specific env vars (screen session, tunnel domain) to .env."""
    env_path = project_path / "secrets" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    additions: list[str] = []
    if answers.screen_session:
        additions.append(f"RICET_SCREEN_SESSION={answers.screen_session}")
    if answers.tunnel_domain:
        additions.append(f"RICET_TUNNEL_DOMAIN={answers.tunnel_domain}")
    if not additions:
        return
    existing = env_path.read_text() if env_path.exists() else ""
    new_lines = [a for a in additions if a.split("=")[0] not in existing]
    if new_lines:
        with env_path.open("a") as f:
            f.write("\n# Mobile access\n" + "\n".join(new_lines) + "\n")
        logger.info("Mobile env vars written to %s", env_path)


def write_env_example(project_path: Path) -> Path:
    """Write secrets/.env.example template showing all possible variables.

    Args:
        project_path: Root of the project.

    Returns:
        Path to the written .env.example file.
    """
    env_example_path = project_path / "secrets" / ".env.example"
    env_example_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# {desc}\n# How to get: {url}\n{var}="
        for var, desc, url, _cat in CREDENTIAL_REGISTRY
    ]
    env_example_path.write_text("\n\n".join(lines) + "\n")
    logger.info("Example env written to %s", env_example_path)
    return env_example_path


REQUIRED_PACKAGES = {
    "typer": "typer",
    "rich": "rich",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
}


def _get_pip_prefix(run_cmd=None) -> str:
    """Return the pip command prefix using the project env's python if available.

    Reads settings to find the project environment info. If an env python is
    configured, uses ``<python> -m pip`` instead of bare ``pip``.

    Returns:
        A command prefix string, e.g. ``"/path/.venv/bin/python -m pip"`` or ``"pip"``.
    """
    try:
        settings = load_settings(Path.cwd())
        env_info = settings.get("environment", {})
        python = env_info.get("python", "")
        if python:
            return f"{python} -m pip"
    except Exception:
        pass
    return "pip"


def check_and_install_packages(
    *,
    install: bool = True,
    run_cmd=None,
) -> list[str]:
    """Check that required Python packages are importable, auto-install missing ones.

    Args:
        install: If True, attempt pip install for missing packages.
        run_cmd: Optional callable(cmd) -> subprocess.CompletedProcess override.

    Returns:
        List of packages that could not be installed (empty = all OK).
    """
    import importlib

    pip_prefix = _get_pip_prefix()

    if run_cmd is None:

        def run_cmd(cmd: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=120,
            )

    failed: list[str] = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            if not install:
                failed.append(pip_name)
                continue
            logger.info("Installing missing package: %s", pip_name)
            try:
                result = run_cmd(f"{pip_prefix} install {pip_name}")
                if result.returncode != 0:
                    # Retry with force
                    result = run_cmd(
                        f"{pip_prefix} install --force-reinstall {pip_name}"
                    )
                    if result.returncode != 0:
                        failed.append(pip_name)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                failed.append(pip_name)
    return failed


# Mapping of keyword patterns in GOAL.md to pip packages
GOAL_PACKAGE_MAP: list[tuple[list[str], list[str]]] = [
    # (keywords, packages_to_install)
    (
        ["machine learning", "ml", "neural", "deep learning", "training", "model"],
        ["numpy", "scipy", "scikit-learn", "matplotlib"],
    ),
    (
        ["torch", "pytorch", "transformer", "attention", "gpu"],
        ["torch", "torchvision"],
    ),
    (
        ["tensorflow", "keras"],
        ["tensorflow"],
    ),
    (
        ["data analysis", "dataset", "csv", "dataframe", "pandas", "tabular"],
        ["pandas", "numpy", "matplotlib"],
    ),
    (
        ["statistics", "statistical", "hypothesis", "p-value", "regression"],
        ["scipy", "statsmodels", "numpy"],
    ),
    (
        ["visualization", "plot", "figure", "chart", "graph"],
        ["matplotlib", "seaborn"],
    ),
    (
        ["nlp", "natural language", "text", "tokeniz", "language model", "llm"],
        ["transformers", "tokenizers"],
    ),
    (
        ["image", "vision", "computer vision", "cnn", "segmentation"],
        ["pillow", "opencv-python"],
    ),
    (
        ["jupyter", "notebook", "ipynb"],
        ["jupyter", "ipykernel"],
    ),
    (
        ["huggingface", "hugging face"],
        ["transformers", "datasets", "huggingface_hub"],
    ),
    (
        ["wandb", "weights and biases", "experiment tracking"],
        ["wandb"],
    ),
    (
        ["bioinformatics", "genomics", "sequence", "protein"],
        ["biopython", "numpy", "pandas"],
    ),
    (
        ["slide", "slides", "presentation", "pptx", "powerpoint", "deck"],
        ["python-pptx", "google-genai", "Pillow"],
    ),
]


def infer_packages_from_goal(
    goal_content: str,
    *,
    use_claude: bool = True,
    run_cmd=None,
) -> list[str]:
    """Infer Python packages needed based on GOAL.md content.

    When Claude CLI is available, asks Claude to analyze the goal and
    return an optimal package list (handles niche domains like spatial
    metabolomics, quantum chemistry, etc.). Falls back to keyword
    matching when Claude is unavailable.

    Args:
        goal_content: Text content of GOAL.md.
        use_claude: Whether to attempt Claude-based inference.
        run_cmd: Optional callable for testing.

    Returns:
        List of pip package names (deduplicated, sorted).
    """
    if use_claude and len(goal_content.strip()) > 50:
        result = _infer_packages_via_claude(goal_content, run_cmd=run_cmd)
        if result:
            try:
                from core.knowledge import log_decision

                log_decision(
                    f"inferred {len(result)} packages via Claude",
                    "Claude analyzed GOAL.md for domain-specific dependencies",
                )
            except Exception:
                pass  # Never break the main flow for logging
            return result

    # Fallback: keyword matching
    packages = _infer_packages_via_keywords(goal_content)

    try:
        from core.knowledge import log_decision

        log_decision(
            f"inferred {len(packages)} packages via keyword matching",
            "Claude unavailable or goal too short, used keyword fallback",
        )
    except Exception:
        pass  # Never break the main flow for logging

    return packages


def _infer_packages_via_claude(
    goal_content: str,
    *,
    run_cmd=None,
) -> list[str]:
    """Ask Claude to analyze GOAL.md and return needed pip packages.

    Args:
        goal_content: Text content of GOAL.md.
        run_cmd: Optional callable for testing.

    Returns:
        List of pip package names, or empty list if Claude unavailable.
    """
    import json as _json

    if run_cmd is None:

        def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

    prompt = (
        "You are a Python dependency advisor. Read this research project description "
        "and return ONLY a JSON array of pip package names that would be needed. "
        "Include domain-specific packages (e.g. squidpy for spatial transcriptomics, "
        "rdkit for chemistry, astropy for astronomy). Be precise - only packages "
        "available on PyPI. No explanations, just the JSON array.\n\n"
        f"Project description:\n{goal_content[:3000]}"
    )

    try:
        result = run_cmd(["claude", "-p", prompt, "--output-format", "json"])
        if result.returncode != 0:
            logger.debug("Claude package inference failed (exit %d)", result.returncode)
            return []

        output = result.stdout.strip()
        # Try to parse JSON array from output
        # Claude may wrap it in markdown code blocks
        if "```" in output:
            # Extract content between code fences
            parts = output.split("```")
            for part in parts:
                cleaned = part.strip().removeprefix("json").strip()
                if cleaned.startswith("["):
                    output = cleaned
                    break

        packages = _json.loads(output)
        if isinstance(packages, list):
            # Filter to strings only, deduplicate
            return sorted(set(p for p in packages if isinstance(p, str) and p))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("Claude not available for package inference: %s", exc)
    except (_json.JSONDecodeError, ValueError) as exc:
        logger.debug("Could not parse Claude package response: %s", exc)

    return []


def _infer_packages_via_keywords(goal_content: str) -> list[str]:
    """Fallback keyword-based package inference.

    Args:
        goal_content: Text content of GOAL.md.

    Returns:
        List of pip package names (deduplicated, sorted).
    """
    goal_lower = goal_content.lower()
    packages: set[str] = set()

    for keywords, pkgs in GOAL_PACKAGE_MAP:
        if any(kw in goal_lower for kw in keywords):
            packages.update(pkgs)

    return sorted(packages)


def _suggest_alternative_package(pkg: str) -> str | None:
    """Ask Claude for an alternative when pip install fails."""
    from core.claude_helper import call_claude

    prompt = (
        f"pip install {pkg} failed. "
        "Suggest one alternative pip package name (just the name, nothing else)."
    )
    result = call_claude(prompt)
    if result:
        # Take first word, strip quotes
        word = result.strip().split()[0].strip("'\"")
        if word and word != pkg:
            return word
    return None


def install_inferred_packages(
    packages: list[str],
    *,
    run_cmd=None,
) -> tuple[list[str], list[str]]:
    """Install a list of pip packages, returning (installed, failed).

    Args:
        packages: List of pip package names.
        run_cmd: Optional callable(cmd) -> subprocess.CompletedProcess.

    Returns:
        Tuple of (successfully_installed, failed_to_install).
    """
    import importlib

    pip_prefix = _get_pip_prefix()

    if run_cmd is None:

        def run_cmd(cmd: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=300,
            )

    installed: list[str] = []
    failed: list[str] = []

    for pkg in packages:
        # Normalize import name: opencv-python → cv2, pillow → PIL, etc.
        import_map = {
            "opencv-python": "cv2",
            "pillow": "PIL",
            "scikit-learn": "sklearn",
            "python-dotenv": "dotenv",
            "pyyaml": "yaml",
            "huggingface_hub": "huggingface_hub",
            "biopython": "Bio",
        }
        import_name = import_map.get(pkg, pkg.replace("-", "_"))

        try:
            importlib.import_module(import_name)
            # Already installed
            continue
        except ImportError:
            pass

        logger.info("Installing inferred package: %s", pkg)
        try:
            result = run_cmd(f"{pip_prefix} install {pkg}")
            if result.returncode == 0:
                installed.append(pkg)
            else:
                # Ask Claude for alternative
                alt = _suggest_alternative_package(pkg)
                if alt and alt != pkg:
                    logger.info("Trying alternative: %s", alt)
                    result = run_cmd(f"{pip_prefix} install {alt}")
                    if result.returncode == 0:
                        installed.append(alt)
                        continue
                failed.append(pkg)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            failed.append(pkg)

    return installed, failed


def ensure_package(
    pip_name: str,
    import_name: str | None = None,
    *,
    run_cmd=None,
) -> bool:
    """Ensure a Python package is importable, installing it on demand if missing.

    Designed to be called at any point during a session — not just at startup.
    Agents can call this when they discover they need a package.

    Args:
        pip_name: The pip package name (e.g. "pandas").
        import_name: The Python import name if different (e.g. "cv2" for
                     "opencv-python"). If None, derives from pip_name.
        run_cmd: Optional callable(cmd) -> subprocess.CompletedProcess.

    Returns:
        True if the package is importable after this call.
    """
    import importlib

    if import_name is None:
        _import_map = {
            "opencv-python": "cv2",
            "pillow": "PIL",
            "scikit-learn": "sklearn",
            "python-dotenv": "dotenv",
            "pyyaml": "yaml",
            "biopython": "Bio",
        }
        import_name = _import_map.get(pip_name, pip_name.replace("-", "_"))

    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        pass

    pip_prefix = _get_pip_prefix()

    if run_cmd is None:

        def run_cmd(cmd: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=300,
            )

    logger.info("Runtime install: %s", pip_name)
    try:
        result = run_cmd(f"{pip_prefix} install {pip_name}")
        if result.returncode == 0:
            # Clear import caches
            importlib.invalidate_caches()
            try:
                importlib.import_module(import_name)
                return True
            except ImportError:
                pass
        # Retry with force
        result = run_cmd(f"{pip_prefix} install --force-reinstall {pip_name}")
        if result.returncode == 0:
            importlib.invalidate_caches()
            try:
                importlib.import_module(import_name)
                return True
            except ImportError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    logger.warning("Failed to install %s", pip_name)
    return False


def generate_goal_todos(goal_content: str, *, run_cmd=None) -> str:
    """Generate goal-specific TODO items from GOAL.md content.

    Calls Claude CLI to produce 8-12 actionable TODO items tailored to the
    research goal.  Falls back to generic TODO items if Claude is unavailable
    or the goal text is too short.

    Args:
        goal_content: Raw text of GOAL.md.
        run_cmd: Optional callable(cmd: list[str]) -> subprocess.CompletedProcess
                 override for testing.

    Returns:
        Markdown string with checkbox TODO items.
    """
    generic_fallback = (
        "- [ ] Literature review and background research\n"
        "- [ ] Set up data pipeline and preprocessing\n"
        "- [ ] Implement baseline approach\n"
        "- [ ] Run initial experiments and validate pipeline\n"
        "- [ ] Iterate on methodology based on results\n"
        "- [ ] Run full-scale experiments\n"
        "- [ ] Analyze results and generate figures\n"
        "- [ ] Write paper draft\n"
    )

    if not goal_content or len(goal_content.strip()) < 50:
        return generic_fallback

    if run_cmd is None:

        def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

    prompt = (
        "Given this research goal, generate 8-12 specific actionable TODO items "
        "as a markdown checklist. Be concrete and specific to this goal, not generic. "
        "Return ONLY the checklist lines, nothing else. Each line must start with "
        "'- [ ] '.\n\n"
        f"Goal:\n{goal_content[:3000]}"
    )

    try:
        result = run_cmd(["claude", "-p", prompt])
        if result.returncode != 0:
            logger.debug("Claude TODO generation failed (exit %d)", result.returncode)
            return generic_fallback

        output = result.stdout.strip()
        # Extract only lines that look like checklist items
        lines = [
            line.strip()
            for line in output.splitlines()
            if line.strip().startswith("- [ ]")
        ]
        if len(lines) >= 4:
            return "\n".join(lines) + "\n"
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("Claude not available for TODO generation: %s", exc)

    return generic_fallback


def generate_goal_folders(goal_content: str, *, run_cmd=None) -> list[str]:
    """Suggest additional project-specific folders based on GOAL.md content.

    Calls Claude CLI to recommend extra directories that suit the research
    goal (e.g. ``simulations/``, ``datasets/``, ``models/``).  Returns an
    empty list when Claude is unavailable or the goal text is too short.

    Args:
        goal_content: Raw text of GOAL.md.
        run_cmd: Optional callable(cmd: list[str]) -> subprocess.CompletedProcess
                 override for testing.

    Returns:
        List of additional folder paths to create (relative to project root).
    """
    if not goal_content or len(goal_content.strip()) < 50:
        return []

    if run_cmd is None:

        def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

    prompt = (
        "Given this research goal, suggest 3-6 additional project-specific folder "
        "names that would be useful. Return ONLY folder names, one per line, no "
        "explanation. Use lowercase with hyphens. Do NOT include standard folders "
        "like src/, tests/, docs/, config/, reference/, uploads/, state/, secrets/.\n\n"
        f"Goal:\n{goal_content[:3000]}"
    )

    try:
        result = run_cmd(["claude", "-p", prompt])
        if result.returncode != 0:
            logger.debug("Claude folder suggestion failed (exit %d)", result.returncode)
            return []

        output = result.stdout.strip()
        folders: list[str] = []
        for line in output.splitlines():
            cleaned = line.strip().strip("-* ").strip("/")
            # Basic validation: no spaces, no dots, reasonable length
            if (
                cleaned
                and len(cleaned) < 50
                and " " not in cleaned
                and ".." not in cleaned
                and not cleaned.startswith(".")
            ):
                folders.append(cleaned)
        return folders[:6]
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("Claude not available for folder suggestion: %s", exc)

    return []


def validate_goal_content(content: str, min_chars: int = 200) -> bool:
    """Check that GOAL.md has real user content (not just template boilerplate).

    Strips HTML comments, headings, placeholder text, and whitespace before
    checking whether at least *min_chars* characters of real prose remain.

    Args:
        content: Raw text of GOAL.md.
        min_chars: Minimum characters of real content required.

    Returns:
        True if sufficient content is present.
    """
    import re

    text = content
    # Strip HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Strip markdown headings
    text = re.sub(r"^#+\s.*$", "", text, flags=re.MULTILINE)
    # Strip checkbox placeholders
    text = re.sub(r"^- \[ \]\s.*$", "", text, flags=re.MULTILINE)
    # Strip common placeholder phrases
    for phrase in [
        "User provides during init",
        "WRITE YOUR PROJECT DESCRIPTION HERE",
        "See GOAL.md",
        "Criterion 1",
        "Criterion 2",
        "e.g., 3 months",
    ]:
        text = text.replace(phrase, "")
    # Strip remaining whitespace
    text = text.strip()
    is_valid = len(text) >= min_chars

    # Log the validation outcome
    try:
        from core.knowledge import log_decision

        if is_valid:
            log_decision(
                "GOAL.md validated as sufficient",
                f"{len(text)} chars of real content (min {min_chars})",
            )
        else:
            log_decision(
                "GOAL.md flagged as insufficient",
                f"only {len(text)} chars of real content (min {min_chars})",
            )
    except Exception:
        pass  # Never break the main flow for logging

    return is_valid


def load_settings(project_path: Path) -> dict:
    """Load project settings from config/settings.yml.

    Args:
        project_path: Root of the project.

    Returns:
        Settings dict, or empty dict if not found.
    """
    settings_path = project_path / "config" / "settings.yml"
    if not settings_path.exists():
        return {}
    return yaml.safe_load(settings_path.read_text()) or {}


def generate_goal_milestones(goal_text: str) -> list[str]:
    """Generate project milestones from GOAL.md content.

    Tries Claude CLI first, falls back to keyword-based generation.

    Args:
        goal_text: Raw text from GOAL.md.

    Returns:
        List of milestone strings (up to 10). Empty list if goal_text
        is too short to be meaningful.
    """
    if not goal_text or len(goal_text.strip()) < 50:
        return []

    # Try Claude
    from core.claude_helper import call_claude

    prompt = (
        "Given this research project goal, generate 5-8 high-level milestones "
        "as a simple numbered list. Each milestone should be one line, actionable, "
        "and in logical order.\n\n"
        f"Goal:\n{goal_text[:2000]}"
    )
    result = call_claude(prompt)
    if result:
        lines = [
            l.strip().lstrip("0123456789.-) ")
            for l in result.strip().splitlines()
            if l.strip()
        ]
        milestones = [l for l in lines if len(l) > 10]
        if milestones:
            return milestones[:10]

    # Keyword fallback
    return _generate_milestones_keywords(goal_text)


def _generate_milestones_keywords(goal_text: str) -> list[str]:
    """Keyword-based milestone generation.

    Args:
        goal_text: Raw text from GOAL.md.

    Returns:
        List of milestone strings.
    """
    milestones = [
        "Literature review and background research",
        "Set up data pipeline and preprocessing",
        "Implement baseline approach",
        "Run initial experiments and validate pipeline",
        "Iterate on methodology based on results",
        "Run full-scale experiments",
        "Analyze results and generate figures",
        "Write paper draft",
    ]
    text_lower = goal_text.lower()
    if "model" in text_lower or "train" in text_lower:
        milestones.insert(3, "Design and implement model architecture")
    if "dataset" in text_lower:
        milestones.insert(1, "Acquire and explore dataset")
    return milestones[:10]


# ---------------------------------------------------------------------------
# Docker setup for overnight mode (called during ricet init)
# ---------------------------------------------------------------------------


def setup_docker_for_overnight(
    project_path: Path,
    *,
    print_fn=None,
) -> dict:
    """Check Docker availability, build image, and test the setup during init.

    This ensures that everything is ready for overnight mode before the user
    finishes onboarding. Non-technical users get clear guidance if Docker is
    missing.

    Args:
        project_path: Root of the project being initialised.
        print_fn: Optional callable(message) for output. Uses print() if None.

    Returns:
        dict with keys:
            "docker_available" (bool) - Docker is installed and running
            "image_built" (bool)      - ricet:latest image exists or was built
            "deps_installed" (bool)   - project deps pre-installed in container
            "test_passed" (bool)      - smoke test passed
            "skipped" (bool)          - Docker not available, setup was skipped
    """
    from core.devops import (
        build_ricet_image,
        ensure_docker_ready,
        get_docker_install_instructions,
        prepare_docker_environment,
        test_docker_setup,
    )

    if print_fn is None:
        print_fn = print

    result = {
        "docker_available": False,
        "image_built": False,
        "deps_installed": False,
        "test_passed": False,
        "skipped": False,
    }

    # Step 1: Check Docker availability
    docker_status = ensure_docker_ready()

    if not docker_status["docker_installed"]:
        print_fn(
            "\n  Docker is NOT installed on this system.\n"
            "  Docker is required for safe overnight mode (autonomous runs).\n"
        )
        print_fn("  " + get_docker_install_instructions().replace("\n", "\n  "))
        print_fn(
            "\n  You can install Docker later and run 'ricet init' again,\n"
            "  or install it now and the setup will continue.\n"
            "  Overnight mode will NOT work until Docker is installed."
        )
        result["skipped"] = True
        return result

    if not docker_status["daemon_running"]:
        # Try to start the daemon without sudo (rootless Docker, user systemd)
        import platform as _plat

        _started = False
        if _plat.system() == "Linux":
            print_fn("  Docker daemon not running — attempting to start...")
            # Try user-level systemd first, then rootless dockerd
            for start_cmd in (
                ["systemctl", "--user", "start", "docker"],
                ["dockerd-rootless-setuptool.sh", "install"],
            ):
                try:
                    sr = subprocess.run(
                        start_cmd, capture_output=True, timeout=30
                    )
                    if sr.returncode == 0:
                        import time as _time

                        _time.sleep(3)
                        docker_status = ensure_docker_ready()
                        if docker_status["daemon_running"]:
                            print_fn("  Docker daemon started successfully.")
                            _started = True
                            break
                except Exception:
                    pass
        if not _started:
            print_fn(
                "\n  Docker is installed but the daemon is not running.\n"
                "  Ask your sysadmin to start it, or use rootless Docker:\n"
                "  https://docs.docker.com/engine/security/rootless/"
            )
            result["docker_available"] = False
            result["skipped"] = True
            return result

    result["docker_available"] = True

    # Step 2: Build or verify the ricet image
    if docker_status["image_available"]:
        print_fn("  Docker image 'ricet:latest' already available.")
        result["image_built"] = True
    else:
        print_fn(
            "  Building Docker image 'ricet:latest' (this may take 10-20 minutes)..."
        )
        if build_ricet_image():
            print_fn("  Docker image built successfully.")
            result["image_built"] = True
        else:
            print_fn(
                "  WARNING: Docker image build failed. "
                "You can retry later with: docker build -t ricet:latest docker/"
            )
            return result

    # Step 3: Pre-install project dependencies inside the container
    print_fn("  Installing project dependencies inside Docker container...")
    if prepare_docker_environment(project_path):
        print_fn("  Dependencies installed in container.")
        result["deps_installed"] = True
    else:
        print_fn("  Some dependencies could not be installed (non-fatal).")

    # Step 4: Smoke test
    print_fn("  Running Docker smoke test...")
    if test_docker_setup():
        print_fn("  Docker setup verified - overnight mode is ready!")
        result["test_passed"] = True
    else:
        print_fn(
            "  WARNING: Docker smoke test failed. "
            "Overnight mode may not work correctly."
        )

    return result
