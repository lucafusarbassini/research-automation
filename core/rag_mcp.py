"""RAG index for MCP server discovery and suggestion.

Provides a searchable index of MCP (Model Context Protocol) servers so the
system can dynamically discover the right MCP for any given task.

The comprehensive catalog lives at ``defaults/raggable_mcps.md`` (1 300+
servers).  :func:`parse_raggable_catalog` converts it into
:class:`MCPEntry` objects that can be fed into :class:`MCPIndex` for
keyword search, used as a fallback when Claude is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

RAGGABLE_CATALOG_PATH = Path(__file__).parent.parent / "defaults" / "raggable_mcps.md"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MCPEntry:
    """Describes a single MCP server available for installation/use."""

    name: str
    description: str
    category: str
    keywords: list[str]
    install_command: str
    config_template: dict[str, Any]
    url: str

    # -- serialization helpers ------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPEntry":
        required = {
            "name",
            "description",
            "category",
            "keywords",
            "install_command",
            "config_template",
            "url",
        }
        missing = required - set(data.keys())
        if missing:
            raise KeyError(f"Missing required fields: {missing}")
        return cls(**{k: data[k] for k in required})


# ---------------------------------------------------------------------------
# Searchable index
# ---------------------------------------------------------------------------


class MCPIndex:
    """Keyword-searchable index of MCP servers."""

    def __init__(self) -> None:
        self.entries: list[MCPEntry] = []
        self._token_map: dict[str, list[int]] = {}  # token -> list of entry indices

    # -- index construction ---------------------------------------------------

    def build_index(self, entries: list[MCPEntry]) -> None:
        """Build (or rebuild) the searchable index from a list of entries."""
        self.entries = list(entries)
        self._token_map = {}
        for idx, entry in enumerate(self.entries):
            tokens = self._tokenize_entry(entry)
            for token in tokens:
                self._token_map.setdefault(token, []).append(idx)

    @staticmethod
    def _tokenize_entry(entry: MCPEntry) -> set[str]:
        """Extract searchable tokens from an entry."""
        parts: list[str] = []
        parts.append(entry.name)
        parts.append(entry.description)
        parts.append(entry.category)
        parts.extend(entry.keywords)
        text = " ".join(parts).lower()
        return {t for t in text.split() if len(t) > 1}

    # -- search ---------------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> list[MCPEntry]:
        """Keyword search over the index.

        Each entry is scored by how many query tokens appear in its
        tokenized representation.  Results are returned in descending
        score order, limited to *top_k*.
        """
        query_tokens = {t.lower() for t in query.split() if len(t) > 1}
        if not query_tokens:
            return []

        scores: dict[int, int] = {}
        for token in query_tokens:
            for idx in self._token_map.get(token, []):
                scores[idx] = scores.get(idx, 0) + 1

        if not scores:
            return []

        ranked = sorted(scores, key=lambda i: scores[i], reverse=True)
        return [self.entries[i] for i in ranked[:top_k]]

    def suggest_mcps(self, task_description: str) -> list[MCPEntry]:
        """Suggest MCP servers relevant to a natural-language task description.

        Performs a broadened keyword search: individual words from the task
        description are matched against entry tokens.
        """
        return self.search(task_description, top_k=5)

    # -- persistence ----------------------------------------------------------

    def save_to_json(self, path: Path) -> None:
        """Serialize the current index entries to a JSON file."""
        data = [e.to_dict() for e in self.entries]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_json(self, path: Path) -> None:
        """Load entries from a JSON file and rebuild the index."""
        with open(path) as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            raise TypeError("Expected a JSON array of MCP entries")
        entries = [MCPEntry.from_dict(item) for item in raw]
        self.build_index(entries)

    # -- installation ---------------------------------------------------------

    def install_suggested(self, entries: list[MCPEntry]) -> dict[str, bool]:
        """Attempt to install each suggested MCP and report success/failure."""
        results: dict[str, bool] = {}
        for entry in entries:
            try:
                subprocess.run(
                    entry.install_command,
                    shell=True,
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
                results[entry.name] = True
            except Exception:
                results[entry.name] = False
        return results


# ---------------------------------------------------------------------------
# Pre-populated default entries
# ---------------------------------------------------------------------------

DEFAULT_ENTRIES: list[MCPEntry] = [
    MCPEntry(
        name="filesystem",
        description="Read, write, and manage files on the local filesystem",
        category="core",
        keywords=["file", "read", "write", "directory", "fs", "path"],
        install_command="npx -y @modelcontextprotocol/server-filesystem /tmp",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
    ),
    MCPEntry(
        name="git",
        description="Git repository operations including clone, commit, diff, and log",
        category="core",
        keywords=[
            "git",
            "repository",
            "commit",
            "diff",
            "version",
            "control",
            "branch",
        ],
        install_command="npx -y @modelcontextprotocol/server-git",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-git"],
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/git",
    ),
    MCPEntry(
        name="memory",
        description="Persistent memory and knowledge graph for long-term context",
        category="core",
        keywords=["memory", "knowledge", "graph", "persist", "remember", "store"],
        install_command="npx -y @modelcontextprotocol/server-memory",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
    ),
    MCPEntry(
        name="fetch",
        description="Fetch content from URLs and APIs over HTTP/HTTPS",
        category="core",
        keywords=["fetch", "http", "url", "api", "request", "download", "web"],
        install_command="npx -y @modelcontextprotocol/server-fetch",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-fetch"],
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
    ),
    MCPEntry(
        name="puppeteer",
        description="Browser automation with Puppeteer for web scraping and testing",
        category="browser",
        keywords=[
            "browser",
            "web",
            "scrape",
            "puppeteer",
            "automation",
            "screenshot",
            "headless",
        ],
        install_command="npx -y @modelcontextprotocol/server-puppeteer",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/puppeteer",
    ),
    MCPEntry(
        name="sequential-thinking",
        description="Chain-of-thought reasoning with structured sequential thinking",
        category="reasoning",
        keywords=[
            "thinking",
            "reasoning",
            "chain",
            "thought",
            "sequential",
            "logic",
            "plan",
        ],
        install_command="npx -y @modelcontextprotocol/server-sequential-thinking",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking",
    ),
    MCPEntry(
        name="apidog",
        description="API design, testing, and documentation with Apidog integration",
        category="api",
        keywords=[
            "api",
            "rest",
            "openapi",
            "swagger",
            "test",
            "design",
            "endpoint",
            "apidog",
        ],
        install_command="npx -y apidog-mcp-server",
        config_template={
            "command": "npx",
            "args": ["-y", "apidog-mcp-server"],
        },
        url="https://github.com/anthropics/mcp-servers",
    ),
    MCPEntry(
        name="arxiv",
        description="Search and retrieve academic papers from arXiv",
        category="research",
        keywords=[
            "arxiv",
            "paper",
            "academic",
            "research",
            "science",
            "publication",
            "preprint",
        ],
        install_command="pip install arxiv-mcp-server",
        config_template={
            "command": "python",
            "args": ["-m", "arxiv_mcp_server"],
        },
        url="https://github.com/arxiv-mcp/arxiv-mcp-server",
    ),
    MCPEntry(
        name="github",
        description="GitHub API access for issues, pull requests, and repository management",
        category="development",
        keywords=["github", "issue", "pull", "request", "pr", "repo", "ci", "actions"],
        install_command="npx -y @modelcontextprotocol/server-github",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>"},
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/github",
    ),
    MCPEntry(
        name="postgres",
        description="Query and manage PostgreSQL databases",
        category="database",
        keywords=["postgres", "postgresql", "database", "sql", "query", "db", "table"],
        install_command="npx -y @modelcontextprotocol/server-postgres",
        config_template={
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-postgres",
                "postgresql://localhost/mydb",
            ],
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/postgres",
    ),
    MCPEntry(
        name="sqlite",
        description="Query and manage SQLite databases",
        category="database",
        keywords=["sqlite", "database", "sql", "query", "db", "table", "embedded"],
        install_command="npx -y @modelcontextprotocol/server-sqlite",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sqlite", "db.sqlite"],
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite",
    ),
    MCPEntry(
        name="slack",
        description="Send and receive messages via Slack workspaces",
        category="communication",
        keywords=["slack", "message", "chat", "channel", "notification", "team"],
        install_command="npx -y @modelcontextprotocol/server-slack",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-slack"],
            "env": {"SLACK_BOT_TOKEN": "<your-token>"},
        },
        url="https://github.com/modelcontextprotocol/servers/tree/main/src/slack",
    ),
]


# ---------------------------------------------------------------------------
# Parse defaults/raggable_mcps.md into MCPEntry objects
# ---------------------------------------------------------------------------

# Regex matching lines like:
#   owner/repo 📇 ☁️ 🏠 - Description text here
# or:
#   name-of-server 🐍 ☁️ - Description text here
_ENTRY_RE = re.compile(
    r"^(?P<name>\S+)"        # name/repo (no spaces)
    r"\s+"
    r"(?P<badges>[^-]*?)"    # emoji badges (optional)
    r"\s*-\s+"
    r"(?P<desc>.+)$"         # description after the dash
)

# Category headers look like: 🔗 Aggregators  or  ## Biology, Medicine ...
_CATEGORY_RE = re.compile(r"^(?:[#]+\s*)?(?:\S+\s+)?(?P<cat>[A-Z][\w &,/]+)", re.IGNORECASE)


def parse_raggable_catalog(
    path: Path | None = None,
) -> list[MCPEntry]:
    """Parse ``defaults/raggable_mcps.md`` into :class:`MCPEntry` objects.

    Each line that matches ``owner/repo <badges> - description`` is
    converted into an MCPEntry suitable for keyword search.  Category
    headers are tracked and assigned as the ``category`` field.

    Returns an empty list if the file is missing or cannot be parsed.
    """
    catalog_path = path or RAGGABLE_CATALOG_PATH
    if not catalog_path.exists():
        logger.debug("raggable_mcps.md not found at %s", catalog_path)
        return []

    entries: list[MCPEntry] = []
    current_category = "general"

    for line in catalog_path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Detect category headers (emoji + title, or ## title)
        if stripped.startswith(("#", "\U0001f517", "\U0001f680", "\U0001f3a8",
                                "\U0001f4d0", "\U0001f9ec", "\U0001f4ac",
                                "\u2601", "\U0001f4bc", "\U0001f4ca",
                                "\U0001f527", "\U0001f3ae", "\U0001f310",
                                "\U0001f512", "\U0001f4d6")):
            # Try to extract a clean category name
            cat_match = _CATEGORY_RE.match(stripped.lstrip("#").strip())
            if cat_match:
                current_category = cat_match.group("cat").strip()
            continue

        # Try to parse an entry line
        m = _ENTRY_RE.match(stripped)
        if not m:
            # Some category header lines don't start with emoji
            if not any(c.isalnum() for c in stripped[:3]):
                continue
            # Could be a continuation or description line — skip
            continue

        name = m.group("name").rstrip("/")
        desc = m.group("desc").strip()

        # Extract keywords from the name (split on / and -) and description
        name_tokens = re.split(r"[/\-_]", name.lower())
        desc_tokens = [w.lower() for w in desc.split() if len(w) > 2]
        keywords = list(set(name_tokens + desc_tokens[:10]))

        # Build a plausible install command from the name
        if "/" in name:
            # GitHub-style: owner/repo
            repo_url = f"https://github.com/{name}"
            install_cmd = f"npx -y {name.split('/')[-1]}"
        else:
            repo_url = ""
            install_cmd = f"npx -y {name}"

        entries.append(
            MCPEntry(
                name=name.split("/")[-1] if "/" in name else name,
                description=desc,
                category=current_category,
                keywords=keywords,
                install_command=install_cmd,
                config_template={},
                url=repo_url,
            )
        )

    logger.debug("Parsed %d entries from raggable_mcps.md", len(entries))
    return entries
