"""Tests for environment management."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.environment import (
    SystemInfo,
    create_project_env,
    discover_system,
    generate_requirements_txt,
    generate_system_md,
    populate_encyclopedia_env,
)


def test_discover_system():
    info = discover_system()
    assert info.os != ""
    assert info.python_version != ""
    assert info.ram_gb >= 0


def test_discover_system_has_cpu():
    info = discover_system()
    assert info.cpu != "" or info.os != ""  # At least one populated


def test_generate_system_md():
    info = SystemInfo(
        os="Linux",
        os_version="6.0",
        python_version="3.11.5",
        cpu="x86_64",
        gpu="NVIDIA RTX 4090",
        ram_gb=32.0,
        conda_available=True,
        docker_available=False,
    )
    md = generate_system_md(info)
    assert "Linux" in md
    assert "3.11.5" in md
    assert "RTX 4090" in md
    assert "32.0 GB" in md
    assert "Conda" in md


def test_generate_system_md_no_gpu():
    info = SystemInfo(os="Linux", python_version="3.11.0")
    md = generate_system_md(info)
    assert "None detected" in md


def test_generate_system_md_auto():
    md = generate_system_md()
    assert "# System Environment" in md
    assert "Python" in md


def test_system_info_defaults():
    info = SystemInfo()
    assert info.os == ""
    assert info.ram_gb == 0.0
    assert info.conda_available is False


# --- Tests for create_project_env ---


def test_create_project_env_conda_success(tmp_path):
    """create_project_env uses conda when available and it succeeds."""
    mock_run = MagicMock()
    # First call: conda create succeeds
    mock_run.return_value = MagicMock(
        stdout="/home/user/miniconda3/envs/ricet-myproj/bin/python\n",
        returncode=0,
    )

    def fake_which(tool):
        return "/usr/bin/conda" if tool == "conda" else None

    with patch("core.environment.shutil.which", side_effect=fake_which):
        result = create_project_env("myproj", tmp_path, run_cmd=mock_run)

    assert result["type"] == "conda"
    assert result["name"] == "ricet-myproj"
    assert "python" in result["python"]
    # Should have called conda create and then which python
    assert mock_run.call_count == 2
    first_call_args = mock_run.call_args_list[0][0][0]
    assert first_call_args[0] == "conda"
    assert "create" in first_call_args


def test_create_project_env_mamba_success(tmp_path):
    """create_project_env prefers mamba over conda when both are available."""
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(
        stdout="/home/user/mambaforge/envs/ricet-myproj/bin/python\n",
        returncode=0,
    )

    def fake_which(tool):
        return f"/usr/bin/{tool}" if tool in ("mamba", "conda") else None

    with patch("core.environment.shutil.which", side_effect=fake_which):
        result = create_project_env("myproj", tmp_path, run_cmd=mock_run)

    assert result["type"] == "mamba"
    assert result["name"] == "ricet-myproj"


def test_create_project_env_venv_fallback(tmp_path):
    """create_project_env falls back to venv when no conda/mamba available."""
    with patch("core.environment.shutil.which", return_value=None):
        result = create_project_env("myproj", tmp_path)

    assert result["type"] == "venv"
    assert result["name"] == ".venv"
    venv_path = tmp_path / ".venv"
    assert venv_path.exists()
    assert result["path"] == str(venv_path)
    assert result["python"] == str(venv_path / "bin" / "python")


def test_create_project_env_conda_fails_falls_to_venv(tmp_path):
    """If conda create fails, falls back to venv."""
    mock_run = MagicMock(side_effect=Exception("conda create failed"))

    with patch("core.environment.shutil.which", return_value="/usr/bin/conda"):
        result = create_project_env("myproj", tmp_path, run_cmd=mock_run)

    assert result["type"] == "venv"
    assert (tmp_path / ".venv").exists()


# --- Tests for generate_requirements_txt ---


def test_generate_requirements_txt_success(tmp_path):
    """generate_requirements_txt writes pip freeze output."""
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(
        stdout="numpy==1.24.0\npandas==2.0.0\n",
        returncode=0,
    )
    env_info = {"python": "/some/python", "type": "venv", "name": ".venv"}

    req_path = generate_requirements_txt(tmp_path, env_info, run_cmd=mock_run)

    assert req_path == tmp_path / "requirements.txt"
    assert req_path.exists()
    content = req_path.read_text()
    assert "numpy==1.24.0" in content
    assert "pandas==2.0.0" in content


def test_generate_requirements_txt_failure(tmp_path):
    """generate_requirements_txt writes fallback comment on error."""
    mock_run = MagicMock(side_effect=Exception("pip not found"))
    env_info = {"python": "/nonexistent/python", "type": "venv", "name": ".venv"}

    req_path = generate_requirements_txt(tmp_path, env_info, run_cmd=mock_run)

    assert req_path.exists()
    content = req_path.read_text()
    assert "Auto-generated by ricet" in content


# --- Tests for populate_encyclopedia_env ---


def test_populate_encyclopedia_env(tmp_path):
    """populate_encyclopedia_env replaces placeholders in ENCYCLOPEDIA.md."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    enc_path = knowledge_dir / "ENCYCLOPEDIA.md"
    enc_path.write_text(
        "# Encyclopedia\n\n"
        "## Environment\n"
        "- Conda environment: TBD\n"
        "- Python version: TBD\n"
        "- Key packages: TBD\n"
        "\n## Other\n"
    )

    env_info = {"type": "venv", "name": ".venv", "python": "/tmp/.venv/bin/python"}
    sys_info = SystemInfo(
        os="Linux",
        os_version="6.0",
        python_version="3.11.5",
        cpu="x86_64",
        ram_gb=16.0,
        conda_available=False,
        docker_available=True,
    )

    populate_encyclopedia_env(tmp_path, env_info, sys_info)

    content = enc_path.read_text()
    assert "**Environment type**: venv" in content
    assert "**Environment name**: .venv" in content
    assert "**Python version**: 3.11.5" in content
    assert "**RAM**: 16.0 GB" in content
    assert "**Docker**: Available" in content


def test_populate_encyclopedia_env_no_file(tmp_path):
    """populate_encyclopedia_env does nothing if ENCYCLOPEDIA.md does not exist."""
    env_info = {"type": "venv", "name": ".venv", "python": "/tmp/python"}
    # Should not raise
    populate_encyclopedia_env(tmp_path, env_info)
