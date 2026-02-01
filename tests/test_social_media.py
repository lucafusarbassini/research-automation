"""Tests for social media posting module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.social_media import (
    PostDraft,
    draft_linkedin_post,
    draft_medium_post,
    generate_thread,
    publish_linkedin,
    publish_medium,
    summarize_for_social,
    validate_post,
)

# ---------------------------------------------------------------------------
# PostDraft dataclass
# ---------------------------------------------------------------------------


def test_post_draft_defaults():
    draft = PostDraft(platform="medium", body="Hello world")
    assert draft.platform == "medium"
    assert draft.title == ""
    assert draft.body == "Hello world"
    assert draft.tags == []
    assert draft.link == ""
    assert draft.char_count == len("Hello world")
    assert draft.ready is False


def test_post_draft_char_count_auto():
    draft = PostDraft(platform="twitter", body="abc")
    assert draft.char_count == 3


# ---------------------------------------------------------------------------
# draft_medium_post
# ---------------------------------------------------------------------------


def test_draft_medium_post_basic():
    result = draft_medium_post("My Title", "Some **bold** content.", ["ai", "ml"])
    assert result["title"] == "My Title"
    assert "# My Title" in result["markdown"]
    assert "Some **bold** content." in result["markdown"]
    assert result["tags"] == ["ai", "ml"]
    assert isinstance(result["draft"], PostDraft)
    assert result["draft"].platform == "medium"
    assert result["draft"].ready is True


def test_draft_medium_post_limits_tags_to_five():
    tags = ["a", "b", "c", "d", "e", "f"]
    result = draft_medium_post("T", "Body", tags)
    assert len(result["tags"]) == 5


# ---------------------------------------------------------------------------
# draft_linkedin_post
# ---------------------------------------------------------------------------


def test_draft_linkedin_post_basic():
    result = draft_linkedin_post("Check out my new paper!")
    assert result["text"] == "Check out my new paper!"
    assert result["draft"].platform == "linkedin"
    assert result["draft"].char_count <= 3000
    assert result["draft"].ready is True


def test_draft_linkedin_post_with_link():
    result = draft_linkedin_post("Read this", link="https://example.com")
    assert "https://example.com" in result["text"]


def test_draft_linkedin_post_truncates_over_limit():
    long_content = "x" * 3500
    result = draft_linkedin_post(long_content)
    assert result["draft"].char_count <= 3000
    assert result["text"].endswith("...")


# ---------------------------------------------------------------------------
# summarize_for_social
# ---------------------------------------------------------------------------


def test_summarize_for_social_twitter():
    paper = "We present a novel method for training large language models. " * 20
    summary = summarize_for_social(paper, "twitter")
    assert len(summary) <= 280


def test_summarize_for_social_linkedin():
    paper = "We present a novel method for training large language models. " * 20
    summary = summarize_for_social(paper, "linkedin")
    assert len(summary) <= 3000


def test_summarize_for_social_medium():
    paper = "We present a novel method. " * 50
    summary = summarize_for_social(paper, "medium")
    # Medium summaries can be longer; just confirm it's non-empty and shorter than original
    assert len(summary) > 0
    assert len(summary) <= len(paper)


# ---------------------------------------------------------------------------
# generate_thread
# ---------------------------------------------------------------------------


def test_generate_thread_short_content():
    thread = generate_thread("Hello world")
    assert len(thread) == 1
    assert thread[0] == "Hello world"


def test_generate_thread_splits_long_content():
    content = "Word " * 200  # well over 280 chars
    thread = generate_thread(content, max_chars=280)
    assert len(thread) > 1
    for tweet in thread:
        assert len(tweet) <= 280


def test_generate_thread_custom_max_chars():
    content = "Hello world this is a test of the thread generation system"
    thread = generate_thread(content, max_chars=20)
    assert len(thread) > 1
    for tweet in thread:
        assert len(tweet) <= 20


# ---------------------------------------------------------------------------
# validate_post
# ---------------------------------------------------------------------------


def test_validate_post_valid_medium():
    draft = PostDraft(platform="medium", title="Title", body="Content", tags=["ai"])
    errors = validate_post(draft)
    assert errors == []


def test_validate_post_missing_title_medium():
    draft = PostDraft(platform="medium", body="Content")
    errors = validate_post(draft)
    assert any("title" in e.lower() for e in errors)


def test_validate_post_linkedin_over_limit():
    draft = PostDraft(platform="linkedin", body="x" * 3001)
    errors = validate_post(draft)
    assert any("3000" in e or "character" in e.lower() for e in errors)


def test_validate_post_twitter_over_limit():
    draft = PostDraft(platform="twitter", body="x" * 281)
    errors = validate_post(draft)
    assert any("280" in e or "character" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# publish_medium (mocked)
# ---------------------------------------------------------------------------


@patch("core.social_media.urlopen")
def test_publish_medium_success(mock_urlopen):
    # First call: GET /v1/me returns user info
    me_response = MagicMock()
    me_response.read.return_value = json.dumps({"data": {"id": "user-42"}}).encode()
    me_response.__enter__ = lambda s: s
    me_response.__exit__ = MagicMock(return_value=False)

    # Second call: POST /v1/users/{id}/posts returns post info
    post_response = MagicMock()
    post_response.read.return_value = json.dumps(
        {"data": {"id": "abc123", "url": "https://medium.com/@user/post-abc123"}}
    ).encode()
    post_response.__enter__ = lambda s: s
    post_response.__exit__ = MagicMock(return_value=False)

    mock_urlopen.side_effect = [me_response, post_response]

    draft = PostDraft(platform="medium", title="Title", body="Body", tags=["ai"])
    result = publish_medium(draft, api_token="fake-token")
    assert result["success"] is True
    assert result["id"] == "abc123"
    assert mock_urlopen.call_count == 2


@patch("core.social_media.urlopen")
def test_publish_medium_failure(mock_urlopen):
    mock_urlopen.side_effect = Exception("Network error")

    draft = PostDraft(platform="medium", title="Title", body="Body")
    result = publish_medium(draft, api_token="fake-token")
    assert result["success"] is False
    assert "error" in result


# ---------------------------------------------------------------------------
# publish_linkedin (mocked)
# ---------------------------------------------------------------------------


@patch("core.social_media.urlopen")
def test_publish_linkedin_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"id": "urn:li:share:123"}).encode()
    mock_response.status = 201
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_response

    draft = PostDraft(platform="linkedin", body="My post content")
    result = publish_linkedin(draft, api_token="fake-token")
    assert result["success"] is True
    assert "id" in result
    mock_urlopen.assert_called_once()


@patch("core.social_media.urlopen")
def test_publish_linkedin_failure(mock_urlopen):
    mock_urlopen.side_effect = Exception("Auth failed")

    draft = PostDraft(platform="linkedin", body="Content")
    result = publish_linkedin(draft, api_token="fake-token")
    assert result["success"] is False
    assert "error" in result
