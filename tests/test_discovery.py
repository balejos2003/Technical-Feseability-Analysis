from pathlib import Path

import pytest

from feasibility.discovery import discover_repository


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_discovery_excludes_directories_and_large_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_text(repo / "src" / "app.py", "print('hello')\n")
    write_text(repo / "node_modules" / "dep.js", "console.log('skip')\n")
    (repo / "large.txt").write_bytes(b"x" * 200)

    result = discover_repository(
        repo,
        scope_rules={
            "excluded_dirs": ("node_modules",),
            "max_file_size_bytes": 64,
        },
    )

    discovered = {item.relative_path for item in result.files}
    assert "src/app.py" in discovered
    assert "node_modules/dep.js" not in discovered
    assert "large.txt" not in discovered
    assert any(issue.kind == "too_large" for issue in result.issues)


def test_discovery_marks_binary_or_unsupported_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "image.bin").write_bytes(b"\x00\x01\x02\x03\x04")

    result = discover_repository(repo)

    assert not any(item.relative_path == "image.bin" for item in result.files)
    assert any(issue.kind == "unreadable" for issue in result.issues)


def test_discovery_skips_symlinks_when_not_followed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "target.txt"
    target.write_text("real text\n", encoding="utf-8")
    link = repo / "link.txt"
    link.symlink_to(target)

    result = discover_repository(repo)

    assert not any(item.relative_path == "link.txt" for item in result.files)
    assert any(issue.kind == "symlink_skipped" for issue in result.issues)


def test_discovery_rejects_app_outputs_under_repository_root(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    bad_data_dir = repo / ".feasibility"

    monkeypatch.setenv("FEASIBILITY_DATA_DIR", str(bad_data_dir))

    with pytest.raises(ValueError, match="outside the analyzed repository"):
        discover_repository(repo)
