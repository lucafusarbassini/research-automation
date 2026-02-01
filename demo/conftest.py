"""Shared fixtures for the research-automation demo test suite."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture
def demo_project_path(tmp_path):
    """Create a temporary project directory with standard knowledge and config files.

    Populates:
        knowledge/GOAL.md
        knowledge/CONSTRAINTS.md
        state/TODO.md
        config/settings.yml
    """
    # knowledge/
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    (knowledge_dir / "GOAL.md").write_text(
        "# Project Goal\n\n"
        "<!-- User provides during init -->\n\n"
        "## Success Criteria\n\n"
        "- [ ] Criterion 1\n"
        "- [ ] Criterion 2\n\n"
        "## Timeline\n\n"
        "<!-- e.g., 3 months -->\n"
    )

    (knowledge_dir / "CONSTRAINTS.md").write_text(
        "# Constraints\n\n"
        "- Compute: local-cpu\n"
        "- Budget: minimal\n"
    )

    # knowledge/ENCYCLOPEDIA.md (needed by knowledge module)
    (knowledge_dir / "ENCYCLOPEDIA.md").write_text(
        "# Project Encyclopedia\n\n"
        "## Tricks\n"
        "<!-- auto-populated -->\n\n"
        "## Decisions\n"
        "<!-- auto-populated -->\n\n"
        "## What Works\n"
        "<!-- auto-populated -->\n\n"
        "## What Doesn't Work\n"
        "<!-- auto-populated -->\n"
    )

    # state/
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    (state_dir / "TODO.md").write_text(
        "# TODO\n\n"
        "- [ ] Set up environment\n"
        "- [ ] Run first experiment\n"
    )

    # config/
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    settings = {
        "project": {
            "name": "demo-project",
            "type": "ml-research",
            "created": "2026-01-01T00:00:00",
        },
        "compute": {
            "type": "local-cpu",
            "gpu": "",
        },
        "notifications": {
            "enabled": False,
            "method": "none",
        },
        "credentials": {},
    }
    (config_dir / "settings.yml").write_text(
        yaml.dump(settings, default_flow_style=False, sort_keys=False)
    )

    return tmp_path


@pytest.fixture
def mock_subprocess():
    """Patch subprocess.run to return a successful CompletedProcess."""
    fake_result = subprocess.CompletedProcess(
        args=["fake"],
        returncode=0,
        stdout="ok\n",
        stderr="",
    )
    with patch("subprocess.run", return_value=fake_result) as mocked:
        yield mocked


@pytest.fixture
def mock_prompt_fn():
    """Return a prompt_fn callable that provides canned onboarding answers.

    The mapping covers every prompt asked by core.onboarding.collect_answers.
    """
    canned = {
        "What is the main goal of this project?": "Train a ResNet on CIFAR-10 to 95% accuracy",
        "Project type": "ml-research",
        "GitHub repository URL": "https://github.com/demo/repo",
        "Success criteria": "accuracy >= 95%, training time < 1h",
        "Target completion date": "2026-06-01",
        "Compute resources": "local-gpu",
        "GPU name": "RTX 4090",
        "Notification method": "none",
        "Target journal or conference": "NeurIPS",
        "Do you need a web dashboard?": "no",
        "Do you need mobile access?": "yes",
    }

    def _prompt_fn(prompt: str, default: str = "") -> str:
        for key, value in canned.items():
            if key.lower() in prompt.lower():
                return value
        return default

    return _prompt_fn
