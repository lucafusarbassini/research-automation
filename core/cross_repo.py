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


def index_linked_repo(repo: LinkedRepo) -> int:
    """Walk a linked repo and index text files into memory.

    Indexes .py, .md, .txt, .tex files. Tries HNSW memory via claude-flow,
    falls back to a local JSON index.

    Args:
        repo: The linked repo to index.

    Returns:
        Number of files indexed.
    """
    repo_path = Path(repo.path)
    if not repo_path.exists():
        logger.warning("Linked repo path not found: %s", repo.path)
        return 0

    extensions = {".py", ".md", ".txt", ".tex", ".rst", ".yml", ".yaml", ".json"}
    namespace = f"linked-{repo.name}"
    count = 0

    # Collect file contents
    entries: list[dict] = []
    for fpath in repo_path.rglob("*"):
        if not fpath.is_file():
            continue
        if fpath.suffix not in extensions:
            continue
        # Skip hidden dirs, node_modules, .git, etc.
        parts = fpath.relative_to(repo_path).parts
        if any(p.startswith(".") or p == "node_modules" for p in parts):
            continue
        try:
            text = fpath.read_text(errors="replace")[:5000]
            if text.strip():
                entries.append({
                    "path": str(fpath.relative_to(repo_path)),
                    "text": text,
                    "repo": repo.name,
                })
                count += 1
        except OSError:
            continue

    # Try storing in HNSW via claude-flow
    try:
        bridge = _get_bridge()
        for entry in entries:
            bridge.store_memory(
                entry["text"][:2000],
                namespace=namespace,
                metadata={"path": entry["path"], "repo": entry["repo"]},
            )
        logger.info("Indexed %d files from '%s' into HNSW", count, repo.name)
        return count
    except ClaudeFlowUnavailable:
        pass

    # Fallback: local JSON index
    index_dir = Path("state") / "linked_indexes"
    index_dir.mkdir(parents=True, exist_ok=True)
    index_file = index_dir / f"{repo.name}.json"
    index_file.write_text(json.dumps(entries, indent=2))
    logger.info("Indexed %d files from '%s' into local JSON", count, repo.name)
    return count


def search_all_linked(
    query: str,
    top_k: int = 10,
    *,
    repos_file: Path = LINKED_REPOS_FILE,
) -> list[dict]:
    """Search across all linked repo indexes.

    Tries HNSW first, falls back to keyword search on local JSON indexes.

    Args:
        query: Search query.
        top_k: Max results.
        repos_file: Path to linked repos file.

    Returns:
        List of dicts with 'text', 'path', 'source' keys.
    """
    repos = _load_linked_repos(repos_file)
    results: list[dict] = []

    # Try HNSW search
    try:
        bridge = _get_bridge()
        for repo in repos:
            namespace = f"linked-{repo.name}"
            cf_result = bridge.query_memory(query, top_k=top_k, namespace=namespace)
            for hit in cf_result.get("results", []):
                results.append({
                    "text": hit.get("text", ""),
                    "path": hit.get("metadata", {}).get("path", ""),
                    "source": repo.name,
                    "score": hit.get("score", 0),
                })
        # Sort by score descending
        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        return results[:top_k]
    except ClaudeFlowUnavailable:
        pass

    # Fallback: keyword search on local JSON indexes
    query_lower = query.lower()
    index_dir = Path("state") / "linked_indexes"
    if not index_dir.exists():
        return []

    for repo in repos:
        index_file = index_dir / f"{repo.name}.json"
        if not index_file.exists():
            continue
        try:
            entries = json.loads(index_file.read_text())
            for entry in entries:
                text = entry.get("text", "")
                if query_lower in text.lower():
                    results.append({
                        "text": text[:500],
                        "path": entry.get("path", ""),
                        "source": repo.name,
                    })
        except (json.JSONDecodeError, OSError):
            continue

    return results[:top_k]


def reindex_all(
    repos_file: Path = LINKED_REPOS_FILE,
) -> dict[str, int]:
    """Re-index all linked repositories.

    Args:
        repos_file: Path to linked repos file.

    Returns:
        Dict mapping repo name -> number of files indexed.
    """
    repos = _load_linked_repos(repos_file)
    results: dict[str, int] = {}
    for repo in repos:
        count = index_linked_repo(repo)
        results[repo.name] = count
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
