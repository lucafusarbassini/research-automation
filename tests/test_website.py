"""Tests for the website making/updating module."""

import json
from pathlib import Path
from unittest.mock import patch

from core.website import (
    WebsiteProject,
    add_page,
    add_publication,
    build_site,
    deploy_site,
    init_website,
    preview_site,
    update_cv,
    update_page,
)


# ---------------------------------------------------------------------------
# 1. init_website
# ---------------------------------------------------------------------------

def test_init_website_academic(tmp_path: Path):
    """init_website creates an academic site scaffold with expected files."""
    project = init_website(tmp_path / "mysite", template="academic")
    assert project.exists()
    assert (project / "index.html").exists()
    assert (project / "css" / "style.css").exists()
    assert (project / "publications.html").exists()
    assert (project / "cv.html").exists()
    # Site config should be written
    config = json.loads((project / "site.json").read_text())
    assert config["template"] == "academic"


def test_init_website_minimal(tmp_path: Path):
    """init_website with 'minimal' template creates a simpler scaffold."""
    project = init_website(tmp_path / "simple", template="minimal")
    assert project.exists()
    assert (project / "index.html").exists()
    assert (project / "css" / "style.css").exists()
    # Minimal template should NOT have publications or cv pages
    assert not (project / "publications.html").exists()
    assert not (project / "cv.html").exists()


def test_init_website_idempotent(tmp_path: Path):
    """Calling init_website twice does not destroy existing content."""
    project = init_website(tmp_path / "site", template="academic")
    (project / "index.html").write_text("<h1>Custom</h1>")
    init_website(tmp_path / "site", template="academic")
    assert "<h1>Custom</h1>" in (project / "index.html").read_text()


# ---------------------------------------------------------------------------
# 2. WebsiteProject
# ---------------------------------------------------------------------------

def test_website_project_pages(tmp_path: Path):
    """WebsiteProject.pages lists all HTML pages in the project."""
    project_path = init_website(tmp_path / "proj", template="academic")
    wp = WebsiteProject(project_path)
    pages = wp.pages
    assert "index.html" in pages
    assert "publications.html" in pages


def test_website_project_config(tmp_path: Path):
    """WebsiteProject exposes the site config."""
    project_path = init_website(tmp_path / "proj", template="academic")
    wp = WebsiteProject(project_path)
    assert wp.config["template"] == "academic"


# ---------------------------------------------------------------------------
# 3. update_page
# ---------------------------------------------------------------------------

def test_update_page_success(tmp_path: Path):
    """update_page replaces a page's content and returns True."""
    project_path = init_website(tmp_path / "site", template="academic")
    result = update_page("index.html", "<h1>Hello World</h1>", project_path)
    assert result is True
    assert "<h1>Hello World</h1>" in (project_path / "index.html").read_text()


def test_update_page_nonexistent(tmp_path: Path):
    """update_page returns False for a page that doesn't exist."""
    project_path = init_website(tmp_path / "site", template="academic")
    result = update_page("nonexistent.html", "content", project_path)
    assert result is False


# ---------------------------------------------------------------------------
# 4. add_page
# ---------------------------------------------------------------------------

def test_add_page(tmp_path: Path):
    """add_page creates a new page and adds it to the navigation."""
    project_path = init_website(tmp_path / "site", template="academic")
    new_page = add_page("Research", "<p>My research interests.</p>", project_path)
    assert new_page.exists()
    assert "research" in new_page.name.lower()
    content = new_page.read_text()
    assert "My research interests." in content
    assert "<title>" in content  # wrapped in proper HTML


# ---------------------------------------------------------------------------
# 5. build_site
# ---------------------------------------------------------------------------

def test_build_site(tmp_path: Path):
    """build_site copies files to a _build directory and returns True."""
    project_path = init_website(tmp_path / "site", template="academic")
    result = build_site(project_path)
    assert result is True
    build_dir = project_path / "_build"
    assert build_dir.exists()
    assert (build_dir / "index.html").exists()
    assert (build_dir / "css" / "style.css").exists()


# ---------------------------------------------------------------------------
# 6. deploy_site
# ---------------------------------------------------------------------------

def test_deploy_site_github_pages(tmp_path: Path):
    """deploy_site returns a dict with deployment info."""
    project_path = init_website(tmp_path / "site", template="academic")
    build_site(project_path)
    result = deploy_site(project_path, method="github-pages")
    assert isinstance(result, dict)
    assert result["method"] == "github-pages"
    assert result["status"] == "ready"
    # Should have created/verified a _build directory
    assert (project_path / "_build").exists()


def test_deploy_site_unsupported_method(tmp_path: Path):
    """deploy_site returns error status for unsupported methods."""
    project_path = init_website(tmp_path / "site", template="academic")
    build_site(project_path)
    result = deploy_site(project_path, method="ftp-magic")
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 7. add_publication
# ---------------------------------------------------------------------------

def test_add_publication(tmp_path: Path):
    """add_publication appends a publication entry to publications.html."""
    project_path = init_website(tmp_path / "site", template="academic")
    bib = (
        "@article{smith2025,\n"
        "  author = {Smith, Alice},\n"
        "  title = {Great Paper},\n"
        "  journal = {Nature},\n"
        "  year = {2025}\n"
        "}"
    )
    result = add_publication(bib, project_path)
    assert result is True
    content = (project_path / "publications.html").read_text()
    assert "Great Paper" in content
    assert "Smith" in content


def test_add_publication_no_page(tmp_path: Path):
    """add_publication returns False if publications page does not exist."""
    project_path = init_website(tmp_path / "site", template="minimal")
    result = add_publication("@article{x, title={Y}}", project_path)
    assert result is False


# ---------------------------------------------------------------------------
# 8. update_cv
# ---------------------------------------------------------------------------

def test_update_cv(tmp_path: Path):
    """update_cv updates a section of the CV page."""
    project_path = init_website(tmp_path / "site", template="academic")
    result = update_cv("education", "<li>PhD, MIT, 2025</li>", project_path)
    assert result is True
    content = (project_path / "cv.html").read_text()
    assert "PhD, MIT, 2025" in content


def test_update_cv_no_page(tmp_path: Path):
    """update_cv returns False when cv.html does not exist."""
    project_path = init_website(tmp_path / "site", template="minimal")
    result = update_cv("education", "stuff", project_path)
    assert result is False


# ---------------------------------------------------------------------------
# 9. preview_site
# ---------------------------------------------------------------------------

def test_preview_site(tmp_path: Path):
    """preview_site returns the local URL and can be stopped."""
    project_path = init_website(tmp_path / "site", template="academic")
    build_site(project_path)
    with patch("core.website.HTTPServer") as mock_server_cls:
        mock_instance = mock_server_cls.return_value
        mock_instance.server_address = ("", 8000)
        url = preview_site(project_path, port=8000)
        assert "8000" in url
        assert "localhost" in url or "127.0.0.1" in url
