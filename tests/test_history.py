import json
import sqlite3

from feasibility.history import get_history_detail, list_history, search_history
from feasibility.storage import initialize_schema


def _seed_history(db_path):
    initialize_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO request (request_id, principal_id, codebase_root, change_description, scope_rules, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "req-1",
                "alice",
                "/tmp/repo",
                "Add a new API client to the service layer.",
                json.dumps({"excluded_dirs": ["node_modules"]}),
                "2026-09-19T10:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO request (request_id, principal_id, codebase_root, change_description, scope_rules, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "req-2",
                "bob",
                "/tmp/other",
                "Refactor the worker queue for better retries.",
                json.dumps({"excluded_dirs": ["dist"]}),
                "2026-09-19T11:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO assessment (
                assessment_id,
                request_id,
                principal_id,
                conclusion,
                evaluated_scope,
                findings,
                limitations,
                report_markdown,
                analyzer_version,
                created_at,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "assess-1",
                "req-1",
                "alice",
                "conditionally_feasible",
                json.dumps(["src/service.py"]),
                json.dumps(
                    [
                        {
                            "finding_id": "f-1",
                            "category": "interpretation",
                            "statement": "The service layer can be extended cleanly.",
                            "basis": "The requested change fits the current adapter pattern.",
                            "uncertainty": "Low",
                            "severity": "medium",
                            "evidence_ids": ["ev-1"],
                        }
                    ]
                ),
                json.dumps(["Runtime verification remains pending."]),
                "# Report\n\nThe service layer can be extended cleanly.",
                "1.0.0",
                "2026-09-19T10:05:00+00:00",
                "completed",
            ),
        )
        conn.execute(
            """
            INSERT INTO assessment (
                assessment_id,
                request_id,
                principal_id,
                conclusion,
                evaluated_scope,
                findings,
                limitations,
                report_markdown,
                analyzer_version,
                created_at,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "assess-2",
                "req-2",
                "bob",
                "feasible",
                json.dumps(["src/worker.py"]),
                json.dumps(
                    [
                        {
                            "finding_id": "f-2",
                            "category": "fact",
                            "statement": "The queue has retry hooks already.",
                            "basis": "The code already exposes retry configuration.",
                            "uncertainty": None,
                            "severity": "low",
                            "evidence_ids": ["ev-2"],
                        }
                    ]
                ),
                json.dumps(["No constraints beyond current backlog." ]),
                "# Report\n\nThe queue already has retry hooks.",
                "1.0.0",
                "2026-09-19T11:05:00+00:00",
                "completed",
            ),
        )
        conn.execute(
            """
            INSERT INTO assessment (
                assessment_id,
                request_id,
                principal_id,
                conclusion,
                evaluated_scope,
                findings,
                limitations,
                report_markdown,
                analyzer_version,
                created_at,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "assess-3",
                "req-1",
                "alice",
                "failed",
                json.dumps(["src/legacy.py"]),
                json.dumps([]),
                json.dumps(["No valid evidence captured."]),
                "# Report\n\nThe assessment failed.",
                "1.0.0",
                "2026-09-19T12:05:00+00:00",
                "failed",
            ),
        )


def test_list_history_only_returns_completed_assessments_for_principal(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    _seed_history(db_path)

    items = list_history("alice", database_path=db_path)

    assert [item.assessment_id for item in items] == ["assess-1"]
    assert all(item.principal_id == "alice" for item in items)


def test_search_history_filters_by_text_and_principal(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    _seed_history(db_path)

    items = search_history("alice", "service", database_path=db_path)

    assert [item.assessment_id for item in items] == ["assess-1"]
    assert search_history("bob", "service", database_path=db_path) == []


def test_get_history_detail_requires_authorized_principal(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    _seed_history(db_path)

    detail = get_history_detail("assess-1", "alice", database_path=db_path)
    assert detail is not None
    assert detail.assessment.assessment_id == "assess-1"
    assert get_history_detail("assess-1", "bob", database_path=db_path) is None
