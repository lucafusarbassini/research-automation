"""Social media posting module: draft, validate, and publish to Medium, LinkedIn, and Twitter/X."""

import json
import logging
from dataclasses import dataclass, field
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Platform character limits
CHAR_LIMITS = {
    "twitter": 280,
    "linkedin": 3000,
    "medium": 100_000,  # effectively unlimited
}

MEDIUM_MAX_TAGS = 5


@dataclass
class PostDraft:
    """A social media post draft ready for validation and publishing."""

    platform: str
    body: str
    title: str = ""
    tags: list[str] = field(default_factory=list)
    link: str = ""
    char_count: int = 0
    ready: bool = False

    def __post_init__(self) -> None:
        if self.char_count == 0:
            self.char_count = len(self.body)


# ---------------------------------------------------------------------------
# Drafting helpers
# ---------------------------------------------------------------------------

def draft_medium_post(title: str, content: str, tags: list[str]) -> dict:
    """Prepare a Medium article draft in markdown format.

    Medium allows at most 5 tags per post. Excess tags are trimmed.
    """
    trimmed_tags = tags[:MEDIUM_MAX_TAGS]
    markdown = f"# {title}\n\n{content}"
    draft = PostDraft(
        platform="medium",
        title=title,
        body=content,
        tags=trimmed_tags,
        ready=True,
    )
    return {
        "title": title,
        "markdown": markdown,
        "tags": trimmed_tags,
        "draft": draft,
    }


def draft_linkedin_post(content: str, link: str = "") -> dict:
    """Prepare a LinkedIn post with character-limit awareness (3000 chars).

    If a link is provided it is appended on its own line.  If the combined
    text exceeds 3000 characters the body is truncated with an ellipsis.
    """
    text = content
    if link:
        text = f"{content}\n\n{link}"

    limit = CHAR_LIMITS["linkedin"]
    if len(text) > limit:
        text = text[: limit - 3] + "..."

    draft = PostDraft(
        platform="linkedin",
        body=text,
        link=link,
        char_count=len(text),
        ready=True,
    )
    return {"text": text, "draft": draft}


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------

def summarize_for_social(paper_content: str, platform: str) -> str:
    """Auto-summarize research content for a given platform.

    This is a heuristic extractive summariser: it picks the first N
    sentences that fit within the platform's character limit.
    """
    limit = CHAR_LIMITS.get(platform, 280)
    sentences = _split_sentences(paper_content)

    summary_parts: list[str] = []
    current_length = 0
    for sentence in sentences:
        addition = sentence if not summary_parts else " " + sentence
        if current_length + len(addition) > limit:
            break
        summary_parts.append(addition)
        current_length += len(addition)

    summary = "".join(summary_parts)
    if not summary and sentences:
        # If even the first sentence is too long, truncate it.
        summary = sentences[0][: limit - 3] + "..."
    return summary


def _split_sentences(text: str) -> list[str]:
    """Naively split text into sentences on period-space boundaries."""
    parts: list[str] = []
    current = ""
    for char in text:
        current += char
        if char == "." and current.rstrip().endswith("."):
            stripped = current.strip()
            if stripped:
                parts.append(stripped)
            current = ""
    remaining = current.strip()
    if remaining:
        parts.append(remaining)
    return parts


# ---------------------------------------------------------------------------
# Thread generation
# ---------------------------------------------------------------------------

def generate_thread(content: str, max_chars: int = 280) -> list[str]:
    """Break content into a Twitter/X-style thread.

    Splits on word boundaries so no tweet exceeds *max_chars*.
    """
    if len(content) <= max_chars:
        return [content]

    words = content.split()
    tweets: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) > max_chars:
            if current:
                tweets.append(current)
            # If a single word exceeds max_chars, hard-wrap it.
            while len(word) > max_chars:
                tweets.append(word[:max_chars])
                word = word[max_chars:]
            current = word
        else:
            current = candidate
    if current:
        tweets.append(current)
    return tweets


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_post(draft: PostDraft) -> list[str]:
    """Validate a PostDraft and return a list of error strings (empty = valid)."""
    errors: list[str] = []

    # Platform-specific required fields
    if draft.platform == "medium" and not draft.title:
        errors.append("Medium posts require a title.")

    # Character-limit checks
    limit = CHAR_LIMITS.get(draft.platform)
    if limit and draft.char_count > limit:
        errors.append(
            f"Body exceeds {draft.platform} character limit "
            f"({draft.char_count}/{limit})."
        )

    if not draft.body:
        errors.append("Post body cannot be empty.")

    return errors


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def publish_medium(draft: PostDraft, api_token: str) -> dict:
    """Publish a draft to the Medium API.

    Uses the Medium REST API v1.  Requires a valid integration token.
    """
    try:
        # Step 1: get authenticated user id
        me_req = Request(
            "https://api.medium.com/v1/me",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(me_req) as resp:
            user_data = json.loads(resp.read())
            user_id = user_data["data"]["id"]

        # Step 2: create post
        payload = json.dumps({
            "title": draft.title,
            "contentFormat": "markdown",
            "content": f"# {draft.title}\n\n{draft.body}",
            "tags": draft.tags,
            "publishStatus": "draft",
        }).encode()

        post_req = Request(
            f"https://api.medium.com/v1/users/{user_id}/posts",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(post_req) as resp:
            result = json.loads(resp.read())

        return {
            "success": True,
            "id": result["data"]["id"],
            "url": result["data"].get("url", ""),
        }
    except Exception as exc:
        logger.error("Failed to publish to Medium: %s", exc)
        return {"success": False, "error": str(exc)}


def publish_linkedin(draft: PostDraft, api_token: str) -> dict:
    """Publish a draft to the LinkedIn API (UGC Posts).

    Requires a valid OAuth2 access token with ``w_member_social`` scope.
    """
    try:
        payload = json.dumps({
            "author": "urn:li:person:me",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": draft.body},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }).encode()

        req = Request(
            "https://api.linkedin.com/v2/ugcPosts",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            method="POST",
        )
        with urlopen(req) as resp:
            result = json.loads(resp.read())

        return {"success": True, "id": result.get("id", "")}
    except Exception as exc:
        logger.error("Failed to publish to LinkedIn: %s", exc)
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# CLI adapter — ``from core.social_media import publish_to_platform``
# ---------------------------------------------------------------------------


def publish_to_platform(
    platform: str,
    *,
    title: str = "",
    body: str = "",
    tags: list[str] | None = None,
    link: str = "",
    api_token: str = "",
) -> dict:
    """Dispatch publishing to the appropriate platform function.

    Args:
        platform: One of ``"medium"``, ``"linkedin"``.
        title: Post title (required for Medium).
        body: Post body content.
        tags: Optional tags (Medium only, max 5).
        link: Optional link to append (LinkedIn).
        api_token: API token for authentication.

    Returns:
        Dict with ``success`` bool and ``url``/``error`` keys.
    """
    platform_lower = platform.lower()

    if not body:
        return {"success": False, "error": "Post body cannot be empty. Provide body text."}

    if platform_lower == "medium":
        if not title:
            return {"success": False, "error": "Medium posts require a title."}
        draft = PostDraft(
            platform="medium",
            title=title,
            body=body,
            tags=(tags or [])[:MEDIUM_MAX_TAGS],
            ready=True,
        )
        return publish_medium(draft, api_token)
    elif platform_lower == "linkedin":
        draft = PostDraft(
            platform="linkedin",
            body=body,
            link=link,
            ready=True,
        )
        return publish_linkedin(draft, api_token)
    else:
        return {"success": False, "error": f"Unsupported platform: {platform}"}
