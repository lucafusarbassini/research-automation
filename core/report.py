"""PDF report generator for integration test results.

Generates a Markdown report from captured command outputs, then converts
it to PDF using wkhtmltopdf, weasyprint, or a pure-Python fallback.
"""

import datetime
import logging
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """A single test step result."""

    step: int
    name: str
    command: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    passed: bool = True
    note: str = ""


@dataclass
class TestReport:
    """Collection of test results with metadata."""

    title: str = "ricet Integration Test Report"
    results: List[TestResult] = field(default_factory=list)
    started_at: Optional[datetime.datetime] = None
    finished_at: Optional[datetime.datetime] = None

    def add(self, result: TestResult) -> None:
        self.results.append(result)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    def to_markdown(self) -> str:
        """Render the report as Markdown."""
        lines: list[str] = []
        lines.append(f"# {self.title}")
        lines.append("")
        if self.started_at:
            lines.append(f"**Started:** {self.started_at.isoformat()}")
        if self.finished_at:
            lines.append(f"**Finished:** {self.finished_at.isoformat()}")
        lines.append(f"**Results:** {self.passed} passed, {self.failed} failed, {self.total} total")
        lines.append("")
        lines.append("---")
        lines.append("")

        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"## Step {r.step}: {r.name} [{status}]")
            lines.append("")
            lines.append(f"**Command:** `{r.command}`")
            lines.append("")
            if r.stdout.strip():
                # Truncate very long output
                out = r.stdout.strip()
                if len(out) > 2000:
                    out = out[:2000] + "\n... (truncated)"
                lines.append("**stdout:**")
                lines.append("```")
                lines.append(out)
                lines.append("```")
                lines.append("")
            if r.stderr.strip():
                err = r.stderr.strip()
                if len(err) > 1000:
                    err = err[:1000] + "\n... (truncated)"
                lines.append("**stderr:**")
                lines.append("```")
                lines.append(err)
                lines.append("```")
                lines.append("")
            if r.note:
                lines.append(f"**Note:** {r.note}")
                lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)


def _md_to_pdf_wkhtmltopdf(md_path: Path, pdf_path: Path) -> bool:
    """Convert markdown to PDF via wkhtmltopdf."""
    if not shutil.which("wkhtmltopdf"):
        return False
    # First convert md -> html (simple wrapping)
    html_path = md_path.with_suffix(".html")
    md_text = md_path.read_text()
    try:
        import markdown
        html_body = markdown.markdown(md_text, extensions=["fenced_code", "tables"])
    except ImportError:
        # Minimal fallback: wrap in <pre> tags
        html_body = f"<pre>{md_text}</pre>"

    html_content = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      body {{ font-family: monospace; font-size: 11px; margin: 20px; }}
      code, pre {{ background: #f4f4f4; padding: 4px; }}
      h1 {{ color: #333; }}
      h2 {{ color: #555; border-bottom: 1px solid #ccc; }}
      table {{ border-collapse: collapse; }}
      th, td {{ border: 1px solid #ccc; padding: 4px 8px; }}
    </style>
    </head>
    <body>
    {html_body}
    </body>
    </html>
    """)
    html_path.write_text(html_content)

    try:
        subprocess.run(
            ["wkhtmltopdf", "--quiet", str(html_path), str(pdf_path)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return pdf_path.exists()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    finally:
        html_path.unlink(missing_ok=True)


def _md_to_pdf_weasyprint(md_path: Path, pdf_path: Path) -> bool:
    """Convert markdown to PDF via weasyprint."""
    try:
        import markdown
        from weasyprint import HTML
    except ImportError:
        return False

    md_text = md_path.read_text()
    html_body = markdown.markdown(md_text, extensions=["fenced_code", "tables"])
    html_content = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8">
    <style>
      body {{ font-family: monospace; font-size: 10px; margin: 15px; }}
      code, pre {{ background: #f4f4f4; padding: 3px; font-size: 9px; }}
      h1 {{ font-size: 16px; }}
      h2 {{ font-size: 13px; border-bottom: 1px solid #ccc; }}
    </style>
    </head>
    <body>{html_body}</body>
    </html>
    """)
    try:
        HTML(string=html_content).write_pdf(str(pdf_path))
        return pdf_path.exists()
    except Exception as e:
        logger.debug("weasyprint failed: %s", e)
        return False


def _md_to_pdf_plain(md_path: Path, pdf_path: Path) -> bool:
    """Pure-Python fallback: generate a minimal PDF from text."""
    text = md_path.read_text()
    # Minimal PDF structure
    lines_list = text.split("\n")
    page_content = []
    for line in lines_list:
        # Escape special PDF chars
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        page_content.append(safe)

    text_block = "\\n".join(page_content[:500])  # Cap at 500 lines per page

    pdf_bytes = textwrap.dedent(f"""\
    %PDF-1.4
    1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
    2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
    3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
    5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Courier>>endobj
    4 0 obj
    <</Length {len(text_block) + 50}>>
    stream
    BT /F1 7 Tf 36 756 Td 9 TL ({text_block}) Tj ET
    endstream
    endobj
    xref
    0 6
    trailer<</Size 6/Root 1 0 R>>
    startxref
    0
    %%EOF
    """).encode()

    pdf_path.write_bytes(pdf_bytes)
    return True


def generate_pdf_report(report: TestReport, output_dir: Path) -> Path:
    """Generate a PDF report from test results.

    Tries wkhtmltopdf -> weasyprint -> plain PDF fallback.

    Returns:
        Path to the generated PDF file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "integration_report.md"
    pdf_path = output_dir / "integration_report.pdf"

    md_path.write_text(report.to_markdown())

    if _md_to_pdf_wkhtmltopdf(md_path, pdf_path):
        logger.info("PDF generated via wkhtmltopdf: %s", pdf_path)
    elif _md_to_pdf_weasyprint(md_path, pdf_path):
        logger.info("PDF generated via weasyprint: %s", pdf_path)
    else:
        _md_to_pdf_plain(md_path, pdf_path)
        logger.info("PDF generated via plain fallback: %s", pdf_path)

    return pdf_path
