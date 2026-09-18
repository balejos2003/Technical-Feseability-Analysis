from pathlib import Path

from feasibility.evidence import EvidenceCapture, capture_evidence


def test_capture_evidence_uses_inclusive_ranges_and_hash(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    code_path = repo / "src" / "app.py"
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    evidence = capture_evidence(
        repository_root=repo,
        path="src/app.py",
        start_line=2,
        end_line=3,
    )

    assert evidence.path == "src/app.py"
    assert evidence.start_line == 2
    assert evidence.end_line == 3
    assert evidence.excerpt.strip().splitlines() == ["beta", "gamma"]
    assert evidence.file_hash


def test_evidence_capture_rejects_invalid_ranges(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    code_path = repo / "file.py"
    code_path.write_text("a\nb\n", encoding="utf-8")

    try:
        capture_evidence(repo, "file.py", start_line=3, end_line=2)
        assert False, "Expected ValueError for reversed range"
    except ValueError:
        pass


def test_evidence_capture_rejects_missing_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    try:
        capture_evidence(repo, "missing.py", start_line=1, end_line=1)
        assert False, "Expected FileNotFoundError for missing file"
    except FileNotFoundError:
        pass
