"""Tests for auto-documentation gap detection."""

from pathlib import Path

from core.auto_docs import (
    auto_update_docs,
    check_api_coverage,
    check_cli_commands,
    generate_module_stub,
    scan_all_modules,
    scan_public_functions,
)


def test_scan_public_functions(tmp_path: Path):
    mod = tmp_path / "example.py"
    mod.write_text(
        'def hello():\n    """Say hello."""\n    pass\n\n'
        "def _private():\n    pass\n\n"
        'class MyClass:\n    """A class."""\n    pass\n'
    )
    items = scan_public_functions(mod)
    names = [i["name"] for i in items]
    assert "hello" in names
    assert "_private" not in names
    assert "MyClass" in names


def test_scan_public_functions_syntax_error(tmp_path: Path):
    mod = tmp_path / "bad.py"
    mod.write_text("def broken(:\n    pass\n")
    assert scan_public_functions(mod) == []


def test_scan_public_functions_nonexistent(tmp_path: Path):
    assert scan_public_functions(tmp_path / "nope.py") == []


def test_scan_all_modules(tmp_path: Path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "agents.py").write_text("def route_task(): pass\n")
    (core / "utils.py").write_text("def helper(): pass\n")
    (core / "__init__.py").write_text("")

    modules = scan_all_modules(core)
    assert "agents" in modules
    assert "utils" in modules
    assert "__init__" not in modules


def test_check_api_coverage(tmp_path: Path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "agents.py").write_text("def route_task(): pass\n")
    (core / "new_module.py").write_text("def new_func(): pass\n")

    api = tmp_path / "api.md"
    api.write_text("## `core.agents`\n\nSome docs here.\n")

    missing = check_api_coverage(api, core)
    assert "new_module" in missing
    assert "agents" not in missing


def test_check_api_coverage_no_file(tmp_path: Path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "foo.py").write_text("def bar(): pass\n")
    missing = check_api_coverage(tmp_path / "nope.md", core)
    assert "foo" in missing


def test_check_cli_commands(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text("| `ricet init` | Initialize |\n| `ricet start` | Start |\n")

    cli = tmp_path / "main.py"
    cli.write_text(
        "@app.command()\ndef init():\n    pass\n\n"
        "@app.command()\ndef start():\n    pass\n\n"
        "@app.command()\ndef adopt():\n    pass\n"
    )

    missing = check_cli_commands(readme, cli)
    assert "adopt" in missing
    assert "init" not in missing


def test_check_cli_commands_no_files(tmp_path: Path):
    assert check_cli_commands(tmp_path / "r.md", tmp_path / "m.py") == []


def test_generate_module_stub():
    items = [
        {"name": "MyClass", "type": "class", "docstring": "A class."},
        {"name": "do_thing", "type": "function", "docstring": "Does a thing."},
    ]
    stub = generate_module_stub("example", items)
    assert "core.example" in stub
    assert "MyClass" in stub
    assert "do_thing" in stub
    assert "Does a thing." in stub


def test_auto_update_docs_disabled(tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"):
    monkeypatch.delenv("RICET_AUTO_DOCS", raising=False)
    result = auto_update_docs(
        core_dir=tmp_path / "core",
        docs_api=tmp_path / "api.md",
        readme=tmp_path / "README.md",
    )
    assert result["missing_api_modules"] == []
    assert result["missing_cli_commands"] == []


def test_auto_update_docs_forced(tmp_path: Path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "new_mod.py").write_text("def func(): pass\n")
    api = tmp_path / "api.md"
    api.write_text("")

    result = auto_update_docs(
        core_dir=core,
        docs_api=api,
        readme=tmp_path / "README.md",
        force=True,
    )
    assert "new_mod" in result["missing_api_modules"]
