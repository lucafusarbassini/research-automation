"""Automation utilities: data handling, experiment running, plot generation, report generation."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DataHandler:
    """Handles data loading, sampling, and basic validation."""

    path: Path
    format: str = ""  # auto-detected if empty
    shape: tuple = ()
    columns: list[str] = field(default_factory=list)

    def detect_format(self) -> str:
        """Detect file format from extension."""
        suffix = self.path.suffix.lower()
        format_map = {
            ".csv": "csv",
            ".tsv": "tsv",
            ".json": "json",
            ".jsonl": "jsonl",
            ".parquet": "parquet",
            ".feather": "feather",
            ".pkl": "pickle",
            ".h5": "hdf5",
            ".hdf5": "hdf5",
            ".npy": "numpy",
            ".npz": "numpy",
        }
        self.format = format_map.get(suffix, "unknown")
        return self.format

    def get_info(self) -> dict:
        """Get basic info about the data file."""
        if not self.path.exists():
            return {"error": f"File not found: {self.path}"}
        if not self.format:
            self.detect_format()
        return {
            "path": str(self.path),
            "format": self.format,
            "size_mb": round(self.path.stat().st_size / (1024 * 1024), 2),
        }


def downsample_data(
    data: list,
    fraction: float = 0.1,
    *,
    seed: int = 42,
) -> list:
    """Downsample a list for quick testing.

    Args:
        data: Input list.
        fraction: Fraction to keep (0.0-1.0).
        seed: Random seed for reproducibility.

    Returns:
        Downsampled list.
    """
    import random

    rng = random.Random(seed)
    n = max(1, int(len(data) * fraction))
    return rng.sample(data, min(n, len(data)))


@dataclass
class ExperimentRunner:
    """Manages experiment execution with logging."""

    name: str
    parameters: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)
    log_dir: Path = field(default_factory=lambda: Path("state/experiments"))

    def log_params(self, params: dict) -> None:
        """Log experiment parameters."""
        self.parameters.update(params)

    def log_metric(self, key: str, value: float) -> None:
        """Log a metric."""
        self.results[key] = value

    def save(self) -> Path:
        """Save experiment to disk."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.log_dir / f"{self.name}_{timestamp}.json"
        data = {
            "name": self.name,
            "timestamp": timestamp,
            "parameters": self.parameters,
            "results": self.results,
        }
        path.write_text(json.dumps(data, indent=2))
        return path


@dataclass
class PlotGenerator:
    """Generates common plot types with sensible defaults."""

    output_dir: Path = field(default_factory=lambda: Path("figures"))

    def generate_spec(
        self,
        plot_type: str,
        data_description: str,
        **kwargs,
    ) -> dict:
        """Generate a plot specification.

        Args:
            plot_type: One of 'line', 'bar', 'scatter', 'heatmap', 'histogram'.
            data_description: What the data represents.

        Returns:
            Plot specification dict.
        """
        return {
            "type": plot_type,
            "description": data_description,
            "output_dir": str(self.output_dir),
            "kwargs": kwargs,
        }


@dataclass
class ReportGenerator:
    """Generates text reports from experiment results."""

    title: str = "Experiment Report"
    sections: list[dict] = field(default_factory=list)

    def add_section(self, heading: str, content: str) -> None:
        """Add a section to the report."""
        self.sections.append({"heading": heading, "content": content})

    def render_markdown(self) -> str:
        """Render the report as Markdown."""
        lines = [
            f"# {self.title}",
            f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]
        for section in self.sections:
            lines.append(f"## {section['heading']}")
            lines.append("")
            lines.append(section["content"])
            lines.append("")
        return "\n".join(lines)

    def save(self, path: Path) -> None:
        """Save the report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_markdown())


def run_smoke_test(
    command: str,
    *,
    timeout: int = 30,
) -> dict:
    """Run a quick smoke test of a command.

    Args:
        command: Shell command to run.
        timeout: Timeout in seconds.

    Returns:
        Dict with 'success', 'output', 'error' keys.
    """
    import subprocess

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout[:1000],
            "error": result.stderr[:500],
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": f"Timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}
