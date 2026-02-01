"""Reproducibility enforcement: run logging, artifact registry, dataset hashing."""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RUNS_DIR = Path("state/runs")
REGISTRY_FILE = Path("state/artifact_registry.json")


@dataclass
class RunLog:
    run_id: str
    command: str
    started: str = field(default_factory=lambda: datetime.now().isoformat())
    ended: Optional[str] = None
    status: str = "running"
    git_hash: str = ""
    parameters: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RunLog":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def log_run(run: RunLog) -> Path:
    """Persist a run log to disk.

    Args:
        run: The RunLog to save.

    Returns:
        Path to the saved run file.
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{run.run_id}.json"
    path.write_text(json.dumps(run.to_dict(), indent=2))
    logger.info("Logged run: %s", run.run_id)
    return path


def load_run(run_id: str) -> Optional[RunLog]:
    """Load a run log by ID."""
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return RunLog.from_dict(json.loads(path.read_text()))


def list_runs() -> list[RunLog]:
    """List all runs sorted by start time."""
    if not RUNS_DIR.exists():
        return []
    runs = []
    for f in sorted(RUNS_DIR.glob("*.json")):
        try:
            runs.append(RunLog.from_dict(json.loads(f.read_text())))
        except (json.JSONDecodeError, KeyError):
            continue
    return runs


class ArtifactRegistry:
    """Registry for tracking experiment artifacts with checksums."""

    def __init__(self, registry_path: Path = REGISTRY_FILE):
        self.registry_path = registry_path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.registry_path.exists():
            self._data = json.loads(self.registry_path.read_text())

    def _save(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(self._data, indent=2))

    def register(
        self, name: str, path: Path, *, run_id: str = "", metadata: dict | None = None
    ) -> str:
        """Register an artifact with its checksum.

        Args:
            name: Artifact name/key.
            path: Path to the artifact file.
            run_id: Associated run ID.
            metadata: Optional metadata dict.

        Returns:
            SHA-256 checksum of the artifact.
        """
        checksum = _sha256(path)
        self._data[name] = {
            "path": str(path),
            "checksum": checksum,
            "run_id": run_id,
            "registered": datetime.now().isoformat(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "metadata": metadata or {},
        }
        self._save()
        logger.info("Registered artifact: %s (%s)", name, checksum[:12])
        return checksum

    def verify(self, name: str) -> bool:
        """Verify an artifact's integrity against its registered checksum.

        Returns:
            True if checksum matches, False otherwise.
        """
        if name not in self._data:
            return False
        entry = self._data[name]
        path = Path(entry["path"])
        if not path.exists():
            return False
        return _sha256(path) == entry["checksum"]

    def list_artifacts(self) -> dict[str, dict]:
        """Return all registered artifacts."""
        return dict(self._data)

    def get(self, name: str) -> Optional[dict]:
        """Get artifact entry by name."""
        return self._data.get(name)


def compute_dataset_hash(path: Path, *, sample_size: int = 0) -> str:
    """Compute a hash for a dataset file or directory.

    Args:
        path: Path to file or directory.
        sample_size: If > 0, only hash first N bytes (for large files).

    Returns:
        SHA-256 hex digest.
    """
    if path.is_file():
        return _sha256(path, max_bytes=sample_size)

    # For directories, hash sorted file names + sizes
    hasher = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            hasher.update(f"{item.relative_to(path)}:{item.stat().st_size}\n".encode())
    return hasher.hexdigest()


def _sha256(path: Path, *, max_bytes: int = 0) -> str:
    """Compute SHA-256 of a file."""
    hasher = hashlib.sha256()
    bytes_read = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
            bytes_read += len(chunk)
            if max_bytes > 0 and bytes_read >= max_bytes:
                break
    return hasher.hexdigest()
