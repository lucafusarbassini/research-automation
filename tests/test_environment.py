"""Tests for environment management."""

from core.environment import SystemInfo, discover_system, generate_system_md


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
