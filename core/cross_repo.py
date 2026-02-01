"""Cross-repository coordination: linking repos, coordinated commits, permission boundaries.

When claude-flow is available, coordinated_commit delegates to the bridge's multi_repo_sync.
Local JSON is always maintained for permission tracking.
"""

import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

logger = logging.getLogger(__name__)

LINKED_REPOS_FILE = Path("state/linked_repos.json")


@dataclass
class LinkedRepo:
    name: str
    path: str
    remote_url: str = ""
    permissions: list[str] = field(default_factory=lambda: ["read"])
    linked_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LinkedRepo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _load_linked_repos(path: Path = LINKED_REPOS_FILE) -> list[LinkedRepo]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [LinkedRepo.from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError):
        return []


def _save_linked_repos(repos: list[LinkedRepo], path: Path = LINKED_REPOS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.to_dict() for r in repos], indent=2))


def link_repository(
    name: str,
    path: str,
    *,
    remote_url: str = "",
    permissions: list[str] | None = None,
    repos_file: Path = LINKED_REPOS_FILE,
) -> LinkedRepo:
    """Link an external repository for cross-repo operations.

    Args:
        name: Short name for the repo.
        path: Local path to the repo.
        remote_url: Git remote URL.
        permissions: List of permissions ('read', 'write', 'commit').

    Returns:
        The created LinkedRepo.
    """
    repos = _load_linked_repos(repos_file)

    # Check for duplicates
    if any(r.name == name for r in repos):
        logger.warning("Repository '%s' already linked", name)
        repos = [r for r in repos if r.name != name]

    repo = LinkedRepo(
        name=name,
        path=path,
        remote_url=remote_url,
        permissions=permissions or ["read"],
    )
    repos.append(repo)
    _save_linked_repos(repos, repos_file)
    logger.info("Linked repository: %s at %s", name, path)
    return repo


def coordinated_commit(
    message: str,
    repo_names: list[str],
    *,
    repos_file: Path = LINKED_REPOS_FILE,
) -> dict[str, bool]:
    """Commit to multiple linked repos with the same message.

    Tries claude-flow multi_repo_sync first, falls back to local git commands.
    Permission checks are always enforced locally.

    Args:
        message: Commit message.
        repo_names: Names of repos to commit to.
        repos_file: Path to linked repos file.

    Returns:
        Dict mapping repo name -> success boolean.
    """
    repos = _load_linked_repos(repos_file)
    repo_map = {r.name: r for r in repos}
    results = {}

    # Pre-check permissions locally
    permitted_names = []
    for name in repo_names:
        if name not in repo_map:
            logger.warning("Repository '%s' not found", name)
            results[name] = False
            continue
        repo = repo_map[name]
        if "commit" not in repo.permissions and "write" not in repo.permissions:
            logger.warning("No commit permission for '%s'", name)
            results[name] = False
            continue
        permitted_names.append(name)

    if not permitted_names:
        return results

    # Try bridge
    try:
        bridge = _get_bridge()
        cf_result = bridge.multi_repo_sync(message, permitted_names)
        for name in permitted_names:
            results[name] = cf_result.get(name, False)
        return results
    except ClaudeFlowUnavailable:
        pass

    # Legacy: local git commits
    for name in permitted_names:
        repo = repo_map[name]
        repo_path = Path(repo.path)
        if not repo_path.exists():
            logger.warning("Repository path not found: %s", repo.path)
            results[name] = False
            continue

        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message, "--allow-empty"],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )
            results[name] = True
            logger.info("Committed to %s", name)
        except subprocess.CalledProcessError as e:
            logger.error("Commit failed for %s: %s", name, e.stderr)
            results[name] = False

    return results


def enforce_permission_boundaries(
    repo_name: str,
    action: str,
    *,
    repos_file: Path = LINKED_REPOS_FILE,
) -> bool:
    """Check if an action is permitted on a linked repo.

    Args:
        repo_name: Name of the linked repo.
        action: Action to check ('read', 'write', 'commit').
        repos_file: Path to linked repos file.

    Returns:
        True if the action is permitted.
    """
    repos = _load_linked_repos(repos_file)
    for repo in repos:
        if repo.name == repo_name:
            allowed = action in repo.permissions
            if not allowed:
                logger.warning("Action '%s' not permitted on '%s'", action, repo_name)
            return allowed
    logger.warning("Repository '%s' not found", repo_name)
    return False
