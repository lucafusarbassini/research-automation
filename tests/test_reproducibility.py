"""Tests for reproducibility enforcement."""

from pathlib import Path

from core.reproducibility import (
    ArtifactRegistry,
    RunLog,
    compute_dataset_hash,
    list_runs,
    load_run,
    log_run,
)


def test_run_log_roundtrip():
    run = RunLog(run_id="test-001", command="python train.py", parameters={"lr": 0.01})
    d = run.to_dict()
    restored = RunLog.from_dict(d)
    assert restored.run_id == "test-001"
    assert restored.parameters["lr"] == 0.01


def test_log_and_load_run(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.reproducibility.RUNS_DIR", tmp_path / "runs")
    run = RunLog(run_id="run-42", command="train", status="success")
    log_run(run)
    loaded = load_run("run-42")
    assert loaded is not None
    assert loaded.command == "train"


def test_load_run_not_found(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.reproducibility.RUNS_DIR", tmp_path / "runs")
    assert load_run("nonexistent") is None


def test_list_runs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.reproducibility.RUNS_DIR", tmp_path / "runs")
    log_run(RunLog(run_id="run-1", command="a"))
    log_run(RunLog(run_id="run-2", command="b"))
    runs = list_runs()
    assert len(runs) == 2


def test_artifact_registry(tmp_path: Path):
    registry = ArtifactRegistry(registry_path=tmp_path / "registry.json")
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"fake model data")

    checksum = registry.register("model-v1", artifact, run_id="run-1")
    assert len(checksum) == 64  # SHA-256 hex

    assert registry.verify("model-v1") is True
    assert registry.verify("nonexistent") is False

    entry = registry.get("model-v1")
    assert entry is not None
    assert entry["run_id"] == "run-1"


def test_artifact_registry_tampered(tmp_path: Path):
    registry = ArtifactRegistry(registry_path=tmp_path / "registry.json")
    artifact = tmp_path / "data.csv"
    artifact.write_text("col1,col2\n1,2\n")

    registry.register("dataset", artifact)
    # Tamper with file
    artifact.write_text("col1,col2\n1,999\n")
    assert registry.verify("dataset") is False


def test_artifact_list(tmp_path: Path):
    registry = ArtifactRegistry(registry_path=tmp_path / "registry.json")
    f1 = tmp_path / "a.txt"
    f1.write_text("aaa")
    f2 = tmp_path / "b.txt"
    f2.write_text("bbb")
    registry.register("a", f1)
    registry.register("b", f2)
    assert len(registry.list_artifacts()) == 2


def test_compute_dataset_hash_file(tmp_path: Path):
    f = tmp_path / "data.csv"
    f.write_text("header\nrow1\nrow2\n")
    h1 = compute_dataset_hash(f)
    assert len(h1) == 64
    # Same content -> same hash
    h2 = compute_dataset_hash(f)
    assert h1 == h2


def test_compute_dataset_hash_directory(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("world")
    h = compute_dataset_hash(tmp_path)
    assert len(h) == 64


def test_compute_dataset_hash_sample(tmp_path: Path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"x" * 10000)
    h_full = compute_dataset_hash(f)
    h_sample = compute_dataset_hash(f, sample_size=100)
    assert h_full != h_sample  # Different because sample reads less
