"""Tests for automation utilities."""

from pathlib import Path

from core.automation_utils import (
    DataHandler,
    ExperimentRunner,
    PlotGenerator,
    ReportGenerator,
    downsample_data,
    run_smoke_test,
)


def test_data_handler_detect_format():
    dh = DataHandler(path=Path("data.csv"))
    assert dh.detect_format() == "csv"


def test_data_handler_detect_parquet():
    dh = DataHandler(path=Path("data.parquet"))
    assert dh.detect_format() == "parquet"


def test_data_handler_detect_unknown():
    dh = DataHandler(path=Path("data.xyz"))
    assert dh.detect_format() == "unknown"


def test_data_handler_get_info(tmp_path: Path):
    f = tmp_path / "test.csv"
    f.write_text("a,b\n1,2\n3,4\n")
    dh = DataHandler(path=f)
    info = dh.get_info()
    assert info["format"] == "csv"
    assert info["size_mb"] >= 0


def test_data_handler_get_info_missing():
    dh = DataHandler(path=Path("nonexistent.csv"))
    info = dh.get_info()
    assert "error" in info


def test_downsample_data():
    data = list(range(100))
    sampled = downsample_data(data, fraction=0.1)
    assert len(sampled) == 10


def test_downsample_data_reproducible():
    data = list(range(100))
    s1 = downsample_data(data, fraction=0.2, seed=42)
    s2 = downsample_data(data, fraction=0.2, seed=42)
    assert s1 == s2


def test_downsample_data_small():
    data = [1, 2, 3]
    sampled = downsample_data(data, fraction=0.1)
    assert len(sampled) >= 1


def test_experiment_runner(tmp_path: Path):
    runner = ExperimentRunner(name="test-exp", log_dir=tmp_path)
    runner.log_params({"lr": 0.01, "epochs": 10})
    runner.log_metric("accuracy", 0.95)
    path = runner.save()
    assert path.exists()

    import json

    data = json.loads(path.read_text())
    assert data["parameters"]["lr"] == 0.01
    assert data["results"]["accuracy"] == 0.95


def test_plot_generator():
    pg = PlotGenerator()
    spec = pg.generate_spec("line", "loss over epochs", xlabel="Epoch", ylabel="Loss")
    assert spec["type"] == "line"
    assert spec["kwargs"]["xlabel"] == "Epoch"


def test_report_generator():
    rg = ReportGenerator(title="Test Report")
    rg.add_section("Introduction", "This is a test.")
    rg.add_section("Results", "Accuracy: 95%")
    md = rg.render_markdown()
    assert "# Test Report" in md
    assert "## Introduction" in md
    assert "95%" in md


def test_report_generator_save(tmp_path: Path):
    rg = ReportGenerator(title="Report")
    rg.add_section("Summary", "Done.")
    path = tmp_path / "report.md"
    rg.save(path)
    assert path.exists()
    assert "# Report" in path.read_text()


def test_run_smoke_test():
    result = run_smoke_test("echo hello")
    assert result["success"] is True
    assert "hello" in result["output"]


def test_run_smoke_test_failure():
    result = run_smoke_test("false")
    assert result["success"] is False
