"""Tests for cross-repository coordination."""

from pathlib import Path

from core.cross_repo import (
    LinkedRepo,
    enforce_permission_boundaries,
    link_repository,
)


def test_linked_repo_roundtrip():
    repo = LinkedRepo(name="main", path="/tmp/main", permissions=["read", "write"])
    d = repo.to_dict()
    restored = LinkedRepo.from_dict(d)
    assert restored.name == "main"
    assert "write" in restored.permissions


def test_link_repository(tmp_path: Path):
    repos_file = tmp_path / "linked.json"
    repo = link_repository("my-lib", "/home/user/lib", permissions=["read"], repos_file=repos_file)
    assert repo.name == "my-lib"
    assert repos_file.exists()


def test_link_repository_duplicate(tmp_path: Path):
    repos_file = tmp_path / "linked.json"
    link_repository("lib", "/path1", repos_file=repos_file)
    link_repository("lib", "/path2", repos_file=repos_file)
    # Should replace, not duplicate
    import json
    data = json.loads(repos_file.read_text())
    names = [d["name"] for d in data]
    assert names.count("lib") == 1
    assert data[0]["path"] == "/path2"


def test_enforce_permission_read(tmp_path: Path):
    repos_file = tmp_path / "linked.json"
    link_repository("data-repo", "/data", permissions=["read"], repos_file=repos_file)
    assert enforce_permission_boundaries("data-repo", "read", repos_file=repos_file) is True
    assert enforce_permission_boundaries("data-repo", "write", repos_file=repos_file) is False


def test_enforce_permission_write(tmp_path: Path):
    repos_file = tmp_path / "linked.json"
    link_repository("code-repo", "/code", permissions=["read", "write", "commit"], repos_file=repos_file)
    assert enforce_permission_boundaries("code-repo", "commit", repos_file=repos_file) is True


def test_enforce_permission_unknown_repo(tmp_path: Path):
    repos_file = tmp_path / "linked.json"
    assert enforce_permission_boundaries("nonexistent", "read", repos_file=repos_file) is False
