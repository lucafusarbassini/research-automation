"""Tests for auto-documentation generation."""

from pathlib import Path

from core.auto_docs import (
    auto_update_docs,
    check_api_coverage,
    check_cli_commands,
    generate_cli_row,
    generate_module_index,
    generate_module_stub,
    scan_all_modules,
    scan_public_functions,
    update_api_doc,
    update_module_index,
    update_readme_commands,
)


def test_scan_public_functions(tmp_path: Path):
    mod = tmp_path / "example.py"
    mod.write_text(
        'def hello(name: str) -> str:\n    """Say hello."""\n    pass\n\n'
        "def _private():\n    pass\n\n"
        'class MyClass:\n    """A class."""\n    pass\n'
    )
    items = scan_public_functions(mod)
    names = [i["name"] for i in items]
    assert "hello" in names
    assert "_private" not in names
    assert "MyClass" in names
    # Check args extracted
    hello_item = [i for i in items if i["name"] == "hello"][0]
    assert "name" in hello_item["args"]


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

    missing = check_api_coverage(api, [core])
    assert "core.new_module" in missing
    assert "core.agents" not in missing


def test_check_api_coverage_no_file(tmp_path: Path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "foo.py").write_text("def bar(): pass\n")
    missing = check_api_coverage(tmp_path / "nope.md", [core])
    assert "core.foo" in missing


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
    assert check_cli_commands(tmp_path / "r.md", None) == []


def test_generate_module_stub():
    items = [
        {"name": "MyClass", "type": "class", "docstring": "A class.", "args": ""},
        {
            "name": "do_thing",
            "type": "function",
            "docstring": "Does a thing.",
            "args": "x, y=...",
        },
    ]
    stub = generate_module_stub("core.example", items)
    assert "core.example" in stub
    assert "MyClass" in stub
    assert "do_thing(x, y=...)" in stub
    assert "Does a thing." in stub


def test_generate_cli_row():
    row = generate_cli_row("list_sessions")
    assert "ricet list-sessions" in row
    assert "--help" in row


def test_generate_module_index():
    modules = {
        "core.agents": [
            {
                "name": "route",
                "type": "function",
                "docstring": "Route tasks.",
                "args": "",
            }
        ],
        "core.paper": [
            {
                "name": "compile",
                "type": "function",
                "docstring": "Compile paper.",
                "args": "",
            }
        ],
    }
    index = generate_module_index(modules)
    assert "core.agents" in index
    assert "core.paper" in index
    assert "Route tasks." in index


# --- Writer tests ---


def test_update_api_doc_creates_file(tmp_path: Path):
    api = tmp_path / "docs" / "API.md"
    missing = {
        "core.new_mod": [
            {"name": "func_a", "type": "function", "docstring": "Does A.", "args": "x"},
        ],
    }
    count = update_api_doc(api, missing)
    assert count == 1
    assert api.exists()
    content = api.read_text()
    assert "core.new_mod" in content
    assert "func_a(x)" in content
    assert "Does A." in content


def test_update_api_doc_appends(tmp_path: Path):
    api = tmp_path / "docs" / "API.md"
    api.parent.mkdir(parents=True)
    api.write_text("# API\n\n## `core.existing`\n\nDocs.\n")
    missing = {
        "core.brand_new": [
            {"name": "hello", "type": "function", "docstring": "Say hi.", "args": ""},
        ],
    }
    count = update_api_doc(api, missing)
    assert count == 1
    content = api.read_text()
    assert "core.existing" in content  # preserved
    assert "core.brand_new" in content  # appended


def test_update_api_doc_empty(tmp_path: Path):
    assert update_api_doc(tmp_path / "api.md", {}) == 0


def test_update_readme_commands_table(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# My Project\n\n"
        "| Command | Description |\n"
        "|---------|-------------|\n"
        "| `ricet init` | Initialize |\n"
    )
    count = update_readme_commands(readme, ["adopt", "link"])
    assert count == 2
    content = readme.read_text()
    assert "ricet adopt" in content
    assert "ricet link" in content
    assert "ricet init" in content  # preserved


def test_update_readme_commands_no_table(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text("# My Project\n\nNo table here.\n")
    count = update_readme_commands(readme, ["new_cmd"])
    assert count == 1
    content = readme.read_text()
    assert "ricet new-cmd" in content
    assert "## CLI Commands" in content


def test_update_readme_commands_empty(tmp_path: Path):
    assert update_readme_commands(tmp_path / "r.md", []) == 0


def test_update_module_index(tmp_path: Path):
    src = tmp_path / "core"
    src.mkdir()
    (src / "agents.py").write_text('def route():\n    """Route tasks."""\n    pass\n')
    (src / "paper.py").write_text('def compile():\n    """Compile."""\n    pass\n')

    index = tmp_path / "docs" / "MODULES.md"
    count = update_module_index(index, [src])
    assert count == 2
    assert index.exists()
    content = index.read_text()
    assert "core.agents" in content
    assert "core.paper" in content


# --- Integration test ---


def test_auto_update_docs_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("RICET_AUTO_DOCS", raising=False)
    result = auto_update_docs(project_root=tmp_path)
    assert result["api_added"] == 0


def test_auto_update_docs_full(tmp_path: Path):
    """End-to-end: project with source dir, README, no docs yet."""
    # Create a mini project
    src = tmp_path / "src"
    src.mkdir()
    (src / "math_lib.py").write_text(
        'def add(a, b):\n    """Add two numbers."""\n    return a + b\n\n'
        'def multiply(a, b):\n    """Multiply two numbers."""\n    return a * b\n'
    )
    readme = tmp_path / "README.md"
    readme.write_text("# My Project\n\nA cool project.\n")

    result = auto_update_docs(project_root=tmp_path, force=True)

    assert result["api_added"] == 1  # src.math_lib
    assert result["modules_indexed"] == 1

    # Check files were created
    api = tmp_path / "docs" / "API.md"
    assert api.exists()
    assert "math_lib" in api.read_text()
    assert "add(" in api.read_text()

    modules_index = tmp_path / "docs" / "MODULES.md"
    assert modules_index.exists()
    assert "src.math_lib" in modules_index.read_text()


def test_auto_update_docs_idempotent(tmp_path: Path):
    """Running twice should not duplicate stubs."""
    src = tmp_path / "core"
    src.mkdir()
    (src / "utils.py").write_text("def helper(): pass\n")
    (tmp_path / "README.md").write_text("# P\n")

    auto_update_docs(project_root=tmp_path, force=True)
    result = auto_update_docs(project_root=tmp_path, force=True)

    # Second run should add 0 because module is already documented
    assert result["api_added"] == 0
