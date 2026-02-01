"""Phase 6 demo tests: website, social media, and notifications."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.website import (
    WebsiteProject,
    add_page,
    add_publication,
    build_site,
    deploy_site,
    init_website,
    site_manager,
)
from core.social_media import (
    PostDraft,
    draft_linkedin_post,
    draft_medium_post,
    generate_thread,
    publish_to_platform,
    summarize_for_social,
    validate_post,
)
from core.notifications import NotificationConfig


# ---------------------------------------------------------------------------
# website: init_website (academic template)
# ---------------------------------------------------------------------------


class TestInitWebsiteAcademic:
    """init_website with 'academic' template creates the expected scaffold."""

    def test_creates_scaffold(self, tmp_path):
        site_dir = tmp_path / "mysite"
        result = init_website(site_dir, template="academic")

        assert result == site_dir
        assert (site_dir / "index.html").exists()
        assert (site_dir / "publications.html").exists()
        assert (site_dir / "cv.html").exists()
        assert (site_dir / "css" / "style.css").exists()
        assert (site_dir / "site.json").exists()

        config = json.loads((site_dir / "site.json").read_text())
        assert config["template"] == "academic"

    def test_idempotent(self, tmp_path):
        site_dir = tmp_path / "mysite"
        init_website(site_dir, template="academic")
        # Write custom content to index.html
        custom = "CUSTOM CONTENT"
        (site_dir / "index.html").write_text(custom)
        # Re-init should NOT overwrite existing files
        init_website(site_dir, template="academic")
        assert (site_dir / "index.html").read_text() == custom


# ---------------------------------------------------------------------------
# website: add_page
# ---------------------------------------------------------------------------


class TestWebsiteAddPage:
    """add_page creates a new HTML page and updates site config."""

    def test_add_page_creates_file(self, tmp_path):
        site_dir = tmp_path / "site"
        init_website(site_dir, template="academic")

        page_path = add_page("Research Notes", "<p>Notes here.</p>", site_dir)
        assert page_path.exists()
        assert "research-notes" in page_path.name
        content = page_path.read_text()
        assert "Research Notes" in content
        assert "<p>Notes here.</p>" in content

    def test_add_page_updates_config(self, tmp_path):
        site_dir = tmp_path / "site"
        init_website(site_dir, template="academic")
        add_page("Blog", "<p>Welcome</p>", site_dir)

        config = json.loads((site_dir / "site.json").read_text())
        assert "blog.html" in config["pages"]


# ---------------------------------------------------------------------------
# website: build_site
# ---------------------------------------------------------------------------


class TestWebsiteBuild:
    """build_site copies source files into _build directory."""

    def test_build_creates_build_dir(self, tmp_path):
        site_dir = tmp_path / "site"
        init_website(site_dir, template="minimal")

        result = build_site(site_dir)
        assert result is True

        build_dir = site_dir / "_build"
        assert build_dir.exists()
        assert (build_dir / "index.html").exists()
        assert (build_dir / "css" / "style.css").exists()

    def test_build_excludes_hidden_and_underscore(self, tmp_path):
        site_dir = tmp_path / "site"
        init_website(site_dir, template="minimal")
        (site_dir / ".hidden").write_text("secret")
        (site_dir / "_internal").mkdir()
        (site_dir / "_internal" / "notes.txt").write_text("internal")

        build_site(site_dir)
        build_dir = site_dir / "_build"
        assert not (build_dir / ".hidden").exists()
        assert not (build_dir / "_internal").exists()


# ---------------------------------------------------------------------------
# website: deploy_site
# ---------------------------------------------------------------------------


class TestWebsiteDeploy:
    """deploy_site returns deployment info for supported methods."""

    def test_deploy_github_pages(self, tmp_path):
        site_dir = tmp_path / "site"
        init_website(site_dir, template="minimal")
        build_site(site_dir)

        result = deploy_site(site_dir, method="github-pages")
        assert result["status"] == "ready"
        assert result["method"] == "github-pages"
        assert (site_dir / "_build" / ".nojekyll").exists()

    def test_deploy_unsupported_method(self, tmp_path):
        site_dir = tmp_path / "site"
        init_website(site_dir, template="minimal")
        build_site(site_dir)

        result = deploy_site(site_dir, method="ftp-upload")
        assert result["status"] == "error"

    def test_deploy_auto_builds_if_needed(self, tmp_path):
        site_dir = tmp_path / "site"
        init_website(site_dir, template="minimal")
        # Do NOT call build_site -- deploy should trigger it
        result = deploy_site(site_dir, method="netlify")
        assert result["status"] == "ready"
        assert (site_dir / "_build").exists()


# ---------------------------------------------------------------------------
# website: add_publication
# ---------------------------------------------------------------------------


class TestWebsiteAddPublication:
    """add_publication parses BibTeX and updates publications.html."""

    def test_add_publication_with_bibtex(self, tmp_path):
        site_dir = tmp_path / "site"
        init_website(site_dir, template="academic")

        bib = (
            "@article{Doe2023,\n"
            "  author = {Jane Doe},\n"
            "  title = {Deep Learning for Science},\n"
            "  year = {2023},\n"
            "  journal = {Nature ML},\n"
            "}"
        )
        result = add_publication(bib, site_dir)
        assert result is True

        pub_html = (site_dir / "publications.html").read_text()
        assert "Deep Learning for Science" in pub_html
        assert "Jane Doe" in pub_html
        assert "2023" in pub_html

    def test_add_publication_no_pub_page(self, tmp_path):
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        # No publications.html
        result = add_publication("@article{X, title={T}}", site_dir)
        assert result is False


# ---------------------------------------------------------------------------
# website: site_manager adapter
# ---------------------------------------------------------------------------


class TestSiteManagerAdapter:
    """_SiteManager wraps module-level functions correctly."""

    def test_site_manager_init_and_build(self, tmp_path):
        from core.website import _SiteManager

        mgr = _SiteManager(project_path=tmp_path)
        mgr.init(template="minimal")
        assert (tmp_path / "index.html").exists()

        assert mgr.build() is True
        assert (tmp_path / "_build").exists()

    def test_site_manager_deploy(self, tmp_path):
        from core.website import _SiteManager

        mgr = _SiteManager(project_path=tmp_path)
        mgr.init(template="minimal")
        result = mgr.deploy(method="manual")
        assert result["status"] == "ready"
        assert result["method"] == "manual"


# ---------------------------------------------------------------------------
# social_media: draft_medium_post
# ---------------------------------------------------------------------------


class TestDraftMediumPost:
    """draft_medium_post builds a Medium article dict."""

    def test_basic_draft(self):
        result = draft_medium_post(
            title="My Research",
            content="We present a novel approach.",
            tags=["AI", "ML", "NLP", "Science", "Research", "Extra"],
        )
        assert result["title"] == "My Research"
        assert "# My Research" in result["markdown"]
        # Medium allows max 5 tags
        assert len(result["tags"]) == 5
        assert "Extra" not in result["tags"]
        assert result["draft"].platform == "medium"
        assert result["draft"].ready is True


# ---------------------------------------------------------------------------
# social_media: draft_linkedin_post
# ---------------------------------------------------------------------------


class TestDraftLinkedinPost:
    """draft_linkedin_post handles content + link + truncation."""

    def test_basic_linkedin_post(self):
        result = draft_linkedin_post("Check out our new paper!", link="https://example.com")
        assert "https://example.com" in result["text"]
        assert result["draft"].platform == "linkedin"
        assert result["draft"].ready is True

    def test_truncation_at_3000_chars(self):
        long_content = "A" * 3500
        result = draft_linkedin_post(long_content)
        assert len(result["text"]) <= 3000
        assert result["text"].endswith("...")


# ---------------------------------------------------------------------------
# social_media: summarize_for_social
# ---------------------------------------------------------------------------


class TestSummarizeForSocial:
    """summarize_for_social extracts sentences within platform char limits."""

    def test_twitter_length(self):
        text = (
            "We introduce a novel method for protein folding. "
            "Our approach achieves state-of-the-art results. "
            "The model was trained on a large dataset."
        )
        summary = summarize_for_social(text, "twitter")
        assert len(summary) <= 280
        assert len(summary) > 0

    def test_linkedin_allows_more(self):
        text = "Short sentence. " * 50
        summary = summarize_for_social(text, "linkedin")
        assert len(summary) <= 3000


# ---------------------------------------------------------------------------
# social_media: generate_thread
# ---------------------------------------------------------------------------


class TestGenerateThread:
    """generate_thread splits long text into tweet-sized chunks."""

    def test_short_text_single_tweet(self):
        tweets = generate_thread("Hello world!")
        assert len(tweets) == 1
        assert tweets[0] == "Hello world!"

    def test_long_text_multiple_tweets(self):
        text = " ".join(["word"] * 200)
        tweets = generate_thread(text, max_chars=100)
        assert len(tweets) > 1
        for tweet in tweets:
            assert len(tweet) <= 100


# ---------------------------------------------------------------------------
# social_media: validate_post
# ---------------------------------------------------------------------------


class TestValidatePost:
    """validate_post returns error strings for invalid drafts."""

    def test_valid_medium_post(self):
        draft = PostDraft(platform="medium", body="Hello", title="Title", ready=True)
        errors = validate_post(draft)
        assert errors == []

    def test_medium_missing_title(self):
        draft = PostDraft(platform="medium", body="Hello", title="")
        errors = validate_post(draft)
        assert any("title" in e.lower() for e in errors)

    def test_empty_body(self):
        draft = PostDraft(platform="twitter", body="", title="")
        errors = validate_post(draft)
        assert any("empty" in e.lower() for e in errors)

    def test_over_char_limit(self):
        draft = PostDraft(platform="twitter", body="X" * 300)
        errors = validate_post(draft)
        assert any("limit" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# social_media: publish_to_platform dispatch
# ---------------------------------------------------------------------------


class TestPublishToPlatformDispatch:
    """publish_to_platform dispatches to the correct publisher or errors."""

    def test_unsupported_platform(self):
        result = publish_to_platform("tiktok", body="test content", api_token="fake")
        assert result["success"] is False
        assert "Unsupported" in result["error"]

    def test_empty_body_rejected(self):
        """publish_to_platform rejects empty body."""
        result = publish_to_platform("medium", api_token="fake")
        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_medium_dispatch_without_network(self):
        """Calling publish_to_platform('medium') without a real token fails gracefully."""
        with patch("core.social_media.publish_medium") as mock_pub:
            mock_pub.return_value = {"success": False, "error": "no token"}
            result = publish_to_platform("medium", title="Test", body="Content", api_token="")
        assert result["success"] is False

    def test_linkedin_dispatch_without_network(self):
        with patch("core.social_media.publish_linkedin") as mock_pub:
            mock_pub.return_value = {"success": False, "error": "no token"}
            result = publish_to_platform("linkedin", body="Content", api_token="")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# notifications: config loading
# ---------------------------------------------------------------------------


class TestNotificationConfig:
    """NotificationConfig loads from JSON and provides sensible defaults."""

    def test_default_config(self):
        config = NotificationConfig()
        assert config.slack_webhook == ""
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.desktop_enabled is True
        assert config.throttle_seconds > 0

    def test_load_from_file(self, tmp_path):
        cfg_path = tmp_path / "notif.json"
        cfg_path.write_text(json.dumps({
            "slack_webhook": "https://hooks.slack.com/test",
            "email_to": "user@example.com",
            "desktop_enabled": False,
        }))
        config = NotificationConfig.load(cfg_path)
        assert config.slack_webhook == "https://hooks.slack.com/test"
        assert config.email_to == "user@example.com"
        assert config.desktop_enabled is False
        # Fields not in file keep defaults
        assert config.smtp_host == "smtp.gmail.com"

    def test_load_missing_file_returns_defaults(self, tmp_path):
        config = NotificationConfig.load(tmp_path / "nonexistent.json")
        assert config.slack_webhook == ""
        assert config.desktop_enabled is True

    def test_save_and_reload(self, tmp_path):
        cfg_path = tmp_path / "notif.json"
        original = NotificationConfig(
            slack_webhook="https://hooks.slack.com/xxx",
            email_to="me@test.com",
            throttle_seconds=600,
        )
        original.save(cfg_path)
        loaded = NotificationConfig.load(cfg_path)
        assert loaded.slack_webhook == original.slack_webhook
        assert loaded.email_to == original.email_to
        assert loaded.throttle_seconds == 600
