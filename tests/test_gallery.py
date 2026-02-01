"""Tests for the plot gallery."""

from pathlib import Path

from cli.gallery import (
    FigureEntry,
    display_gallery,
    organize_by_run,
    scan_figures,
)


def test_scan_figures_empty(tmp_path: Path):
    figs = scan_figures(tmp_path / "nonexistent")
    assert figs == []


def test_scan_figures(tmp_path: Path):
    (tmp_path / "plot1.png").write_bytes(b"\x89PNG" + b"\x00" * 100)
    (tmp_path / "plot2.pdf").write_bytes(b"%PDF" + b"\x00" * 200)
    (tmp_path / "data.csv").write_text("not a figure")

    figs = scan_figures(tmp_path)
    assert len(figs) == 2
    names = {f.name for f in figs}
    assert "plot1" in names
    assert "plot2" in names


def test_scan_figures_with_run_dirs(tmp_path: Path):
    run_dir = tmp_path / "run-001"
    run_dir.mkdir()
    (run_dir / "loss.png").write_bytes(b"\x89PNG" + b"\x00" * 50)

    figs = scan_figures(tmp_path)
    assert len(figs) == 1
    assert figs[0].run_id == "run-001"


def test_organize_by_run():
    figs = [
        FigureEntry(
            path=Path("a.png"), name="a", format="png", size_kb=10, run_id="run-1"
        ),
        FigureEntry(
            path=Path("b.png"), name="b", format="png", size_kb=20, run_id="run-1"
        ),
        FigureEntry(
            path=Path("c.png"), name="c", format="png", size_kb=30, run_id="run-2"
        ),
        FigureEntry(path=Path("d.png"), name="d", format="png", size_kb=5),
    ]
    by_run = organize_by_run(figs)
    assert len(by_run["run-1"]) == 2
    assert len(by_run["run-2"]) == 1
    assert len(by_run["(no run)"]) == 1


def test_organize_by_run_empty():
    by_run = organize_by_run([])
    assert by_run == {}


def test_display_gallery_empty(tmp_path: Path):
    result = display_gallery(tmp_path / "nonexistent")
    assert "No figures" in result


def test_display_gallery(tmp_path: Path):
    (tmp_path / "fig1.png").write_bytes(b"\x89PNG" + b"\x00" * 100)
    (tmp_path / "fig2.svg").write_text("<svg></svg>")

    result = display_gallery(tmp_path)
    assert "Figure Gallery" in result
    assert "fig1" in result
    assert "fig2" in result
