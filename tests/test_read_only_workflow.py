import hashlib
import os
import shutil
from pathlib import Path

from feasibility.workflow import run_analysis_workflow


def snapshot_tree(root: Path) -> dict[str, tuple[str, bytes | None]]:
    snapshot: dict[str, tuple[str, bytes | None]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path).encode("utf-8"))
        elif path.is_dir():
            snapshot[relative] = ("directory", None)
        else:
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


def test_analysis_workflow_leaves_analyzed_fixture_unchanged(tmp_path, monkeypatch):
    fixture_root = Path(__file__).parent / "fixtures" / "mixed-repo"
    analyzed_root = tmp_path / "analyzed-repo"
    shutil.copytree(fixture_root, analyzed_root)
    data_dir = tmp_path / "application-data"
    monkeypatch.setenv("FEASIBILITY_DATA_DIR", str(data_dir))

    source_path = analyzed_root / "src" / "service.py"
    source_text = source_path.read_text(encoding="utf-8")
    source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    before = snapshot_tree(analyzed_root)

    def provider(_prompt):
        return {
            "conclusion": "conditionally_feasible",
            "findings": [
                {
                    "id": "f-read-only",
                    "category": "fact",
                    "statement": "The service entry point is available.",
                    "basis": "The fixture contains the service implementation.",
                    "evidence": [
                        {
                            "id": "ev-read-only",
                            "kind": "code",
                            "path": "src/service.py",
                            "start_line": 1,
                            "end_line": 3,
                            "excerpt": "\n".join(source_text.splitlines()[:3]),
                            "hash": source_hash,
                            "description": "The service entry point is the inspected source.",
                        }
                    ],
                }
            ],
            "limitations": ["Runtime behavior was not tested."],
            "assumptions": [],
            "estimates": [],
            "suggestions": [],
            "unresolved_questions": [],
        }

    assessment = run_analysis_workflow(
        {
            "codebase_path": str(analyzed_root),
            "requested_change": "Add a cache to the service",
            "additional_context": "",
            "save_report": True,
        },
        principal_id="read-only-test",
        provider=provider,
    )

    after = snapshot_tree(analyzed_root)
    assert after == before
    assert assessment.report_markdown
    assert (data_dir / "history.sqlite3").is_file()
    assert (data_dir / "reports" / f"{assessment.assessment_id}.md").is_file()
    assert not any(path.is_relative_to(analyzed_root) for path in data_dir.rglob("*"))
