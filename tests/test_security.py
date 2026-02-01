"""Tests for security utilities."""

from pathlib import Path

from core.security import protect_immutable_files, scan_for_secrets


def test_scan_for_secrets_finds_api_key(tmp_path: Path):
    f = tmp_path / "config.py"
    f.write_text('API_KEY = "sk-abc123456789012345678901"\n')
    findings = scan_for_secrets(f)
    assert len(findings) >= 1
    assert findings[0]["file"] == str(f)


def test_scan_for_secrets_finds_github_pat(tmp_path: Path):
    f = tmp_path / "env.txt"
    f.write_text("GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890\n")
    findings = scan_for_secrets(f)
    assert len(findings) >= 1


def test_scan_for_secrets_clean_file(tmp_path: Path):
    f = tmp_path / "clean.py"
    f.write_text('x = 42\nname = "hello"\n')
    findings = scan_for_secrets(f)
    assert len(findings) == 0


def test_scan_for_secrets_directory(tmp_path: Path):
    (tmp_path / "ok.py").write_text("x = 1\n")
    (tmp_path / "bad.py").write_text('secret = "mysupersecretpassword123"\n')
    findings = scan_for_secrets(tmp_path)
    assert len(findings) >= 1


def test_scan_for_secrets_private_key(tmp_path: Path):
    f = tmp_path / "key.pem"
    f.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----\n"
    )
    findings = scan_for_secrets(f)
    assert len(findings) >= 1


def test_protect_immutable_default():
    files = [Path(".env"), Path("src/main.py"), Path("secrets/key.pem")]
    blocked = protect_immutable_files(files)
    assert Path(".env") in blocked
    assert Path("src/main.py") not in blocked


def test_protect_immutable_custom():
    files = [Path("data/raw.csv"), Path("src/main.py")]
    blocked = protect_immutable_files(files, immutable=["data/*"])
    assert Path("data/raw.csv") in blocked
    assert Path("src/main.py") not in blocked


def test_protect_immutable_no_matches():
    files = [Path("src/main.py"), Path("tests/test_foo.py")]
    blocked = protect_immutable_files(files)
    assert len(blocked) == 0


# --- Bridge-integrated tests ---

from unittest.mock import MagicMock, patch


def test_scan_merges_bridge_findings(tmp_path: Path):
    f = tmp_path / "clean.py"
    f.write_text("x = 42\n")
    mock_bridge = MagicMock()
    mock_bridge.scan_security.return_value = {
        "findings": [{"file": str(f), "line": 1, "pattern": "custom-pattern"}]
    }
    with patch("core.security._get_bridge", return_value=mock_bridge):
        findings = scan_for_secrets(f)
        assert len(findings) == 1
        assert findings[0]["pattern"] == "custom-pattern"


def test_scan_deduplicates_bridge_findings(tmp_path: Path):
    f = tmp_path / "config.py"
    f.write_text('API_KEY = "sk-abc123456789012345678901"\n')
    mock_bridge = MagicMock()
    # Bridge returns same finding as local scan
    mock_bridge.scan_security.return_value = {
        "findings": [{"file": str(f), "line": 1, "pattern": "duplicate"}]
    }
    with patch("core.security._get_bridge", return_value=mock_bridge):
        findings = scan_for_secrets(f)
        # Should have exactly 1 (deduped), not 2
        assert len(findings) == 1


def test_scan_bridge_unavailable(tmp_path: Path):
    f = tmp_path / "clean.py"
    f.write_text("x = 42\n")
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.security._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        findings = scan_for_secrets(f)
        assert len(findings) == 0
