"""Zenodo publishing: deposit software, datasets, and papers with a permanent DOI.

Uses the Zenodo REST API v3. Requires a Zenodo personal access token:
    https://zenodo.org/account/settings/applications/tokens/new/
    Required scopes: deposit:write, deposit:actions

Set in .env:
    ZENODO_TOKEN=your-zenodo-token

Usage:
    from core.zenodo import create_deposition, upload_file, publish_deposition
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ZENODO_API = "https://zenodo.org/api"
_SANDBOX_API = "https://sandbox.zenodo.org/api"  # for testing


def _get_token(sandbox: bool = False) -> str:
    """Load Zenodo token from environment / .env."""
    try:
        from dotenv import load_dotenv
        for candidate in [Path.cwd() / ".env", Path(__file__).parent.parent / ".env"]:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                break
    except ImportError:
        pass

    key = "ZENODO_SANDBOX_TOKEN" if sandbox else "ZENODO_TOKEN"
    token = os.getenv(key, "").strip()
    if not token:
        raise RuntimeError(
            f"{key} not set. Get one at:\n"
            "  https://zenodo.org/account/settings/applications/tokens/new/\n"
            "  Required scopes: deposit:write, deposit:actions\n"
            "  Then add to .env: ZENODO_TOKEN=your-token"
        )
    return token


def _api(sandbox: bool = False) -> str:
    return _SANDBOX_API if sandbox else _ZENODO_API


def _request(
    method: str,
    url: str,
    *,
    token: str,
    json_body: dict | None = None,
    data: bytes | None = None,
    content_type: str = "application/json",
) -> dict:
    """Make a Zenodo API request and return the parsed JSON response."""
    import urllib.request

    body = json.dumps(json_body).encode() if json_body is not None else data
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    resp = urllib.request.urlopen(req, timeout=60)
    raw = resp.read()
    return json.loads(raw) if raw else {}


def create_deposition(
    *,
    title: str,
    description: str,
    creators: list[dict],
    upload_type: str = "software",
    keywords: list[str] | None = None,
    related_identifiers: list[dict] | None = None,
    sandbox: bool = False,
) -> dict:
    """Create a new Zenodo deposition (draft).

    Args:
        title: Record title.
        description: HTML/plain description of the deposit.
        creators: List of ``{"name": "Last, First", "affiliation": "Inst"}`` dicts.
        upload_type: One of: software, dataset, publication, poster, presentation,
                     image, video, lesson, physicalobject, other.
        keywords: List of keyword strings.
        related_identifiers: e.g. [{"identifier": "https://github.com/...",
                                     "relation": "isSupplementTo",
                                     "scheme": "url"}]
        sandbox: Use sandbox.zenodo.org for testing.

    Returns:
        Deposition dict with ``id``, ``links.bucket``, ``links.publish``.

    Example::

        dep = create_deposition(
            title="My Research Tool v1.0",
            description="Automates ...",
            creators=[{"name": "Fusar Bassini, Luca", "affiliation": "EPFL"}],
            upload_type="software",
        )
        print(dep["id"], dep["links"]["html"])
    """
    token = _get_token(sandbox)
    metadata: dict[str, Any] = {
        "title": title,
        "description": description,
        "creators": creators,
        "upload_type": upload_type,
    }
    if keywords:
        metadata["keywords"] = keywords
    if related_identifiers:
        metadata["related_identifiers"] = related_identifiers

    url = f"{_api(sandbox)}/deposit/depositions"
    result = _request("POST", url, token=token, json_body={"metadata": metadata})
    logger.info("Created Zenodo deposition %s", result.get("id"))
    return result


def upload_file(
    deposition_id: int | str,
    file_path: str | Path,
    *,
    sandbox: bool = False,
) -> dict:
    """Upload a file to a Zenodo deposition.

    Args:
        deposition_id: The deposition ID from ``create_deposition()``.
        file_path: Local path to the file to upload.
        sandbox: Use sandbox.zenodo.org.

    Returns:
        File metadata dict with ``id``, ``filename``, ``checksum``.
    """
    token = _get_token(sandbox)
    file_path = Path(file_path)
    file_bytes = file_path.read_bytes()

    # Get the bucket URL
    dep_url = f"{_api(sandbox)}/deposit/depositions/{deposition_id}"
    dep = _request("GET", dep_url, token=token)
    bucket_url = dep["links"]["bucket"]

    # PUT file into bucket
    put_url = f"{bucket_url}/{file_path.name}"
    result = _request(
        "PUT", put_url, token=token, data=file_bytes, content_type="application/octet-stream"
    )
    logger.info("Uploaded %s to deposition %s", file_path.name, deposition_id)
    return result


def update_metadata(
    deposition_id: int | str,
    metadata: dict,
    *,
    sandbox: bool = False,
) -> dict:
    """Update metadata on a draft deposition."""
    token = _get_token(sandbox)
    url = f"{_api(sandbox)}/deposit/depositions/{deposition_id}"
    return _request("PUT", url, token=token, json_body={"metadata": metadata})


def publish_deposition(
    deposition_id: int | str,
    *,
    sandbox: bool = False,
) -> dict:
    """Publish a deposition and obtain a permanent DOI.

    Args:
        deposition_id: Draft deposition ID.
        sandbox: Use sandbox.zenodo.org.

    Returns:
        Published record dict containing ``doi``, ``doi_url``, ``links.record``.
    """
    token = _get_token(sandbox)
    url = f"{_api(sandbox)}/deposit/depositions/{deposition_id}/actions/publish"
    result = _request("POST", url, token=token)
    doi = result.get("doi", "")
    logger.info("Published Zenodo record %s — DOI: %s", deposition_id, doi)
    return result


def list_depositions(*, sandbox: bool = False) -> list[dict]:
    """List all depositions for this account."""
    token = _get_token(sandbox)
    url = f"{_api(sandbox)}/deposit/depositions"
    result = _request("GET", url, token=token)
    return result if isinstance(result, list) else []


def get_deposition(deposition_id: int | str, *, sandbox: bool = False) -> dict:
    """Fetch a deposition by ID."""
    token = _get_token(sandbox)
    url = f"{_api(sandbox)}/deposit/depositions/{deposition_id}"
    return _request("GET", url, token=token)


def deposit_from_project(
    project_path: str | Path = ".",
    *,
    files: list[str] | None = None,
    sandbox: bool = False,
    upload_type: str = "software",
) -> dict:
    """High-level helper: create a Zenodo deposition from a ricet project.

    Reads metadata from ``config/settings.yml`` and ``knowledge/GOAL.md``.
    Uploads the specified files (or auto-detects: paper PDF + source archive).

    Args:
        project_path: Root of the ricet project.
        files: Explicit list of file paths to deposit.
        sandbox: Test on sandbox.zenodo.org first.
        upload_type: "software" or "dataset" or "publication".

    Returns:
        Deposition dict (draft, not yet published).
    """
    project_path = Path(project_path).resolve()

    # Read project metadata
    import yaml

    settings_file = project_path / "config" / "settings.yml"
    settings = {}
    if settings_file.exists():
        settings = yaml.safe_load(settings_file.read_text()) or {}

    project_name = settings.get("project", {}).get("name", project_path.name)
    author_name = os.getenv("GIT_AUTHOR_NAME", "") or ""
    author_affiliation = settings.get("project", {}).get("affiliation", "")

    goal_file = project_path / "knowledge" / "GOAL.md"
    description = goal_file.read_text()[:2000] if goal_file.exists() else project_name

    # Auto-detect files if not specified
    if not files:
        candidates = []
        paper_pdf = project_path / "paper" / "main.pdf"
        if paper_pdf.exists():
            candidates.append(str(paper_pdf))
        # Check for source archive
        for archive in project_path.glob("dist/*.tar.gz"):
            candidates.append(str(archive))
        for archive in project_path.glob("dist/*.whl"):
            candidates.append(str(archive))
        files = candidates or [str(project_path / "paper" / "main.tex")]

    creators = [{"name": author_name or "Unknown"}]
    if author_affiliation:
        creators[0]["affiliation"] = author_affiliation

    dep = create_deposition(
        title=project_name,
        description=description,
        creators=creators,
        upload_type=upload_type,
        sandbox=sandbox,
    )

    dep_id = dep["id"]
    for f in files:
        fp = Path(f)
        if fp.exists():
            upload_file(dep_id, fp, sandbox=sandbox)
        else:
            logger.warning("File not found, skipping: %s", f)

    return dep
