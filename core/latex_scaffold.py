"""Adaptive LaTeX scaffold generation based on paper type and project domain.

Generates appropriate LaTeX document structure, packages, and section layout
depending on:
  - Paper type: journal article, conference paper, thesis chapter, technical
    report, review paper
  - Project domain: ML, NLP, CV, biology, general (detected from config or
    GOAL.md content)

The scaffold is composed from modular template fragments that can be mixed
and matched, following the same adaptive philosophy used for folder structures
and Python packages elsewhere in ricet.
"""

import logging
import re
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAPER_TYPES = [
    "journal-article",
    "conference-paper",
    "thesis-chapter",
    "technical-report",
    "review-paper",
]

DOMAIN_TYPES = [
    "ml",
    "nlp",
    "cv",
    "biology",
    "chemistry",
    "physics",
    "general",
]

FRAGMENTS_DIR = Path(__file__).parent.parent / "templates" / "paper" / "fragments"

# ---------------------------------------------------------------------------
# Domain detection
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "ml": [
        "machine learning",
        "deep learning",
        "neural network",
        "training",
        "gradient",
        "loss function",
        "backprop",
        "reinforcement learning",
        "classification",
        "regression",
        "clustering",
        "random forest",
        "xgboost",
        "hyperparameter",
        "epoch",
        "batch size",
    ],
    "nlp": [
        "natural language",
        "nlp",
        "language model",
        "tokeniz",
        "embedding",
        "transformer",
        "attention mechanism",
        "bert",
        "gpt",
        "llm",
        "text classification",
        "named entity",
        "sentiment",
        "translation",
        "seq2seq",
        "corpus",
        "vocabulary",
    ],
    "cv": [
        "computer vision",
        "image",
        "object detection",
        "segmentation",
        "convolutional",
        "cnn",
        "resnet",
        "yolo",
        "detection",
        "recognition",
        "pose estimation",
        "optical flow",
        "feature extraction",
        "gan",
        "diffusion model",
        "image generation",
    ],
    "biology": [
        "biology",
        "biological",
        "genomic",
        "protein",
        "cell",
        "tissue",
        "gene expression",
        "sequencing",
        "rna",
        "dna",
        "mutation",
        "phylogen",
        "metabol",
        "clinical trial",
        "patient",
        "cohort",
        "biomarker",
        "drug",
        "therapeutic",
        "consort",
        "prisma",
        "systematic review",
        "meta-analysis",
        "epidemiolog",
    ],
    "chemistry": [
        "chemistry",
        "chemical",
        "molecule",
        "reaction",
        "synthesis",
        "catalyst",
        "compound",
        "spectroscop",
        "nmr",
        "mass spec",
        "chromatograph",
        "organic",
        "inorganic",
        "polymer",
    ],
    "physics": [
        "physics",
        "quantum",
        "particle",
        "cosmolog",
        "astrophys",
        "relativity",
        "thermodynamic",
        "electrodynamic",
        "optics",
        "condensed matter",
        "simulation",
        "monte carlo",
    ],
}


def detect_domain(goal_text: str, project_type: str = "general") -> str:
    """Detect the project domain from GOAL.md content and config.

    Args:
        goal_text: Content of GOAL.md or project description.
        project_type: Explicit project_type from config (may already be set).

    Returns:
        One of the DOMAIN_TYPES strings.
    """
    if project_type in DOMAIN_TYPES and project_type != "general":
        return project_type

    if not goal_text:
        return "general"

    text_lower = goal_text.lower()
    scores: dict[str, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return "general"

    return max(scores, key=scores.get)


# ---------------------------------------------------------------------------
# Package selection
# ---------------------------------------------------------------------------

# Base packages always included (loaded via preamble.tex)
_BASE_PACKAGES: list[str] = [
    "inputenc",
    "fontenc",
    "lmodern",
    "microtype",
    "amsmath",
    "amssymb",
    "amsthm",
    "mathtools",
    "bm",
    "booktabs",
    "multirow",
    "array",
    "graphicx",
    "xcolor",
    "subcaption",
    "natbib",
    "hyperref",
    "cleveref",
    "enumitem",
    "xspace",
]

# Domain-specific extra packages
_DOMAIN_PACKAGES: dict[str, list[tuple[str, str, str]]] = {
    # (package_name, options, comment)
    "ml": [
        ("algorithm2e", "ruled,vlined,linesnumbered", "Algorithm pseudocode"),
        ("siunitx", "", "Consistent number formatting"),
        ("pgfplots", "", "Publication-quality plots in LaTeX"),
        ("tikz", "", "Diagrams and computational graphs"),
    ],
    "nlp": [
        ("algorithm2e", "ruled,vlined,linesnumbered", "Algorithm pseudocode"),
        ("siunitx", "", "Consistent number formatting"),
        ("tikz", "", "Parse trees and architecture diagrams"),
        ("tikz-dependency", "", "Dependency parse visualisation"),
        ("gb4e", "", "Linguistic examples and glosses"),
    ],
    "cv": [
        ("algorithm2e", "ruled,vlined,linesnumbered", "Algorithm pseudocode"),
        ("siunitx", "", "Consistent number formatting"),
        ("tikz", "", "Architecture diagrams"),
        ("pgfplots", "", "Result plots"),
        ("float", "", "Precise figure placement (figure-heavy)"),
    ],
    "biology": [
        ("siunitx", "", "SI units for measurements"),
        ("mhchem", "", "Chemical formulae via \\ce{}"),
        ("textgreek", "", "Greek letters in text mode"),
        ("longtable", "", "Multi-page tables for large datasets"),
        ("pdflscape", "", "Landscape pages for wide tables"),
    ],
    "chemistry": [
        ("siunitx", "", "SI units"),
        ("mhchem", "", "Chemical formulae and reactions"),
        ("chemfig", "", "Structural formulae drawing"),
        ("textgreek", "", "Greek letters in text mode"),
    ],
    "physics": [
        ("siunitx", "", "SI units"),
        ("tikz", "", "Feynman diagrams and schematics"),
        ("braket", "", "Dirac notation"),
        ("tensor", "", "Tensor index notation"),
        ("pgfplots", "", "Data plots"),
    ],
    "general": [
        ("siunitx", "", "Consistent number formatting"),
    ],
}

# Paper-type specific packages
_PAPER_TYPE_PACKAGES: dict[str, list[tuple[str, str, str]]] = {
    "conference-paper": [
        ("balance", "", "Balance columns on last page"),
    ],
    "thesis-chapter": [
        ("fancyhdr", "", "Custom headers and footers"),
        ("titlesec", "", "Chapter title formatting"),
        ("appendix", "", "Appendix management"),
    ],
    "review-paper": [
        ("longtable", "", "Multi-page comparison tables"),
        ("pdflscape", "", "Landscape pages for wide tables"),
        ("forest", "", "Taxonomy trees"),
    ],
    "technical-report": [
        ("fancyhdr", "", "Custom headers and footers"),
        ("appendix", "", "Appendix management"),
        ("listings", "", "Code listings"),
    ],
}


def select_packages(
    paper_type: str,
    domain: str,
) -> list[tuple[str, str, str]]:
    """Select LaTeX packages appropriate for the paper type and domain.

    Args:
        paper_type: One of PAPER_TYPES.
        domain: One of DOMAIN_TYPES.

    Returns:
        List of (package_name, options, comment) tuples for extra packages
        beyond the base preamble.
    """
    seen: set[str] = set(_BASE_PACKAGES)
    extras: list[tuple[str, str, str]] = []

    for pkg_name, opts, comment in _DOMAIN_PACKAGES.get(domain, []):
        if pkg_name not in seen:
            extras.append((pkg_name, opts, comment))
            seen.add(pkg_name)

    for pkg_name, opts, comment in _PAPER_TYPE_PACKAGES.get(paper_type, []):
        if pkg_name not in seen:
            extras.append((pkg_name, opts, comment))
            seen.add(pkg_name)

    return extras


# ---------------------------------------------------------------------------
# Section structure
# ---------------------------------------------------------------------------

_SECTION_STRUCTURES: dict[str, dict[str, list[dict]]] = {
    # Keyed by paper_type, then domain -> list of section dicts
    # Each section: {"level": "section"|"subsection", "title": ..., "label": ..., "guidance": ...}
    "journal-article": {
        "ml": [
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Motivate the problem, state contributions, and outline the paper.",
            },
            {
                "level": "section",
                "title": "Related Work",
                "label": "sec:related",
                "guidance": "Position this work relative to prior approaches. Group by methodology.",
            },
            {
                "level": "section",
                "title": "Methods",
                "label": "sec:methods",
                "guidance": "Describe the proposed approach in full detail.",
            },
            {
                "level": "subsection",
                "title": "Problem Formulation",
                "label": "sec:methods:formulation",
                "guidance": "Define notation, input/output spaces, and the objective function.",
            },
            {
                "level": "subsection",
                "title": "Model Architecture",
                "label": "sec:methods:architecture",
                "guidance": "Describe the model architecture with a figure reference.",
            },
            {
                "level": "subsection",
                "title": "Training Procedure",
                "label": "sec:methods:training",
                "guidance": "Loss function, optimiser, learning rate schedule, regularisation.",
            },
            {
                "level": "section",
                "title": "Experiments",
                "label": "sec:experiments",
                "guidance": "Describe experimental setup, datasets, baselines, and metrics.",
            },
            {
                "level": "subsection",
                "title": "Datasets",
                "label": "sec:experiments:datasets",
                "guidance": "Dataset statistics, splits, preprocessing steps.",
            },
            {
                "level": "subsection",
                "title": "Baselines",
                "label": "sec:experiments:baselines",
                "guidance": "Describe baseline methods and their configurations.",
            },
            {
                "level": "subsection",
                "title": "Results",
                "label": "sec:experiments:results",
                "guidance": "Present main results with tables and figures. Include error bars.",
            },
            {
                "level": "subsection",
                "title": "Ablation Study",
                "label": "sec:experiments:ablation",
                "guidance": "Systematically evaluate contribution of each component.",
            },
            {
                "level": "section",
                "title": "Discussion",
                "label": "sec:discussion",
                "guidance": "Interpret results, discuss limitations, and suggest future work.",
            },
            {
                "level": "section",
                "title": "Conclusion",
                "label": "sec:conclusion",
                "guidance": "Summarise contributions and key findings.",
            },
        ],
        "biology": [
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Provide biological context, state the knowledge gap, and the aim.",
            },
            {
                "level": "section",
                "title": "Materials and Methods",
                "label": "sec:methods",
                "guidance": "Sufficient detail for reproducibility.",
            },
            {
                "level": "subsection",
                "title": "Study Design",
                "label": "sec:methods:design",
                "guidance": "Describe study design, ethical approvals, patient consent.",
            },
            {
                "level": "subsection",
                "title": "Sample Collection",
                "label": "sec:methods:samples",
                "guidance": "Cohort description, inclusion/exclusion criteria, sample sizes.",
            },
            {
                "level": "subsection",
                "title": "Experimental Procedures",
                "label": "sec:methods:procedures",
                "guidance": "Protocols, reagents, instruments with catalogue numbers.",
            },
            {
                "level": "subsection",
                "title": "Statistical Analysis",
                "label": "sec:methods:statistics",
                "guidance": "Tests used, significance thresholds, multiple testing correction.",
            },
            {
                "level": "section",
                "title": "Results",
                "label": "sec:results",
                "guidance": "Present findings with references to figures and tables.",
            },
            {
                "level": "section",
                "title": "Discussion",
                "label": "sec:discussion",
                "guidance": "Interpret findings in biological context, compare with literature.",
            },
            {
                "level": "subsection",
                "title": "Limitations",
                "label": "sec:discussion:limitations",
                "guidance": "Acknowledge limitations and potential confounders.",
            },
            {
                "level": "section",
                "title": "Conclusion",
                "label": "sec:conclusion",
                "guidance": "Summarise the biological significance and clinical implications.",
            },
        ],
        "general": [
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Context, motivation, gap in knowledge, and aim.",
            },
            {
                "level": "section",
                "title": "Methods",
                "label": "sec:methods",
                "guidance": "Describe the approach with enough detail for reproducibility.",
            },
            {
                "level": "section",
                "title": "Results",
                "label": "sec:results",
                "guidance": "Present findings with figures and tables.",
            },
            {
                "level": "section",
                "title": "Discussion",
                "label": "sec:discussion",
                "guidance": "Interpret results, compare with prior work, discuss limitations.",
            },
            {
                "level": "section",
                "title": "Conclusion",
                "label": "sec:conclusion",
                "guidance": "Summarise contribution and outlook.",
            },
        ],
    },
    "conference-paper": {
        "ml": [
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Motivate the problem concisely. State contributions as a bulleted list.",
            },
            {
                "level": "section",
                "title": "Related Work",
                "label": "sec:related",
                "guidance": "Brief comparison with closest prior work.",
            },
            {
                "level": "section",
                "title": "Method",
                "label": "sec:method",
                "guidance": "Describe the proposed approach. Include architecture figure.",
            },
            {
                "level": "section",
                "title": "Experiments",
                "label": "sec:experiments",
                "guidance": "Datasets, baselines, metrics, main results table, ablations.",
            },
            {
                "level": "section",
                "title": "Conclusion",
                "label": "sec:conclusion",
                "guidance": "Brief summary and future directions.",
            },
        ],
        "general": [
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Problem statement and contributions.",
            },
            {
                "level": "section",
                "title": "Background",
                "label": "sec:background",
                "guidance": "Key concepts and related work.",
            },
            {
                "level": "section",
                "title": "Approach",
                "label": "sec:approach",
                "guidance": "Describe the proposed method or analysis.",
            },
            {
                "level": "section",
                "title": "Evaluation",
                "label": "sec:evaluation",
                "guidance": "Experimental setup and results.",
            },
            {
                "level": "section",
                "title": "Conclusion",
                "label": "sec:conclusion",
                "guidance": "Summary and future work.",
            },
        ],
    },
    "thesis-chapter": {
        "general": [
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Chapter overview and how it fits into the thesis narrative.",
            },
            {
                "level": "section",
                "title": "Background and Literature Review",
                "label": "sec:background",
                "guidance": "Detailed review of relevant prior work.",
            },
            {
                "level": "section",
                "title": "Methodology",
                "label": "sec:methodology",
                "guidance": "Detailed description of the approach.",
            },
            {
                "level": "section",
                "title": "Results",
                "label": "sec:results",
                "guidance": "Present all findings comprehensively.",
            },
            {
                "level": "section",
                "title": "Discussion",
                "label": "sec:discussion",
                "guidance": "In-depth interpretation and comparison with literature.",
            },
            {
                "level": "section",
                "title": "Summary",
                "label": "sec:summary",
                "guidance": "Chapter summary and transition to next chapter.",
            },
        ],
    },
    "technical-report": {
        "general": [
            {
                "level": "section",
                "title": "Executive Summary",
                "label": "sec:summary",
                "guidance": "High-level overview of findings and recommendations.",
            },
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Problem statement, scope, and objectives.",
            },
            {
                "level": "section",
                "title": "Background",
                "label": "sec:background",
                "guidance": "Context and prior work.",
            },
            {
                "level": "section",
                "title": "Methodology",
                "label": "sec:methodology",
                "guidance": "Detailed technical approach.",
            },
            {
                "level": "section",
                "title": "Results",
                "label": "sec:results",
                "guidance": "Findings with supporting data.",
            },
            {
                "level": "section",
                "title": "Analysis",
                "label": "sec:analysis",
                "guidance": "Interpretation and implications of results.",
            },
            {
                "level": "section",
                "title": "Recommendations",
                "label": "sec:recommendations",
                "guidance": "Actionable recommendations based on findings.",
            },
            {
                "level": "section",
                "title": "Appendices",
                "label": "sec:appendices",
                "guidance": "Supplementary data, code listings, detailed tables.",
            },
        ],
    },
    "review-paper": {
        "general": [
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Define the scope of the review and the research questions addressed.",
            },
            {
                "level": "section",
                "title": "Search Strategy and Selection Criteria",
                "label": "sec:search",
                "guidance": "Describe databases searched, keywords, inclusion/exclusion criteria.",
            },
            {
                "level": "section",
                "title": "Overview of the Field",
                "label": "sec:overview",
                "guidance": "Provide a high-level taxonomy of approaches.",
            },
            {
                "level": "section",
                "title": "Detailed Analysis",
                "label": "sec:analysis",
                "guidance": "In-depth comparison of methods, organised thematically.",
            },
            {
                "level": "subsection",
                "title": "Category A",
                "label": "sec:analysis:cat_a",
                "guidance": "First category of methods or findings.",
            },
            {
                "level": "subsection",
                "title": "Category B",
                "label": "sec:analysis:cat_b",
                "guidance": "Second category of methods or findings.",
            },
            {
                "level": "section",
                "title": "Discussion and Open Challenges",
                "label": "sec:discussion",
                "guidance": "Synthesise trends, identify gaps, and suggest future directions.",
            },
            {
                "level": "section",
                "title": "Conclusion",
                "label": "sec:conclusion",
                "guidance": "Summarise the state of the field and key takeaways.",
            },
        ],
        "biology": [
            {
                "level": "section",
                "title": "Introduction",
                "label": "sec:introduction",
                "guidance": "Define the clinical/biological question and scope of the review.",
            },
            {
                "level": "section",
                "title": "Methods",
                "label": "sec:methods",
                "guidance": "PRISMA-compliant search strategy and selection criteria.",
            },
            {
                "level": "subsection",
                "title": "Search Strategy",
                "label": "sec:methods:search",
                "guidance": "Databases, date ranges, MeSH terms, Boolean operators.",
            },
            {
                "level": "subsection",
                "title": "Eligibility Criteria",
                "label": "sec:methods:eligibility",
                "guidance": "Inclusion/exclusion criteria (PICOS framework if applicable).",
            },
            {
                "level": "subsection",
                "title": "Data Extraction and Quality Assessment",
                "label": "sec:methods:extraction",
                "guidance": "Data extraction form, risk of bias assessment tool.",
            },
            {
                "level": "section",
                "title": "Results",
                "label": "sec:results",
                "guidance": "PRISMA flow diagram, study characteristics table, synthesis.",
            },
            {
                "level": "section",
                "title": "Discussion",
                "label": "sec:discussion",
                "guidance": "Summarise evidence, discuss heterogeneity, clinical implications.",
            },
            {
                "level": "section",
                "title": "Conclusion",
                "label": "sec:conclusion",
                "guidance": "Key findings and recommendations for practice/research.",
            },
        ],
    },
}


def get_section_structure(
    paper_type: str,
    domain: str,
) -> list[dict]:
    """Get the section structure for a given paper type and domain.

    Falls back through domain -> "general" and paper_type -> "journal-article"
    to always return a valid structure.

    Args:
        paper_type: One of PAPER_TYPES.
        domain: One of DOMAIN_TYPES.

    Returns:
        List of section dicts with keys: level, title, label, guidance.
    """
    type_map = _SECTION_STRUCTURES.get(paper_type, {})
    # Try exact domain match first
    if domain in type_map:
        return type_map[domain]
    # NLP and CV fall back to ML structure for ML-family domains
    if domain in ("nlp", "cv") and "ml" in type_map:
        return type_map["ml"]
    # Chemistry and physics fall back to general
    if "general" in type_map:
        return type_map["general"]
    # Ultimate fallback: journal-article general
    return _SECTION_STRUCTURES["journal-article"]["general"]


# ---------------------------------------------------------------------------
# Document class configuration
# ---------------------------------------------------------------------------

_DOCUMENT_CLASS: dict[str, dict] = {
    "journal-article": {
        "class": "article",
        "options": "11pt,a4paper,onecolumn",
        "geometry": "top=2.5cm,bottom=2.5cm,left=2.5cm,right=2.5cm",
        "spacing": "onehalfspacing",
    },
    "conference-paper": {
        "class": "article",
        "options": "10pt,a4paper,twocolumn",
        "geometry": "top=2cm,bottom=2cm,left=1.8cm,right=1.8cm",
        "spacing": "singlespacing",
    },
    "thesis-chapter": {
        "class": "book",
        "options": "12pt,a4paper,onecolumn,oneside",
        "geometry": "top=3cm,bottom=3cm,left=3.5cm,right=2.5cm",
        "spacing": "doublespacing",
    },
    "technical-report": {
        "class": "article",
        "options": "11pt,a4paper,onecolumn",
        "geometry": "top=2.5cm,bottom=2.5cm,left=2.5cm,right=2.5cm",
        "spacing": "onehalfspacing",
    },
    "review-paper": {
        "class": "article",
        "options": "11pt,a4paper,onecolumn",
        "geometry": "top=2.5cm,bottom=2.5cm,left=2.5cm,right=2.5cm",
        "spacing": "onehalfspacing",
    },
}


def get_document_class_config(paper_type: str) -> dict:
    """Get document class configuration for a paper type.

    Args:
        paper_type: One of PAPER_TYPES.

    Returns:
        Dict with keys: class, options, geometry, spacing.
    """
    return _DOCUMENT_CLASS.get(paper_type, _DOCUMENT_CLASS["journal-article"])


# ---------------------------------------------------------------------------
# Back-matter configuration
# ---------------------------------------------------------------------------

_BACK_MATTER: dict[str, list[str]] = {
    "journal-article": [
        "data-availability",
        "author-contributions",
        "acknowledgements",
        "conflicts-of-interest",
    ],
    "conference-paper": [
        "acknowledgements",
    ],
    "thesis-chapter": [],
    "technical-report": [
        "acknowledgements",
    ],
    "review-paper": [
        "acknowledgements",
        "conflicts-of-interest",
    ],
}

_BACK_MATTER_CONTENT: dict[str, str] = {
    "data-availability": (
        "\\section*{Data Availability}\n\n"
        "% State where data and code can be accessed (e.g., Zenodo, GitHub).\n"
    ),
    "author-contributions": (
        "\\section*{Author Contributions}\n\n"
        "% CRediT taxonomy: Conceptualization, Methodology, Software, Validation,\n"
        "% Formal analysis, Investigation, Resources, Data curation, Writing --\n"
        "% original draft, Writing -- review \\& editing, Visualisation, Supervision,\n"
        "% Project administration, Funding acquisition.\n"
    ),
    "acknowledgements": (
        "\\section*{Acknowledgements}\n\n"
        "% Funding agencies, compute resources, helpful discussions.\n"
    ),
    "conflicts-of-interest": (
        "\\section*{Conflicts of Interest}\n\n"
        "The authors declare no competing interests.\n"
    ),
}


# ---------------------------------------------------------------------------
# File generators
# ---------------------------------------------------------------------------


def _generate_preamble_extra(
    paper_type: str,
    domain: str,
) -> str:
    """Generate the domain/type-specific preamble additions.

    This content is written to ``preamble_extra.tex`` and loaded after
    the base ``preamble.tex``.

    Args:
        paper_type: One of PAPER_TYPES.
        domain: One of DOMAIN_TYPES.

    Returns:
        LaTeX string for preamble_extra.tex.
    """
    extras = select_packages(paper_type, domain)
    if not extras:
        return (
            "% preamble_extra.tex -- additional packages for this project\n"
            "% (no extra packages needed for current configuration)\n"
        )

    lines = [
        "% =============================================================================",
        f"% preamble_extra.tex -- additional packages for {paper_type} / {domain}",
        "% =============================================================================",
        f"% Auto-generated by ricet for paper_type={paper_type}, domain={domain}",
        "% Edit freely -- this file is yours.",
        "% =============================================================================",
        "",
    ]

    for pkg_name, opts, comment in extras:
        if opts:
            lines.append(f"\\usepackage[{opts}]{{{pkg_name}}}  % {comment}")
        else:
            lines.append(f"\\usepackage{{{pkg_name}}}  % {comment}")

    # Add tikz libraries if tikz is included
    tikz_included = any(p[0] == "tikz" for p in extras)
    if tikz_included:
        lines.append("")
        lines.append("% TikZ libraries (add more as needed)")
        lines.append("\\usetikzlibrary{arrows.meta,positioning,calc,shapes}")
        if domain in ("ml", "nlp", "cv"):
            lines.append("\\usetikzlibrary{matrix,chains,decorations.pathreplacing}")

    # Add pgfplots config if included
    pgfplots_included = any(p[0] == "pgfplots" for p in extras)
    if pgfplots_included:
        lines.append("")
        lines.append("\\pgfplotsset{compat=1.18}")

    lines.append("")
    lines.append(
        "% ============================================================================="
    )
    lines.append("% End of preamble_extra.tex")
    lines.append(
        "% ============================================================================="
    )

    return "\n".join(lines) + "\n"


def _generate_main_tex(
    paper_type: str,
    domain: str,
) -> str:
    """Generate the main.tex file content.

    Args:
        paper_type: One of PAPER_TYPES.
        domain: One of DOMAIN_TYPES.

    Returns:
        Complete main.tex content string.
    """
    doc_config = get_document_class_config(paper_type)
    sections = get_section_structure(paper_type, domain)

    lines: list[str] = []

    # Header comment
    lines.extend(
        [
            "% =============================================================================",
            f"%  main.tex -- {paper_type} ({domain} domain)",
            "% =============================================================================",
            "%",
            "%  Build:   make all        (or: latexmk -pdf main.tex)",
            "%  Clean:   make clean",
            "%  Watch:   make watch",
            "%",
            "% =============================================================================",
        ]
    )

    # Document class
    if paper_type == "thesis-chapter":
        lines.append(
            f"\\documentclass[{doc_config['options']}]{{{doc_config['class']}}}"
        )
    else:
        lines.append(
            f"\\documentclass[{doc_config['options']}]{{{doc_config['class']}}}"
        )

    lines.append("")

    # Preamble
    lines.append(
        "% --- Shared preamble --------------------------------------------------------"
    )
    lines.append("\\input{preamble}")
    lines.append("\\input{preamble_extra}")
    lines.append("")

    # Geometry
    lines.append(
        "% --- Page geometry ----------------------------------------------------------"
    )
    lines.append(f"\\usepackage[{doc_config['geometry']}]{{geometry}}")
    lines.append("")

    # Spacing
    lines.append(
        "% --- Line spacing -----------------------------------------------------------"
    )
    lines.append("\\usepackage{setspace}")
    spacing_cmd = {
        "singlespacing": "\\singlespacing",
        "onehalfspacing": "\\onehalfspacing",
        "doublespacing": "\\doublespacing",
    }.get(doc_config["spacing"], "\\onehalfspacing")
    lines.append(f"{spacing_cmd}")
    lines.append("")

    # Line numbers for review
    lines.append(
        "% --- Line numbers (uncomment for review) ------------------------------------"
    )
    lines.append("% \\usepackage{lineno}")
    lines.append("% \\linenumbers")
    lines.append("")

    # Metadata
    lines.extend(
        [
            "% =============================================================================",
            "%  Metadata",
            "% =============================================================================",
        ]
    )

    if paper_type == "thesis-chapter":
        lines.extend(
            [
                "\\title{Chapter Title}",
                "\\author{Author Name}",
                "\\date{}",
            ]
        )
    else:
        lines.extend(
            [
                "\\title{%",
                "  \\textbf{A Descriptive Title That Clearly Communicates\\\\",
                "  the Main Finding of This Study}%",
                "}",
                "",
                "\\author{%",
                "  First~Author\\textsuperscript{1,*},\\quad",
                "  Second~Author\\textsuperscript{2},\\quad",
                "  Third~Author\\textsuperscript{1,2}\\\\[6pt]",
                "  \\small\\textsuperscript{1}Department of Example, University of Somewhere,",
                "    City, Country\\\\",
                "  \\small\\textsuperscript{2}Institute of Research, Organisation, City, Country\\\\[4pt]",
                "  \\small\\textsuperscript{*}Corresponding author:",
                "    \\href{mailto:first.author@example.com}{first.author@example.com}",
                "}",
                "",
                "\\date{}  % Suppress date; journals set their own",
            ]
        )

    lines.append("")
    lines.extend(
        [
            "% =============================================================================",
            "\\begin{document}",
            "% =============================================================================",
            "",
        ]
    )

    if paper_type == "thesis-chapter":
        lines.append("\\chapter{Chapter Title}")
        lines.append("\\label{ch:main}")
    else:
        lines.append("\\maketitle")
        lines.append("\\thispagestyle{empty}  % No page number on title page")

    lines.append("")

    # Abstract (not for thesis chapters)
    if paper_type != "thesis-chapter":
        lines.append(
            "% --- Abstract ---------------------------------------------------------------"
        )
        if paper_type == "conference-paper":
            lines.extend(
                [
                    "\\begin{abstract}",
                    "\\noindent",
                    "Brief description of the problem, approach, key results, and significance.",
                    "Keep within the conference word limit (typically 150--250 words).",
                    "\\end{abstract}",
                ]
            )
        elif domain == "biology":
            lines.extend(
                [
                    "\\begin{abstract}",
                    "\\noindent",
                    "\\textbf{Background.}\\quad",
                    "Provide context and motivation for the study.",
                    "%",
                    "\\textbf{Methods.}\\quad",
                    "Briefly describe the experimental or computational approach.",
                    "%",
                    "\\textbf{Results.}\\quad",
                    "State the key findings with quantitative detail.",
                    "%",
                    "\\textbf{Conclusions.}\\quad",
                    "Summarise the implications and significance.",
                    "",
                    "\\medskip",
                    "\\noindent",
                    "\\textbf{Keywords:}\\quad",
                    "keyword one, keyword two, keyword three, keyword four, keyword five",
                    "\\end{abstract}",
                ]
            )
        else:
            lines.extend(
                [
                    "\\begin{abstract}",
                    "\\noindent",
                    "A concise summary of the problem, approach, key results, and significance.",
                    "",
                    "\\medskip",
                    "\\noindent",
                    "\\textbf{Keywords:}\\quad",
                    "keyword one, keyword two, keyword three, keyword four, keyword five",
                    "\\end{abstract}",
                ]
            )
        lines.append("")
        lines.append("\\clearpage")
        lines.append("")

    # Sections
    for sec in sections:
        cmd = f"\\{sec['level']}"
        lines.extend(
            [
                "% =============================================================================",
                f"{cmd}{{{sec['title']}}}",
                f"\\label{{{sec['label']}}}",
                "% =============================================================================",
                "",
                f"% {sec['guidance']}",
                "",
                f"\\todo{{Write {sec['title'].lower()}.}}",
                "",
            ]
        )

    # Example figure and table for appropriate types
    if paper_type in ("journal-article", "conference-paper") and domain in (
        "ml",
        "nlp",
        "cv",
    ):
        lines.extend(
            [
                "% --- Example figure ---------------------------------------------------------",
                "% \\begin{figure}[htbp]",
                "%   \\centering",
                "%   \\includegraphics[width=0.8\\textwidth]{figures/placeholder.pdf}",
                "%   \\caption{%",
                "%     \\textbf{Model architecture.}",
                "%     Description of the architecture diagram.",
                "%   }",
                "%   \\label{fig:architecture}",
                "% \\end{figure}",
                "",
                "% --- Example results table --------------------------------------------------",
                "% \\begin{table}[htbp]",
                "%   \\centering",
                "%   \\caption{%",
                "%     \\textbf{Main results.}",
                "%     Comparison of methods on benchmark datasets. Best in \\textbf{bold}.",
                "%   }",
                "%   \\label{tab:results}",
                "%   \\begin{tabular}{@{} l S[table-format=2.1] S[table-format=2.1] S[table-format=2.1] @{}}",
                "%     \\toprule",
                "%     {Method} & {Dataset A} & {Dataset B} & {Dataset C} \\\\",
                "%     \\midrule",
                "%     Baseline        & 72.3 & 68.1 & 75.4 \\\\",
                "%     Our method      & \\textbf{89.7} & \\textbf{85.4} & \\textbf{91.2} \\\\",
                "%     \\bottomrule",
                "%   \\end{tabular}",
                "% \\end{table}",
                "",
            ]
        )

    # Example algorithm for ML/NLP/CV
    if domain in ("ml", "nlp", "cv"):
        lines.extend(
            [
                "% --- Example algorithm ------------------------------------------------------",
                "% \\begin{algorithm}[htbp]",
                "%   \\SetAlgoLined",
                "%   \\KwIn{Input data $\\mathcal{D}$, learning rate $\\eta$}",
                "%   \\KwOut{Trained model parameters $\\theta^*$}",
                "%   Initialize $\\theta$ randomly\\;",
                "%   \\For{epoch $= 1$ \\KwTo $E$}{",
                "%     \\For{mini-batch $(x, y) \\in \\mathcal{D}$}{",
                "%       Compute loss $\\mathcal{L}(f_\\theta(x), y)$\\;",
                "%       $\\theta \\leftarrow \\theta - \\eta \\nabla_\\theta \\mathcal{L}$\\;",
                "%     }",
                "%   }",
                "%   \\caption{Training procedure}",
                "%   \\label{alg:training}",
                "% \\end{algorithm}",
                "",
            ]
        )

    # Back matter
    lines.extend(
        [
            "% =============================================================================",
            "%  Back matter",
            "% =============================================================================",
            "",
        ]
    )

    back_matter_keys = _BACK_MATTER.get(paper_type, [])
    for key in back_matter_keys:
        if key in _BACK_MATTER_CONTENT:
            lines.append(_BACK_MATTER_CONTENT[key])

    # Bibliography
    lines.append(
        "% --- Bibliography -----------------------------------------------------------"
    )
    lines.append("\\bibliography{references}")
    lines.append("")

    # Supplementary
    if paper_type in ("journal-article", "review-paper"):
        lines.extend(
            [
                "% --- Supplementary (separate file) ------------------------------------------",
                "% \\clearpage",
                "% \\input{supplementary}",
                "",
            ]
        )

    lines.append("\\end{document}")
    lines.append("")

    return "\n".join(lines)


def _generate_supplementary_tex(
    paper_type: str,
    domain: str,
) -> str:
    """Generate supplementary.tex appropriate for the domain.

    Args:
        paper_type: One of PAPER_TYPES.
        domain: One of DOMAIN_TYPES.

    Returns:
        Complete supplementary.tex content string.
    """
    # For thesis chapters and technical reports, no supplementary needed
    if paper_type in ("thesis-chapter", "technical-report"):
        return ""

    lines = [
        "% =============================================================================",
        f"%  supplementary.tex -- Supplementary Materials ({domain} domain)",
        "% =============================================================================",
        "",
        "\\setcounter{section}{0}",
        "\\setcounter{figure}{0}",
        "\\setcounter{table}{0}",
        "\\setcounter{equation}{0}",
        "",
        "\\renewcommand{\\thesection}{S\\arabic{section}}",
        "\\renewcommand{\\thefigure}{S\\arabic{figure}}",
        "\\renewcommand{\\thetable}{S\\arabic{table}}",
        "\\renewcommand{\\theequation}{S\\arabic{equation}}",
        "",
        "\\crefname{section}{Supplementary Section}{Supplementary Sections}",
        "\\crefname{figure}{Supplementary Figure}{Supplementary Figures}",
        "\\crefname{table}{Supplementary Table}{Supplementary Tables}",
        "\\crefname{equation}{Supplementary Equation}{Supplementary Equations}",
        "",
        "\\clearpage",
        "\\begin{center}",
        "  {\\LARGE\\bfseries Supplementary Materials}",
        "\\end{center}",
        "",
        "\\bigskip",
        "\\tableofcontents",
        "",
    ]

    if domain in ("ml", "nlp", "cv"):
        lines.extend(
            [
                "% =============================================================================",
                "\\section{Implementation Details}",
                "\\label{sec:supp:implementation}",
                "% =============================================================================",
                "",
                "% Hyperparameters, compute resources, training time, random seeds.",
                "",
                "% =============================================================================",
                "\\section{Additional Results}",
                "\\label{sec:supp:results}",
                "% =============================================================================",
                "",
                "% Full benchmark tables, per-class breakdowns, additional ablations.",
                "",
                "% =============================================================================",
                "\\section{Supplementary Figures}",
                "\\label{sec:supp:figures}",
                "% =============================================================================",
                "",
                "% Additional visualisations, attention maps, t-SNE plots, etc.",
                "",
            ]
        )
    elif domain == "biology":
        lines.extend(
            [
                "% =============================================================================",
                "\\section{Supplementary Methods}",
                "\\label{sec:supp:methods}",
                "% =============================================================================",
                "",
                "% Extended protocols, reagent details, quality control steps.",
                "",
                "% =============================================================================",
                "\\section{Supplementary Figures}",
                "\\label{sec:supp:figures}",
                "% =============================================================================",
                "",
                "% Additional experimental data, flow cytometry plots, gel images, etc.",
                "",
                "% =============================================================================",
                "\\section{Supplementary Tables}",
                "\\label{sec:supp:tables}",
                "% =============================================================================",
                "",
                "% Full patient demographics, complete statistical results, etc.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "% =============================================================================",
                "\\section{Supplementary Methods}",
                "\\label{sec:supp:methods}",
                "% =============================================================================",
                "",
                "% Extended methodological detail.",
                "",
                "% =============================================================================",
                "\\section{Supplementary Figures}",
                "\\label{sec:supp:figures}",
                "% =============================================================================",
                "",
                "% =============================================================================",
                "\\section{Supplementary Tables}",
                "\\label{sec:supp:tables}",
                "% =============================================================================",
                "",
            ]
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_latex_scaffold(
    paper_dir: Path,
    paper_type: str = "journal-article",
    domain: str = "general",
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Generate a complete adaptive LaTeX scaffold in the paper directory.

    Creates or overwrites main.tex, preamble_extra.tex, supplementary.tex
    based on the paper type and detected domain. The base preamble.tex,
    Makefile, and references.bib are copied from templates if not present.

    Args:
        paper_dir: Directory to write LaTeX files into.
        paper_type: One of PAPER_TYPES.
        domain: One of DOMAIN_TYPES.
        overwrite: If True, overwrite existing files.

    Returns:
        Dict mapping file description to path of created file.
    """
    if paper_type not in PAPER_TYPES:
        logger.warning(
            "Unknown paper_type '%s', falling back to journal-article", paper_type
        )
        paper_type = "journal-article"

    if domain not in DOMAIN_TYPES:
        logger.warning("Unknown domain '%s', falling back to general", domain)
        domain = "general"

    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "figures").mkdir(parents=True, exist_ok=True)

    created: dict[str, Path] = {}

    # Copy base template files if not present
    template_paper_dir = Path(__file__).parent.parent / "templates" / "paper"
    for base_file in ("preamble.tex", "references.bib", "Makefile"):
        dest = paper_dir / base_file
        src = template_paper_dir / base_file
        if not dest.exists() and src.exists():
            shutil.copy2(src, dest)
            created[base_file] = dest

    # Copy journals directory if not present
    journals_src = template_paper_dir / "journals"
    journals_dst = paper_dir / "journals"
    if not journals_dst.exists() and journals_src.exists():
        shutil.copytree(journals_src, journals_dst)
        created["journals/"] = journals_dst

    # Generate adaptive files
    main_tex_path = paper_dir / "main.tex"
    if not main_tex_path.exists() or overwrite:
        main_tex_path.write_text(_generate_main_tex(paper_type, domain))
        created["main.tex"] = main_tex_path
        logger.info("Generated main.tex for %s/%s", paper_type, domain)

    preamble_extra_path = paper_dir / "preamble_extra.tex"
    if not preamble_extra_path.exists() or overwrite:
        preamble_extra_path.write_text(_generate_preamble_extra(paper_type, domain))
        created["preamble_extra.tex"] = preamble_extra_path
        logger.info("Generated preamble_extra.tex for %s/%s", paper_type, domain)

    supp_content = _generate_supplementary_tex(paper_type, domain)
    if supp_content:
        supp_path = paper_dir / "supplementary.tex"
        if not supp_path.exists() or overwrite:
            supp_path.write_text(supp_content)
            created["supplementary.tex"] = supp_path
            logger.info("Generated supplementary.tex for %s/%s", paper_type, domain)

    return created


def scaffold_from_config(
    project_path: Path,
    paper_type: str = "journal-article",
    project_type: str = "general",
    goal_text: str = "",
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    """High-level entry point: detect domain and generate scaffold.

    Reads GOAL.md if goal_text is not provided. Detects domain from
    goal content and project_type. Generates the full LaTeX scaffold.

    Args:
        project_path: Root of the research project.
        paper_type: Paper type selected during onboarding.
        project_type: Project type from config/onboarding.
        goal_text: Optional pre-read goal text.
        overwrite: If True, overwrite existing LaTeX files.

    Returns:
        Dict mapping file description to path of created file.
    """
    if not goal_text:
        goal_file = project_path / "knowledge" / "GOAL.md"
        if goal_file.exists():
            goal_text = goal_file.read_text()

    domain = detect_domain(goal_text, project_type)
    paper_dir = project_path / "paper"

    logger.info(
        "Generating LaTeX scaffold: paper_type=%s, domain=%s",
        paper_type,
        domain,
    )

    return generate_latex_scaffold(
        paper_dir,
        paper_type=paper_type,
        domain=domain,
        overwrite=overwrite,
    )
