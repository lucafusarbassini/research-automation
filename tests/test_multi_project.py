"""Tests for multi-project handling module."""

import json
from pathlib import Path

import pytest

from core.multi_project import (
    ProjectRegistry,
    get_active_project,
    list_projects,
    register_project,
    run_task_in_project,
    switch_project,
    sync_knowledge_across,
)


@pytest.fixture
def registry(tmp_path: Path) -> ProjectRegistry:
    """Create a ProjectRegistry backed by a temp file."""
    registry_file = tmp_path / "projects.json"
    return ProjectRegistry(registry_file=registry_file)


@pytest.fixture
def populated_registry(registry: ProjectRegistry, tmp_path: Path) -> ProjectRegistry:
    """Registry with two projects already registered."""
    p1 = tmp_path / "project_alpha"
    p1.mkdir()
    p2 = tmp_path / "project_beta"
    p2.mkdir()
    registry.register_project("alpha", p1, project_type="research")
    registry.register_project("beta", p2, project_type="website")
    return registry


# ---------- Registration ----------


class TestRegisterProject:
    def test_register_creates_entry(self, registry: ProjectRegistry, tmp_path: Path):
        proj_dir = tmp_path / "my_project"
        proj_dir.mkdir()
        result = registry.register_project(
            "my_project", proj_dir, project_type="research"
        )
        assert result["name"] == "my_project"
        assert result["project_type"] == "research"
        assert result["path"] == str(proj_dir)

    def test_register_persists_to_disk(self, registry: ProjectRegistry, tmp_path: Path):
        proj_dir = tmp_path / "persist_test"
        proj_dir.mkdir()
        registry.register_project("persist_test", proj_dir)
        data = json.loads(registry.registry_file.read_text())
        assert any(p["name"] == "persist_test" for p in data["projects"])

    def test_register_duplicate_updates(
        self, registry: ProjectRegistry, tmp_path: Path
    ):
        d1 = tmp_path / "v1"
        d1.mkdir()
        d2 = tmp_path / "v2"
        d2.mkdir()
        registry.register_project("dup", d1)
        registry.register_project("dup", d2)
        projects = registry.list_projects()
        names = [p["name"] for p in projects]
        assert names.count("dup") == 1
        assert projects[0]["path"] == str(d2)

    def test_register_nonexistent_path_raises(
        self, registry: ProjectRegistry, tmp_path: Path
    ):
        with pytest.raises(FileNotFoundError):
            registry.register_project("ghost", tmp_path / "nonexistent")


# ---------- Listing ----------


class TestListProjects:
    def test_list_empty(self, registry: ProjectRegistry):
        assert registry.list_projects() == []

    def test_list_returns_all(self, populated_registry: ProjectRegistry):
        projects = populated_registry.list_projects()
        assert len(projects) == 2
        names = {p["name"] for p in projects}
        assert names == {"alpha", "beta"}


# ---------- Switching ----------


class TestSwitchProject:
    def test_switch_sets_active(self, populated_registry: ProjectRegistry):
        path = populated_registry.switch_project("beta")
        active = populated_registry.get_active_project()
        assert active["name"] == "beta"
        assert Path(active["path"]) == path

    def test_switch_unknown_raises(self, populated_registry: ProjectRegistry):
        with pytest.raises(KeyError):
            populated_registry.switch_project("nonexistent")


# ---------- Active project ----------


class TestGetActiveProject:
    def test_no_active_initially(self, registry: ProjectRegistry):
        with pytest.raises(RuntimeError):
            registry.get_active_project()

    def test_active_after_register_first(
        self, registry: ProjectRegistry, tmp_path: Path
    ):
        proj = tmp_path / "first"
        proj.mkdir()
        registry.register_project("first", proj)
        # First registered project becomes active automatically
        active = registry.get_active_project()
        assert active["name"] == "first"


# ---------- Run task in project ----------


class TestRunTaskInProject:
    def test_run_task_returns_result(self, populated_registry: ProjectRegistry):
        result = populated_registry.run_task_in_project("alpha", "build")
        assert result["project"] == "alpha"
        assert result["task"] == "build"
        assert "status" in result

    def test_run_task_unknown_project_raises(self, populated_registry: ProjectRegistry):
        with pytest.raises(KeyError):
            populated_registry.run_task_in_project("nonexistent", "build")

    def test_run_task_restores_active(self, populated_registry: ProjectRegistry):
        populated_registry.switch_project("alpha")
        populated_registry.run_task_in_project("beta", "test")
        # Active project should be restored to alpha after task completes
        assert populated_registry.get_active_project()["name"] == "alpha"


# ---------- Sync knowledge across ----------


class TestSyncKnowledgeAcross:
    def test_sync_copies_entries(self, populated_registry: ProjectRegistry):
        # Write a mock knowledge file in source project
        source_path = Path(populated_registry._get_project("alpha")["path"])
        kb_dir = source_path / "knowledge"
        kb_dir.mkdir(parents=True)
        kb_file = kb_dir / "ENCYCLOPEDIA.md"
        kb_file.write_text(
            "## Tricks\n"
            "- [2025-01-01 10:00] Use caching for speed\n"
            "- [2025-01-02 11:00] Batch API calls\n"
            "## Decisions\n"
        )

        # Target has its own knowledge dir
        target_path = Path(populated_registry._get_project("beta")["path"])
        target_kb_dir = target_path / "knowledge"
        target_kb_dir.mkdir(parents=True)
        target_kb_file = target_kb_dir / "ENCYCLOPEDIA.md"
        target_kb_file.write_text("## Tricks\n<!-- tips -->\n## Decisions\n")

        count = populated_registry.sync_knowledge_across("alpha", "beta")
        assert count == 2

    def test_sync_unknown_source_raises(self, populated_registry: ProjectRegistry):
        with pytest.raises(KeyError):
            populated_registry.sync_knowledge_across("nonexistent", "beta")

    def test_sync_no_knowledge_returns_zero(self, populated_registry: ProjectRegistry):
        count = populated_registry.sync_knowledge_across("alpha", "beta")
        assert count == 0


# ---------- Module-level convenience functions ----------


class TestModuleFunctions:
    def test_module_functions_use_default_registry(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        proj = tmp_path / "proj"
        proj.mkdir()
        result = register_project("proj", proj)
        assert result["name"] == "proj"
        projects = list_projects()
        assert len(projects) == 1
        switch_project("proj")
        active = get_active_project()
        assert active["name"] == "proj"
