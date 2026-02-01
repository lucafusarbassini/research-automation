"""Environment management: system discovery, conda environments, system docs."""

import logging
import platform
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
    lines.append(f"- **Docker**: {'Available' if info.docker_available else 'Not found'}")

    return "\n".join(lines)
