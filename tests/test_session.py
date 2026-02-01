"""Tests for session management."""

from pathlib import Path

from core.session import (
    Session,
    close_session,
    create_session,
    list_sessions,
    load_session,
    snapshot_state,
)


def test_create_session(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    session = create_session("test-session")
    assert session.name == "test-session"
    assert session.status == "active"
    assert (tmp_path / "sessions" / "test-session.json").exists()


def test_load_session(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    create_session("my-session")
    loaded = load_session("my-session")
    assert loaded is not None
    assert loaded.name == "my-session"


def test_load_session_not_found(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    assert load_session("nonexistent") is None


def test_list_sessions(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    create_session("session-1")
    create_session("session-2")
    sessions = list_sessions()
    assert len(sessions) == 2


def test_close_session(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    session = create_session("closing-test")
    close_session(session)
    loaded = load_session("closing-test")
    assert loaded.status == "completed"


def test_snapshot_state(tmp_path: Path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "TODO.md").write_text("# TODO\n- [ ] test")
    (state_dir / "PROGRESS.md").write_text("# Progress\n")
    monkeypatch.setattr("core.session.STATE_DIR", state_dir)

    snapshot_path = snapshot_state("test-snap")
    assert snapshot_path.exists()
    assert (snapshot_path / "TODO.md").exists()


def test_session_to_dict():
    session = Session(name="test", status="active")
    d = session.to_dict()
    assert d["name"] == "test"
    assert d["status"] == "active"
    assert "started" in d


# --- Bridge-integrated tests ---

from unittest.mock import MagicMock, patch


def test_create_session_with_bridge(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    mock_bridge = MagicMock()
    mock_bridge.start_session.return_value = {"session_id": "cf-123"}
    with patch("core.session._get_bridge", return_value=mock_bridge):
        session = create_session("bridge-test")
        assert session.name == "bridge-test"
        mock_bridge.start_session.assert_called_once_with("bridge-test")


def test_close_session_with_bridge(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    session = create_session("close-bridge")
    mock_bridge = MagicMock()
    mock_bridge.end_session.return_value = {"summary": {}}
    with patch("core.session._get_bridge", return_value=mock_bridge):
        close_session(session)
        mock_bridge.end_session.assert_called_once_with("close-bridge")
        assert session.status == "completed"


def test_create_session_bridge_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.session._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        session = create_session("fallback-test")
        assert session.name == "fallback-test"
        assert (tmp_path / "sessions" / "fallback-test.json").exists()


def test_close_session_bridge_unavailable(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
    session = create_session("close-fallback")
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.session._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        close_session(session)
        assert session.status == "completed"
        # Verify local JSON was still written
        loaded = load_session("close-fallback")
        assert loaded.status == "completed"
