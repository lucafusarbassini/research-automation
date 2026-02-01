"""Browser integration module.

Provides ``BrowserSession`` — a unified interface for headless-browser
automation.  When a Puppeteer MCP server is reachable the session delegates
to it; otherwise it falls back to basic HTTP fetching via *curl/wget* and
lightweight subprocess tools (e.g. ``wkhtmltopdf`` for PDF generation,
``cutycapt`` for screenshots).
"""

from __future__ import annotations

import html.parser
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight HTML-to-text helper (no external dependency)
# ---------------------------------------------------------------------------


class _HTMLTextExtractor(html.parser.HTMLParser):
    """Minimal HTML→plain-text converter."""

    _SKIP_TAGS = frozenset({"script", "style", "head"})

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._pieces.append(data)

    def get_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._pieces)).strip()


def _html_to_text(html_source: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html_source)
    return parser.get_text()


# ---------------------------------------------------------------------------
# BrowserSession
# ---------------------------------------------------------------------------


class BrowserSession:
    """Unified browser-automation session.

    Parameters
    ----------
    puppeteer_server : str, optional
        Address of a running Puppeteer MCP server.  When *None* the class
        attempts auto-detection via ``_detect_puppeteer``.
    """

    def __init__(self, puppeteer_server: Optional[str] = None) -> None:
        self._puppeteer_available: bool = self._detect_puppeteer()
        self._puppeteer_server = puppeteer_server

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return *True* when at least one automation backend is usable."""
        if self._puppeteer_available:
            return True
        # Fallback: need curl or wget for basic HTTP fetching
        return shutil.which("curl") is not None or shutil.which("wget") is not None

    def screenshot(self, url: str, output: Path) -> Path:
        """Capture a full-page screenshot and save it to *output*.

        Returns the path to the written file.
        """
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        if self._puppeteer_available:
            self._puppeteer_call("screenshot", url=url, output=str(output))
            return output

        # Fallback: try cutycapt / wkhtmltoimage / chromium headless
        cmd = self._find_screenshot_cmd(url, output)
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return output

    def extract_text(self, url: str) -> str:
        """Extract visible text content from a page."""
        if self._puppeteer_available:
            result = self._puppeteer_call("extract_text", url=url)
            return result.get("text", "")

        # Fallback: fetch HTML and strip tags
        html_source = self._http_get(url)
        return _html_to_text(html_source)

    def fill_form(self, url: str, fields: dict) -> bool:
        """Fill form fields on *url* and submit.

        Returns *True* on success.  The fallback backend cannot interact with
        a live DOM, so it always returns *False*.
        """
        if not self._puppeteer_available:
            logger.warning(
                "fill_form requires Puppeteer — unavailable, returning False"
            )
            return False

        result = self._puppeteer_call("fill_form", url=url, fields=fields)
        return bool(result.get("submitted", False))

    def wait_for_element(self, url: str, selector: str, timeout: int = 10) -> bool:
        """Wait for a CSS *selector* to appear on *url*.

        Returns *True* if the element is found within *timeout* seconds.
        The fallback backend cannot evaluate selectors, so it returns *False*.
        """
        if not self._puppeteer_available:
            logger.warning(
                "wait_for_element requires Puppeteer — unavailable, returning False"
            )
            return False

        result = self._puppeteer_call(
            "wait_for_element", url=url, selector=selector, timeout=timeout
        )
        return bool(result.get("found", False))

    def generate_pdf(self, url: str, output: Path) -> Path:
        """Render *url* as PDF and save to *output*.

        Returns the path to the written file.
        """
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        if self._puppeteer_available:
            self._puppeteer_call("generate_pdf", url=url, output=str(output))
            return output

        # Fallback: wkhtmltopdf or chromium --print-to-pdf
        cmd = self._find_pdf_cmd(url, output)
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return output

    # ------------------------------------------------------------------
    # Puppeteer MCP plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_puppeteer() -> bool:
        """Check whether the Puppeteer MCP server is reachable."""
        try:
            result = subprocess.run(
                ["npx", "@anthropic-ai/puppeteer-mcp", "--version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _puppeteer_call(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        """Send a command to the Puppeteer MCP server and return JSON result."""
        payload = json.dumps({"action": action, **kwargs})
        try:
            result = subprocess.run(
                ["npx", "@anthropic-ai/puppeteer-mcp", "--run", payload],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return json.loads(result.stdout) if result.stdout else {}
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ) as exc:
            logger.error("Puppeteer call failed (%s): %s", action, exc)
            return {}

    # ------------------------------------------------------------------
    # Fallback helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _http_get(url: str) -> str:
        """Fetch raw HTML via curl (preferred) or wget."""
        curl = shutil.which("curl")
        if curl:
            result = subprocess.run(
                [curl, "-sL", "--max-time", "15", url],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return result.stdout
        wget = shutil.which("wget")
        if wget:
            result = subprocess.run(
                [wget, "-qO-", url],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return result.stdout
        raise RuntimeError("Neither curl nor wget found on PATH")

    @staticmethod
    def _find_screenshot_cmd(url: str, output: Path) -> list[str]:
        """Build a CLI command for taking a screenshot."""
        for tool, builder in [
            (
                "chromium-browser",
                lambda t: [
                    t,
                    "--headless",
                    "--disable-gpu",
                    f"--screenshot={output}",
                    url,
                ],
            ),
            (
                "google-chrome",
                lambda t: [
                    t,
                    "--headless",
                    "--disable-gpu",
                    f"--screenshot={output}",
                    url,
                ],
            ),
            ("cutycapt", lambda t: [t, f"--url={url}", f"--out={output}"]),
            ("wkhtmltoimage", lambda t: [t, url, str(output)]),
        ]:
            path = shutil.which(tool)
            if path:
                return builder(path)
        raise RuntimeError(
            "No screenshot tool found (need chromium, cutycapt, or wkhtmltoimage)"
        )

    @staticmethod
    def _find_pdf_cmd(url: str, output: Path) -> list[str]:
        """Build a CLI command for rendering a page to PDF."""
        for tool, builder in [
            (
                "chromium-browser",
                lambda t: [
                    t,
                    "--headless",
                    "--disable-gpu",
                    f"--print-to-pdf={output}",
                    url,
                ],
            ),
            (
                "google-chrome",
                lambda t: [
                    t,
                    "--headless",
                    "--disable-gpu",
                    f"--print-to-pdf={output}",
                    url,
                ],
            ),
            ("wkhtmltopdf", lambda t: [t, url, str(output)]),
        ]:
            path = shutil.which(tool)
            if path:
                return builder(path)
        raise RuntimeError("No PDF tool found (need chromium or wkhtmltopdf)")
