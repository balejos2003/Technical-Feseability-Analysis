from feasibility.context import prepare_source_context
from feasibility.discovery import discover_repository
from feasibility.models import ScopeRules


def test_context_preserves_relative_lines_excerpt_hash_and_scope(tmp_path):
    source_file = tmp_path / "module.py"
    source_file.write_text("def calculate():\n    return 1\n", encoding="utf-8")
    rules = ScopeRules(excluded_dirs=("ignored",), excluded_files=("skip.py",))
    discovery = discover_repository(tmp_path, rules)

    context = prepare_source_context(
        tmp_path,
        discovery,
        scope_rules=rules,
        max_context_chars=1_000,
    )

    item = context.items[0]
    assert item.path == "module.py"
    assert item.start_line == 1
    assert item.end_line == 2
    assert item.excerpt == "def calculate():\n    return 1"
    assert len(item.file_hash) == 64
    assert context.excluded_dirs == ("ignored",)
    assert context.excluded_files == ("skip.py",)
    assert "module.py lines 1-2" in context.as_text()
    assert f"sha256:{item.file_hash}" in context.as_text()


def test_context_enforces_total_character_budget(tmp_path):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("a" * 40 + "\n", encoding="utf-8")
    second.write_text("b" * 40 + "\n", encoding="utf-8")
    discovery = discover_repository(tmp_path)

    context = prepare_source_context(
        tmp_path,
        discovery,
        max_context_chars=55,
    )

    assert context.total_chars <= 55
    assert context.truncated_files or len(context.items) < 2
    assert context.issues == ()


def test_context_keeps_discovery_issues_visible(tmp_path):
    binary_file = tmp_path / "data.bin"
    binary_file.write_bytes(b"\x00\x01")
    discovery = discover_repository(tmp_path)

    context = prepare_source_context(tmp_path, discovery)

    assert context.items == ()
    assert len(context.issues) == 1
    assert "data.bin" in context.as_text()


def test_context_includes_constitution_without_special_priority(tmp_path):
    constitution = tmp_path / ".specify" / "memory" / "constitution.md"
    constitution.parent.mkdir(parents=True)
    constitution.write_text("# Constitution\n\nProtect the codebase.\n", encoding="utf-8")
    source_file = tmp_path / "source.py"
    source_file.write_text("value = 1\n", encoding="utf-8")

    discovery = discover_repository(tmp_path)
    context = prepare_source_context(tmp_path, discovery, max_context_chars=1_000)

    assert [item.path for item in context.items] == [
        ".specify/memory/constitution.md",
        "source.py",
    ]
    assert "Constitution" in context.items[0].excerpt
