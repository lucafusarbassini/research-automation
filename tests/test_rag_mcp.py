"""Tests for RAG-based MCP server index and discovery."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from core.rag_mcp import DEFAULT_ENTRIES, MCPEntry, MCPIndex


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_entries() -> list[MCPEntry]:
    return [
        MCPEntry(
            name="filesystem",
            description="Read, write, and manage files on the local filesystem",
            category="core",
            keywords=["file", "read", "write", "directory", "fs"],
            install_command="npx -y @modelcontextprotocol/server-filesystem",
            config_template={"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]},
            url="https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
        ),
        MCPEntry(
            name="git",
            description="Git repository operations including clone, commit, diff, and log",
            category="core",
            keywords=["git", "repository", "commit", "diff", "version control"],
            install_command="npx -y @modelcontextprotocol/server-git",
            config_template={"command": "npx", "args": ["-y", "@modelcontextprotocol/server-git"]},
            url="https://github.com/modelcontextprotocol/servers/tree/main/src/git",
        ),
        MCPEntry(
            name="puppeteer",
            description="Browser automation with Puppeteer for web scraping and testing",
            category="browser",
            keywords=["browser", "web", "scrape", "puppeteer", "automation", "screenshot"],
            install_command="npx -y @modelcontextprotocol/server-puppeteer",
            config_template={"command": "npx", "args": ["-y", "@modelcontextprotocol/server-puppeteer"]},
            url="https://github.com/modelcontextprotocol/servers/tree/main/src/puppeteer",
        ),
    ]


@pytest.fixture
def index(sample_entries) -> MCPIndex:
    idx = MCPIndex()
    idx.build_index(sample_entries)
    return idx


@pytest.fixture
def empty_index() -> MCPIndex:
    return MCPIndex()


# ---------------------------------------------------------------------------
# MCPEntry dataclass tests
# ---------------------------------------------------------------------------

class TestMCPEntry:
    def test_creation(self):
        entry = MCPEntry(
            name="test-mcp",
            description="A test MCP server",
            category="testing",
            keywords=["test", "mock"],
            install_command="npm install test-mcp",
            config_template={"command": "node", "args": ["test"]},
            url="https://example.com",
        )
        assert entry.name == "test-mcp"
        assert entry.category == "testing"
        assert "test" in entry.keywords

    def test_serialization_roundtrip(self, sample_entries):
        entry = sample_entries[0]
        as_dict = entry.to_dict()
        restored = MCPEntry.from_dict(as_dict)
        assert restored.name == entry.name
        assert restored.keywords == entry.keywords
        assert restored.config_template == entry.config_template


# ---------------------------------------------------------------------------
# MCPIndex core tests
# ---------------------------------------------------------------------------

class TestMCPIndexBuild:
    def test_build_index_populates_entries(self, index, sample_entries):
        assert len(index.entries) == len(sample_entries)

    def test_build_index_empty_list(self, empty_index):
        empty_index.build_index([])
        assert len(empty_index.entries) == 0

    def test_build_index_replaces_previous(self, index, sample_entries):
        """Building again should replace, not append."""
        index.build_index(sample_entries[:1])
        assert len(index.entries) == 1


class TestMCPIndexSearch:
    def test_search_by_keyword(self, index):
        results = index.search("git")
        assert any(e.name == "git" for e in results)

    def test_search_returns_top_k(self, index):
        results = index.search("file", top_k=1)
        assert len(results) <= 1

    def test_search_no_results(self, index):
        results = index.search("zzzznonexistent")
        assert results == []

    def test_search_matches_description(self, index):
        results = index.search("browser automation")
        assert any(e.name == "puppeteer" for e in results)

    def test_search_case_insensitive(self, index):
        lower = index.search("git")
        upper = index.search("GIT")
        assert lower == upper


class TestSuggestMCPs:
    def test_suggest_for_file_task(self, index):
        results = index.suggest_mcps("I need to read and write files on disk")
        assert any(e.name == "filesystem" for e in results)

    def test_suggest_for_web_task(self, index):
        results = index.suggest_mcps("scrape a website and take screenshots")
        assert any(e.name == "puppeteer" for e in results)

    def test_suggest_returns_list(self, index):
        results = index.suggest_mcps("do something")
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load_json(self, index):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            index.save_to_json(path)
            assert path.exists()

            new_index = MCPIndex()
            new_index.load_from_json(path)
            assert len(new_index.entries) == len(index.entries)
            assert new_index.entries[0].name == index.entries[0].name
        finally:
            path.unlink(missing_ok=True)

    def test_load_json_validates(self, empty_index):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"bad": "data"}, f)
            path = Path(f.name)

        try:
            with pytest.raises((KeyError, TypeError, ValueError)):
                empty_index.load_from_json(path)
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Default entries
# ---------------------------------------------------------------------------

class TestDefaultEntries:
    def test_default_entries_exist(self):
        assert len(DEFAULT_ENTRIES) >= 8

    def test_default_entries_are_mcp_entries(self):
        for entry in DEFAULT_ENTRIES:
            assert isinstance(entry, MCPEntry)

    def test_default_entries_have_required_fields(self):
        for entry in DEFAULT_ENTRIES:
            assert entry.name
            assert entry.description
            assert entry.category
            assert entry.keywords


# ---------------------------------------------------------------------------
# Install suggested
# ---------------------------------------------------------------------------

class TestInstallSuggested:
    @patch("core.rag_mcp.subprocess.run")
    def test_install_suggested_success(self, mock_run, sample_entries):
        mock_run.return_value = None  # no exception means success
        idx = MCPIndex()
        result = idx.install_suggested(sample_entries[:1])
        assert result["filesystem"] is True
        mock_run.assert_called_once()

    @patch("core.rag_mcp.subprocess.run", side_effect=Exception("fail"))
    def test_install_suggested_failure(self, mock_run, sample_entries):
        idx = MCPIndex()
        result = idx.install_suggested(sample_entries[:1])
        assert result["filesystem"] is False
