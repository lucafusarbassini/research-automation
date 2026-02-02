"""Environment management: system discovery, conda environments, system docs."""

import logging
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SystemInfo:
    os: str = ""
    os_version: str = ""
    python_version: str = ""
    cpu: str = ""
    gpu: str = ""
    ram_gb: float = 0.0
    conda_available: bool = False
    docker_available: bool = False


def discover_system() -> SystemInfo:
    """Discover the current system's capabilities.

    Returns:
        SystemInfo with detected hardware and software.
    """
    info = SystemInfo()
    info.os = platform.system()
    info.os_version = platform.version()
    info.python_version = platform.python_version()
    info.cpu = platform.processor() or platform.machine()

    # RAM
    try:
        import os

        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if pages > 0 and page_size > 0:
                info.ram_gb = round((pages * page_size) / (1024**3), 1)
    except (ValueError, OSError):
        pass

    # GPU
    info.gpu = _detect_gpu()

    # Conda
    info.conda_available = shutil.which("conda") is not None

    # Docker
    info.docker_available = shutil.which("docker") is not None

    return info


def _detect_gpu() -> str:
    """Detect GPU using nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            gpus = result.stdout.strip().splitlines()
            return ", ".join(gpus)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def create_conda_env(
    name: str,
    python_version: str = "3.11",
    packages: list[str] | None = None,
) -> bool:
    """Create a conda environment for the project.

    Args:
        name: Environment name.
        python_version: Python version to install.
        packages: Additional packages to install.

    Returns:
        True if environment was created successfully.
    """
    if not shutil.which("conda"):
        logger.error("Conda not found on PATH")
        return False

    cmd = ["conda", "create", "-n", name, f"python={python_version}", "-y"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("Created conda environment: %s", name)
    except subprocess.CalledProcessError as e:
        logger.error("Failed to create conda env: %s", e.stderr)
        return False

    if packages:
        install_cmd = ["conda", "run", "-n", name, "pip", "install"] + packages
        try:
            subprocess.run(install_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.warning("Package installation failed: %s", e.stderr)

    return True


def generate_system_md(info: Optional[SystemInfo] = None) -> str:
    """Generate a Markdown summary of the system environment.

    Args:
        info: SystemInfo to render. Discovers current system if None.

    Returns:
        Markdown-formatted system description.
    """
    if info is None:
        info = discover_system()

    lines = [
        "# System Environment",
        "",
        f"- **OS**: {info.os} {info.os_version}",
        f"- **Python**: {info.python_version}",
        f"- **CPU**: {info.cpu}",
        f"- **RAM**: {info.ram_gb} GB",
    ]

    if info.gpu:
        lines.append(f"- **GPU**: {info.gpu}")
    else:
        lines.append("- **GPU**: None detected")

    lines.append(f"- **Conda**: {'Available' if info.conda_available else 'Not found'}")
    lines.append(
        f"- **Docker**: {'Available' if info.docker_available else 'Not found'}"
    )

    return "\n".join(lines)


def _default_run(cmd):
    """Default subprocess runner for environment functions."""
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _get_conda_python(env_name, tool, run_cmd):
    """Get python path for a conda env."""
    try:
        result = run_cmd([tool, "run", "-n", env_name, "which", "python"])
        return result.stdout.strip() if hasattr(result, "stdout") and result.stdout else f"conda run -n {env_name} python"
    except Exception:
        return f"conda run -n {env_name} python"


def create_project_env(
    project_name: str,
    project_root: Path,
    python_version: str = "3.11",
    *,
    run_cmd=None,
) -> dict:
    """Create an isolated Python environment for the project.

    Strategy: Try conda/mamba first, fall back to venv.
    Returns dict with 'type' ('conda'|'mamba'|'venv'), 'name', 'path', 'python'.
    """
    _run = run_cmd or _default_run

    # Try mamba first (faster), then conda, then venv
    for tool in ("mamba", "conda"):
        if shutil.which(tool):
            env_name = f"ricet-{project_name}"
            cmd = [tool, "create", "-n", env_name, f"python={python_version}", "-y"]
            try:
                _run(cmd)
                python_path = _get_conda_python(env_name, tool, _run)
                return {"type": tool, "name": env_name, "path": "", "python": python_path}
            except Exception:
                continue

    # Fallback: venv
    import venv as _venv

    venv_path = project_root / ".venv"
    _venv.create(str(venv_path), with_pip=True)
    python_path = str(venv_path / "bin" / "python")
    return {"type": "venv", "name": ".venv", "path": str(venv_path), "python": python_path}


def generate_requirements_txt(project_root: Path, env_info: dict, *, run_cmd=None) -> Path:
    """Generate requirements.txt from the project environment."""
    _run = run_cmd or _default_run
    req_path = project_root / "requirements.txt"

    python = env_info.get("python", "python")
    try:
        result = _run([python, "-m", "pip", "freeze"])
        req_path.write_text(result.stdout if hasattr(result, "stdout") and result.stdout else "")
    except Exception:
        req_path.write_text("# Auto-generated by ricet\n# Run: pip freeze > requirements.txt\n")

    return req_path


def populate_encyclopedia_env(project_root: Path, env_info: dict, sys_info: SystemInfo = None):
    """Write environment info to encyclopedia."""
    if sys_info is None:
        sys_info = discover_system()

    enc_path = project_root / "knowledge" / "ENCYCLOPEDIA.md"
    if not enc_path.exists():
        return

    content = enc_path.read_text()
    env_block = (
        f"- **Environment type**: {env_info['type']}\n"
        f"- **Environment name**: {env_info['name']}\n"
        f"- **Python path**: {env_info['python']}\n"
        f"- **Python version**: {sys_info.python_version}\n"
        f"- **OS**: {sys_info.os} {sys_info.os_version}\n"
        f"- **CPU**: {sys_info.cpu}\n"
        f"- **RAM**: {sys_info.ram_gb} GB\n"
        f"- **GPU**: {sys_info.gpu or 'None detected'}\n"
        f"- **Conda**: {'Available' if sys_info.conda_available else 'Not found'}\n"
        f"- **Docker**: {'Available' if sys_info.docker_available else 'Not found'}\n"
    )

    # Replace placeholder lines
    content = re.sub(
        r"- Conda environment:.*\n- Python version:.*\n- Key packages:.*",
        env_block.strip(),
        content,
    )
    enc_path.write_text(content)
