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
