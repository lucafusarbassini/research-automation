"""Doability assessment: evaluate whether a research goal is well-defined and feasible."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keywords used for heuristic analysis
# ---------------------------------------------------------------------------

_GOAL_QUALITY_KEYWORDS = {
    "specific": ["accuracy", "f1", "loss", "metric", "percent", "%", "score", "auc"],
    "dataset": [
        "dataset",
        "data",
        "corpus",
        "benchmark",
        "cifar",
        "imagenet",
        "csv",
        "json",
    ],
    "architecture": [
        "resnet",
        "transformer",
        "bert",
        "gpt",
        "cnn",
        "rnn",
        "lstm",
        "mlp",
        "model",
        "architecture",
        "network",
        "classifier",
        "regressor",
    ],
    "compute": ["gpu", "tpu", "cpu", "a100", "v100", "cloud", "cluster", "ram"],
    "framework": [
        "pytorch",
        "tensorflow",
        "jax",
        "keras",
        "scikit",
        "sklearn",
        "pandas",
    ],
    "metric": [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "bleu",
        "rouge",
        "rmse",
        "mse",
        "auc",
    ],
    "output": ["paper", "report", "dashboard", "plot", "table", "figure", "notebook"],
}

_VAGUE_PHRASES = [
    "do something",
    "play around",
    "try stuff",
    "figure out",
    "look into",
    "explore",
    "maybe",
    "somehow",
    "something with",
]

_PAPER_KEYWORDS = [
    "paper",
    "manuscript",
    "journal",
    "conference",
    "submission",
    "latex",
    "write up",
    "write-up",
]

_REQUIREMENT_DIMENSIONS = [
    "dataset",
    "architecture",
    "metric",
    "compute",
    "framework",
    "output",
    "timeline",
    "evaluation",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DoabilityReport:
    """Result of a doability assessment for a research goal."""

    is_feasible: bool = False
    missing_info: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    checklist: dict[str, bool] = field(default_factory=dict)


@dataclass
class ReadinessReport:
    """Result of a project-directory readiness audit."""

    is_ready: bool = False
    missing_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    found_files: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assess_doability(
    goal: str,
    constraints: dict,
    available_resources: dict,
) -> DoabilityReport:
    """Analyse whether a research goal is well-defined and feasible.

    Args:
        goal: Natural-language description of the research goal.
        constraints: Dict of constraints (e.g. timeline, compute budget).
        available_resources: Dict of resources the user already has.

    Returns:
        DoabilityReport summarising feasibility, gaps, and risks.
    """
    logger.debug("Assessing doability for goal: %s", goal[:80])

    report = DoabilityReport()
    goal_lower = goal.lower()

    # --- 1. Check if goal is specific enough ---
    is_vague = (
        any(phrase in goal_lower for phrase in _VAGUE_PHRASES) or len(goal.split()) < 4
    )
    report.checklist["goal_specific"] = not is_vague

    # --- 2. Check each dimension ---
    missing: list[str] = []
    present_dimensions: list[str] = []

    combined_text = (
        goal_lower
        + " "
        + " ".join(str(v).lower() for v in constraints.values())
        + " "
        + " ".join(str(v).lower() for v in available_resources.values())
    )

    for dimension, keywords in _GOAL_QUALITY_KEYWORDS.items():
        found = any(kw in combined_text for kw in keywords)
        report.checklist[f"has_{dimension}"] = found
        if found:
            present_dimensions.append(dimension)
        else:
            missing.append(dimension)

    # --- 3. Resources check ---
    has_resources = len(available_resources) > 0
    report.checklist["resources_listed"] = has_resources
    if not has_resources:
        missing.append("No resources specified — unclear what is available")
        report.suggestions.append(
            "List available resources (data, compute, libraries)."
        )

    has_constraints = len(constraints) > 0
    report.checklist["constraints_defined"] = has_constraints
    if not has_constraints:
        report.suggestions.append(
            "Define constraints such as timeline and compute budget."
        )

    # --- 4. Feasibility decision ---
    critical_missing = [
        m for m in missing if m in ("dataset", "metric", "architecture")
    ]
    if is_vague:
        report.is_feasible = False
        report.missing_info.append(
            "Goal is too vague — provide a specific, measurable objective."
        )
    elif len(critical_missing) >= 2 and not has_resources:
        report.is_feasible = False
    else:
        report.is_feasible = True

    # Add non-vagueness missing items
    for m in missing:
        if m not in report.missing_info:
            report.missing_info.append(m)

    # --- 5. Risk level ---
    risk_score = len(missing)
    if is_vague:
        risk_score += 3
    if not has_resources:
        risk_score += 2

    if risk_score <= 2:
        report.risk_level = "low"
    elif risk_score <= 5:
        report.risk_level = "medium"
    else:
        report.risk_level = "high"

    # --- 6. Suggestions ---
    if "dataset" in missing:
        report.suggestions.append("Specify the dataset or data source to use.")
    if "metric" in missing:
        report.suggestions.append("Define a clear evaluation metric.")
    if "compute" in missing and any(
        kw in goal_lower
        for kw in ["train", "fine-tune", "finetune", "large", "7b", "13b", "70b"]
    ):
        report.suggestions.append("Clarify GPU/compute requirements for training.")

    logger.info(
        "Doability assessment: feasible=%s, risk=%s, missing=%d items",
        report.is_feasible,
        report.risk_level,
        len(report.missing_info),
    )
    return report


def check_project_readiness(project_path: Path) -> ReadinessReport:
    """Audit a project directory for required files and configuration.

    Checks for:
        - GOAL.md, CONSTRAINTS.md, TODO.md
        - config/settings.yml
        - .env for API keys
        - Journal/conference templates if paper writing is mentioned in GOAL.md
        - Uploaded files referenced in GOAL.md

    Args:
        project_path: Root directory of the research project.

    Returns:
        ReadinessReport with lists of missing files and warnings.
    """
    project_path = Path(project_path)
    logger.debug("Checking project readiness at: %s", project_path)

    report = ReadinessReport()

    # --- Required markdown files ---
    required_files = ["GOAL.md", "CONSTRAINTS.md", "TODO.md"]
    for fname in required_files:
        fpath = project_path / fname
        if fpath.exists():
            report.found_files.append(fname)
        else:
            report.missing_files.append(fname)

    # --- config/settings.yml ---
    settings_path = project_path / "config" / "settings.yml"
    if settings_path.exists():
        report.found_files.append("config/settings.yml")
    else:
        report.missing_files.append("config/settings.yml")

    # --- .env ---
    env_path = project_path / ".env"
    if env_path.exists():
        report.found_files.append(".env")
    else:
        report.missing_files.append(".env")

    # --- Paper-writing template check ---
    goal_path = project_path / "GOAL.md"
    goal_text = ""
    if goal_path.exists():
        try:
            goal_text = goal_path.read_text(encoding="utf-8").lower()
        except OSError:
            report.warnings.append(
                "Could not read GOAL.md to check for paper references."
            )

    if any(kw in goal_text for kw in _PAPER_KEYWORDS):
        templates_dir = project_path / "templates"
        if not templates_dir.exists() or not any(templates_dir.iterdir()):
            report.warnings.append(
                "GOAL.md mentions paper/journal writing but no templates/ directory found."
            )

    # --- Referenced uploads ---
    _check_referenced_files(goal_text, project_path, report)

    # --- Final verdict ---
    report.is_ready = len(report.missing_files) == 0

    logger.info(
        "Project readiness: ready=%s, missing=%d files, %d warnings",
        report.is_ready,
        len(report.missing_files),
        len(report.warnings),
    )
    return report


def extract_missing_requirements(user_prompt: str) -> list[str]:
    """Parse a user prompt and identify under-specified requirements.

    Checks for common research dimensions: dataset, architecture, metric,
    compute, framework, output format, timeline, evaluation strategy.

    Args:
        user_prompt: Free-text description of what the user wants to do.

    Returns:
        List of requirement names that appear to be missing.
    """
    if not user_prompt or not user_prompt.strip():
        logger.debug("Empty prompt — all requirements missing.")
        return list(_REQUIREMENT_DIMENSIONS)

    prompt_lower = user_prompt.lower()
    missing: list[str] = []

    dimension_keywords: dict[str, list[str]] = {
        "dataset": [
            "dataset",
            "data",
            "corpus",
            "csv",
            "json",
            "sql",
            "cifar",
            "imagenet",
            "benchmark",
        ],
        "architecture": [
            "model",
            "resnet",
            "transformer",
            "bert",
            "gpt",
            "cnn",
            "rnn",
            "lstm",
            "architecture",
            "network",
            "classifier",
            "regressor",
            "xgboost",
            "random forest",
        ],
        "metric": [
            "accuracy",
            "precision",
            "recall",
            "f1",
            "bleu",
            "rouge",
            "rmse",
            "mse",
            "auc",
            "metric",
            "evaluate",
        ],
        "compute": [
            "gpu",
            "tpu",
            "cpu",
            "a100",
            "v100",
            "cloud",
            "cluster",
            "machine",
            "server",
        ],
        "framework": [
            "pytorch",
            "tensorflow",
            "jax",
            "keras",
            "scikit",
            "sklearn",
            "pandas",
            "numpy",
        ],
        "output": [
            "paper",
            "report",
            "plot",
            "figure",
            "notebook",
            "dashboard",
            "table",
            "output",
            "result",
        ],
        "timeline": [
            "deadline",
            "week",
            "month",
            "day",
            "date",
            "timeline",
            "by",
            "before",
            "until",
        ],
        "evaluation": [
            "test set",
            "validation",
            "cross-val",
            "holdout",
            "split",
            "evaluated",
            "benchmark",
        ],
    }

    for dimension, keywords in dimension_keywords.items():
        if not any(kw in prompt_lower for kw in keywords):
            missing.append(dimension)

    logger.debug("Missing requirements from prompt: %s", missing)
    return missing


def generate_clarifying_questions(missing: list[str]) -> list[str]:
    """Generate focused clarifying questions for each missing requirement.

    Args:
        missing: List of missing requirement names (e.g. 'dataset', 'metric').

    Returns:
        List of human-readable questions, at least one per missing item.
    """
    if not missing:
        return []

    templates: dict[str, str] = {
        "dataset": "What dataset or data source will you use? (e.g. public benchmark, proprietary CSV, API)",
        "architecture": "Which model architecture do you want to use? (e.g. ResNet, Transformer, XGBoost)",
        "metric": "How will you measure success? What evaluation metric should be used?",
        "compute": "What compute resources are available? (e.g. local CPU, single GPU, cloud cluster)",
        "framework": "Which ML/data framework do you prefer? (e.g. PyTorch, TensorFlow, scikit-learn)",
        "output": "What is the desired output? (e.g. a trained model, a paper draft, plots/figures)",
        "timeline": "What is the target deadline or timeline for this project?",
        "evaluation": "How should the results be evaluated? (e.g. hold-out test set, cross-validation, A/B test)",
    }

    questions: list[str] = []
    for item in missing:
        item_lower = item.lower().strip()
        if item_lower in templates:
            questions.append(templates[item_lower])
        else:
            questions.append(f"Can you provide more details about: {item}?")

    logger.debug("Generated %d clarifying questions", len(questions))
    return questions


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_referenced_files(
    goal_text: str,
    project_path: Path,
    report: ReadinessReport,
) -> None:
    """Look for file/folder references in GOAL.md text and check they exist."""
    if not goal_text:
        return

    # Simple heuristic: find quoted paths or common extensions
    patterns = [
        r'["\']([^"\']+\.\w{1,5})["\']',  # quoted filenames
        r"`([^`]+\.\w{1,5})`",  # backtick filenames
        r"\b(uploads?/[\w./-]+)",  # uploads/ references
        r"\b(data/[\w./-]+)",  # data/ references
    ]

    referenced: set[str] = set()
    for pat in patterns:
        referenced.update(re.findall(pat, goal_text))

    for ref in referenced:
        ref_path = project_path / ref
        if not ref_path.exists():
            report.warnings.append(f"GOAL.md references '{ref}' but it was not found.")
