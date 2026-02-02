"""Multi-project handling module.

Manages multiple concurrent projects (e.g., update a website while working
on a paper). Provides a registry for tracking projects, switching active
context, running tasks across projects, and sharing knowledge between them.

Registry is persisted at ``~/.ricet/projects.json``.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path.home() / ".ricet" / "projects.json"


class ProjectRegistry:
    """Central registry that tracks all registered projects."""

    def __init__(self, registry_file: Path = DEFAULT_REGISTRY_PATH) -> None:
        self.registry_file = registry_file
        self._data = self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        """Load registry from disk, returning empty structure if missing."""
        if self.registry_file.exists():
            data = json.loads(self.registry_file.read_text())
            # Migrate legacy format (plain list) to dict structure
            if isinstance(data, list):
                active = next(
                    (p.get("name") for p in data if p.get("active")),
                    None,
                )
                for p in data:
                    p.pop("active", None)
                data = {"projects": data, "active": active}
                self.registry_file.write_text(json.dumps(data, indent=2))
            return data
        return {"projects": [], "active": None}

    def _save(self) -> None:
        """Persist registry to disk."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.registry_file.write_text(json.dumps(self._data, indent=2))

    # ------------------------------------------------------------------
    # Internal lookup
    # ------------------------------------------------------------------

    def _get_project(self, name: str) -> dict:
        """Return project dict or raise ``KeyError``."""
        for proj in self._data["projects"]:
            if proj["name"] == name:
                return proj
        raise KeyError(f"Project not found: {name}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_project(
        self,
        name: str,
        path: Path,
        project_type: str = "research",
    ) -> dict:
        """Register (or update) a project in the registry.

        Args:
            name: Unique project name.
            path: Filesystem path to the project root.  Must exist.
            project_type: Arbitrary type label (e.g. ``"research"``, ``"website"``).

        Returns:
            dict describing the registered project.

        Raises:
            FileNotFoundError: If *path* does not exist on disk.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Project path does not exist: {path}")

        entry = {
            "name": name,
            "path": str(path),
            "project_type": project_type,
            "registered_at": datetime.now().isoformat(),
        }

        # Replace existing entry with the same name, or append.
        existing_idx = next(
            (i for i, p in enumerate(self._data["projects"]) if p["name"] == name),
            None,
        )
        if existing_idx is not None:
            self._data["projects"][existing_idx] = entry
        else:
            self._data["projects"].append(entry)

        # First project becomes active automatically.
        if self._data["active"] is None:
            self._data["active"] = name

        self._save()
        logger.info("Registered project '%s' at %s", name, path)
        return entry

    def list_projects(self) -> list[dict]:
        """Return a list of all registered projects with their status.

        Each dict contains ``name``, ``path``, ``project_type``,
        ``registered_at``, and an ``active`` boolean flag.
        """
        active_name = self._data.get("active")
        return [
            {**proj, "active": proj["name"] == active_name}
            for proj in self._data["projects"]
        ]

    def switch_project(self, name: str) -> Path:
        """Switch the active project context.

        Args:
            name: Name of a previously registered project.

        Returns:
            :class:`~pathlib.Path` to the project root.

        Raises:
            KeyError: If *name* is not in the registry.
        """
        proj = self._get_project(name)
        self._data["active"] = name
        self._save()
        logger.info("Switched active project to '%s'", name)
        return Path(proj["path"])

    def get_active_project(self) -> dict:
        """Return the currently active project.

        Raises:
            RuntimeError: If no project is active.
        """
        active_name = self._data.get("active")
        if active_name is None:
            raise RuntimeError(
                "No active project. Register or switch to a project first."
            )
        return self._get_project(active_name)

    def run_task_in_project(self, project_name: str, task: str) -> dict:
        """Execute *task* in the context of *project_name*.

        Temporarily switches the active project, records the task, and
        restores the previously active project afterwards.

        Args:
            project_name: Target project.
            task: Free-form task description.

        Returns:
            dict with ``project``, ``task``, ``status``, and ``timestamp`` keys.

        Raises:
            KeyError: If *project_name* is not registered.
        """
        proj = self._get_project(project_name)
        previous_active = self._data.get("active")

        # Switch context
        self._data["active"] = project_name

        result = {
            "project": project_name,
            "task": task,
            "path": proj["path"],
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
        }
        logger.info("Ran task '%s' in project '%s'", task, project_name)

        # Restore previous active project
        self._data["active"] = previous_active
        self._save()
        return result

    def sync_knowledge_across(self, source: str, target: str) -> int:
        """Share knowledge entries from *source* project to *target* project.

        Reads ``knowledge/ENCYCLOPEDIA.md`` inside the source project,
        extracts timestamped entries, and appends any new entries to the
        target project's encyclopedia.

        Args:
            source: Name of the source project.
            target: Name of the target project.

        Returns:
            Number of entries synced.

        Raises:
            KeyError: If either project is not registered.
        """
        source_proj = self._get_project(source)
        target_proj = self._get_project(target)

        source_kb = Path(source_proj["path"]) / "knowledge" / "ENCYCLOPEDIA.md"
        target_kb = Path(target_proj["path"]) / "knowledge" / "ENCYCLOPEDIA.md"

        if not source_kb.exists():
            logger.warning("No knowledge file in source project '%s'", source)
            return 0

        # Extract timestamped entries from source
        source_content = source_kb.read_text()
        entry_pattern = re.compile(r"^- \[.+$", re.MULTILINE)
        source_entries = entry_pattern.findall(source_content)

        if not source_entries:
            return 0

        # Read existing target entries to avoid duplicates
        if target_kb.exists():
            target_content = target_kb.read_text()
        else:
            target_kb.parent.mkdir(parents=True, exist_ok=True)
            target_content = "## Tricks\n## Decisions\n"
            target_kb.write_text(target_content)

        count = 0
        for entry in source_entries:
            if entry not in target_content:
                # Append under first section header
                first_section = re.search(r"(## \w+\n)", target_content)
                if first_section:
                    insert_pos = first_section.end()
                    target_content = (
                        target_content[:insert_pos]
                        + entry
                        + "\n"
                        + target_content[insert_pos:]
                    )
                    count += 1

        if count > 0:
            target_kb.write_text(target_content)
            logger.info("Synced %d entries from '%s' to '%s'", count, source, target)

        return count


# ------------------------------------------------------------------
# Module-level convenience functions (use default registry path)
# ------------------------------------------------------------------

_default_registry: Optional[ProjectRegistry] = None


def _get_default_registry() -> ProjectRegistry:
    global _default_registry
    # Re-derive path each call so monkeypatched HOME is respected
    path = Path.home() / ".ricet" / "projects.json"
    if _default_registry is None or _default_registry.registry_file != path:
        _default_registry = ProjectRegistry(registry_file=path)
    return _default_registry


def register_project(name: str, path: Path, project_type: str = "research") -> dict:
    """Register a project using the default registry."""
    return _get_default_registry().register_project(name, path, project_type)


def list_projects() -> list[dict]:
    """List all projects using the default registry."""
    return _get_default_registry().list_projects()


def switch_project(name: str) -> Path:
    """Switch active project using the default registry."""
    return _get_default_registry().switch_project(name)


def get_active_project() -> dict:
    """Get the active project using the default registry."""
    return _get_default_registry().get_active_project()


def run_task_in_project(project_name: str, task: str) -> dict:
    """Run a task in a project using the default registry."""
    return _get_default_registry().run_task_in_project(project_name, task)


def sync_knowledge_across(source: str, target: str) -> int:
    """Sync knowledge between projects using the default registry."""
    return _get_default_registry().sync_knowledge_across(source, target)


# ---------------------------------------------------------------------------
# CLI adapter — ``from core.multi_project import project_manager``
# ---------------------------------------------------------------------------


class _ProjectManager:
    """Thin CLI-facing adapter wrapping the module-level convenience functions."""

    def list_projects(self) -> list[dict]:
        return list_projects()

    def switch(self, name: str) -> Path:
        return switch_project(name)

    def register(self, name: str, path: str, project_type: str = "research") -> None:
        register_project(name, Path(path), project_type)


project_manager = _ProjectManager()
