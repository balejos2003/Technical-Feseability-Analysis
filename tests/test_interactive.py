import hashlib
import json
import sqlite3

import pytest

from feasibility.ai_analysis import build_openai_provider
from feasibility.errors import AIServiceUnavailableError
from feasibility.interactive import (
    display_report,
    prompt_analysis_request,
    run_history_menu,
    save_external_report,
    run_interactive_session,
)
from feasibility.models import (
    AssessmentStatus,
    FeasibilityAssessment,
    FeasibilityConclusion,
    Finding,
    FindingCategory,
    ScopeRules,
)
from feasibility.storage import initialize_schema
from feasibility.workflow import prepare_analysis_context, run_analysis_workflow


def _seed_history_for_menu(db_path):
    initialize_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO request (request_id, principal_id, codebase_root, change_description, scope_rules, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "req-menu",
                "alice",
                "/tmp/repo",
                "Add a new API client to the service layer.",
                json.dumps({"excluded_dirs": ["node_modules"]}),
                "2026-09-19T10:00:00+00:00",
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
                "assess-menu",
                "req-menu",
                "alice",
                "conditionally_feasible",
                json.dumps(["src/service.py"]),
                json.dumps([
                    {
                        "finding_id": "f-menu",
                        "category": "interpretation",
                        "statement": "The service layer can be extended cleanly.",
                        "basis": "The requested change fits the current adapter pattern.",
                        "uncertainty": "Low",
                        "severity": "medium",
                        "evidence_ids": ["ev-menu"],
                    }
                ]),
                json.dumps(["Runtime verification remains pending."]),
                "# Report\n\nThe service layer can be extended cleanly.",
                "1.0.0",
                "2026-09-19T10:05:00+00:00",
                "completed",
            ),
        )
        conn.execute(
            """
            INSERT INTO evidence (
                evidence_id,
                assessment_id,
                kind,
                path,
                start_line,
                end_line,
                excerpt,
                file_hash,
                description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ev-menu",
                "assess-menu",
                "code",
                "src/service.py",
                12,
                18,
                "adapter = ClientAdapter()",
                "abc123",
                "The service layer already uses an adapter pattern that matches the proposed extension.",
            ),
        )
        conn.execute(
            """
            INSERT INTO finding (
                finding_id,
                assessment_id,
                category,
                severity,
                statement,
                basis,
                uncertainty
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "f-menu",
                "assess-menu",
                "interpretation",
                "medium",
                "The service layer can be extended cleanly.",
                "The requested change fits the current adapter pattern.",
                "Low",
            ),
        )
        conn.execute(
            """
            INSERT INTO finding_evidence (finding_id, evidence_id) VALUES (?, ?)
            """,
            ("f-menu", "ev-menu"),
        )


def test_history_menu_supports_list_search_and_open(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    _seed_history_for_menu(db_path)

    inputs = iter(["1", "2", "service", "3", "assess-menu", "4"])
    output = []

    run_history_menu(
        input_fn=lambda _: next(inputs),
        output_fn=output.append,
        principal_id="alice",
        database_path=str(db_path),
    )

    assert any("assess-menu" in message for message in output)
    assert any("No matching analyses found." in message for message in output) is False
    assert any("The service layer can be extended cleanly." in message for message in output)


def test_session_exits_from_main_menu():
    inputs = iter(["3"])
    output = []

    run_interactive_session(input_fn=lambda _: next(inputs), output_fn=output.append)

    assert output == [
        "1. Analyze a change",
        "2. Consult analysis history",
        "3. Exit",
    ]


def test_invalid_menu_choice_keeps_session_open():
    inputs = iter(["invalid", "3"])
    output = []

    run_interactive_session(input_fn=lambda _: next(inputs), output_fn=output.append)

    assert "Invalid menu choice. Please select 1, 2, or 3." in output
    assert output.count("1. Analyze a change") == 2


def test_analysis_prompt_collects_all_requested_values(tmp_path):
    answers = iter([
        str(tmp_path),
        "Add a cache to the data access path",
        "The cache must be invalidated after writes.",
        "yes",
    ])

    request_input = prompt_analysis_request(input_fn=lambda _: next(answers))

    assert request_input == {
        "codebase_path": str(tmp_path),
        "requested_change": "Add a cache to the data access path",
        "additional_context": "The cache must be invalidated after writes.",
        "save_report": True,
    }


def test_analysis_prompt_accepts_blank_optional_context_and_no_save():
    answers = iter([".", "Refactor the parser", "", "no"])

    request_input = prompt_analysis_request(input_fn=lambda _: next(answers))

    assert request_input["additional_context"] == ""
    assert request_input["save_report"] is False


def test_analysis_prompt_retries_unavailable_path_and_blank_change(tmp_path):
    answers = iter([
        str(tmp_path / "missing"),
        str(tmp_path),
        "",
        "Add validation",
        "",
        "no",
    ])
    output = []

    request_input = prompt_analysis_request(
        input_fn=lambda _: next(answers),
        output_fn=output.append,
    )

    assert request_input["codebase_path"] == str(tmp_path)
    assert request_input["requested_change"] == "Add validation"
    assert "Codebase path is unavailable. Please try again." in output
    assert "Requested change cannot be blank. Please try again." in output


def test_analysis_prompt_explains_that_a_file_is_not_a_codebase_root(tmp_path):
    source_file = tmp_path / "script.js"
    source_file.write_text("console.log('ok');\n", encoding="utf-8")
    answers = iter([str(source_file), str(tmp_path), "Review the script", "", "no"])
    output = []

    request_input = prompt_analysis_request(
        input_fn=lambda _: next(answers),
        output_fn=output.append,
    )

    assert request_input["codebase_path"] == str(tmp_path)
    assert any("Codebase path must be a directory, not a file." in message for message in output)


def test_session_ends_cleanly_when_interrupted():
    output = []

    def interrupted_input(_: str) -> str:
        raise KeyboardInterrupt

    run_interactive_session(input_fn=interrupted_input, output_fn=output.append)

    assert output[-1] == "Session ended."


def test_analysis_context_preserves_request_and_discovered_scope(tmp_path):
    source_file = tmp_path / "module.py"
    source_file.write_text("def calculate():\n    return 1\n", encoding="utf-8")
    request_input = {
        "codebase_path": str(tmp_path),
        "requested_change": "Add caching to calculate",
        "additional_context": "Cache values for one minute.",
        "save_report": True,
    }

    context = prepare_analysis_context(
        request_input,
        principal_id="developer-1",
        request_id="request-1",
        scope_rules=ScopeRules(allowed_extensions=("py",)),
    )

    assert context.request.codebase_root == str(tmp_path.resolve())
    assert context.request.change_description == "Add caching to calculate"
    assert context.additional_context == "Cache values for one minute."
    assert [item.relative_path for item in context.discovery.files] == ["module.py"]
    assert context.request.scope_rules.allowed_extensions == ("py",)


def test_menu_option_one_runs_analysis_workflow(tmp_path):
    (tmp_path / "module.py").write_text("value = 1\n", encoding="utf-8")
    inputs = iter(["1", str(tmp_path), "Change value", "", "no", "3"])
    output = []

    run_interactive_session(input_fn=lambda _: next(inputs), output_fn=output.append)

    assert "Analysis request prepared." in output
    assert "Discovered files: 1" in output


def test_menu_option_one_runs_provider_and_displays_completed_report(tmp_path):
    source_text = "def calculate():\n    return 1\n"
    (tmp_path / "module.py").write_text(source_text, encoding="utf-8")
    file_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    inputs = iter(["1", str(tmp_path), "Add parentheses", "", "no", "yes", "yes", "3"])

    def provider(prompt):
        return {
            "conclusion": "feasible",
            "findings": [
                {
                    "id": "f-interactive",
                    "category": "fact",
                    "statement": "The calculator entry point is available.",
                    "basis": "The supplied module contains the calculation function.",
                    "evidence": [
                        {
                            "id": "ev-interactive",
                            "kind": "code",
                            "path": "module.py",
                            "start_line": 1,
                            "end_line": 2,
                            "excerpt": source_text,
                            "hash": file_hash,
                            "description": "The calculation function is the relevant entry point.",
                        }
                    ],
                }
            ],
            "limitations": ["Runtime behavior was not tested."],
            "assumptions": [],
            "estimates": [],
            "suggestions": ["Add focused tests for nested parentheses."],
            "unresolved_questions": [],
        }

    output = []
    run_interactive_session(
        input_fn=lambda _: next(inputs),
        output_fn=output.append,
        provider=provider,
    )

    assert any("# Technical Feasibility Assessment" in message for message in output)
    assert any("## Developer Review" in message for message in output)
    assert any("reviewed this assessment" in message.lower() for message in output)


def test_openai_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AIServiceUnavailableError, match="OPENAI_API_KEY"):
        build_openai_provider()


def test_run_analysis_workflow_creates_assessment_and_report(tmp_path):
    source_file = tmp_path / "service.py"
    source_text = "def connect():\n    return 1\n"
    source_file.write_text(source_text, encoding="utf-8")
    file_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    request_input = {
        "codebase_path": str(tmp_path),
        "requested_change": "Add a small adapter around the service",
        "additional_context": "The API contract is stable.",
        "save_report": False,
    }

    def provider(prompt):
        return {
            "conclusion": "conditionally_feasible",
            "findings": [
                {
                    "id": "f-1",
                    "category": "interpretation",
                    "statement": "The change is feasible with a small adapter.",
                    "basis": "The service exposes a clear integration seam.",
                    "uncertainty": "Low uncertainty.",
                    "severity": "medium",
                    "evidence": [
                        {
                            "id": "ev-1",
                            "kind": "code",
                            "path": "service.py",
                            "start_line": 1,
                            "end_line": 2,
                            "excerpt": source_text,
                            "hash": file_hash,
                            "description": "The adapter point is defined directly in the service entry point.",
                        }
                    ],
                }
            ],
            "limitations": ["Runtime behavior remains untested."],
            "assumptions": ["The existing API contract is stable."],
            "estimates": [
                {
                    "label": "Implementation effort",
                    "value": "2-4 days",
                    "basis": "Single integration seam and limited surface.",
                    "uncertainty": "Medium.",
                }
            ],
            "suggestions": ["Add a thin adapter and verify the contract end-to-end."],
            "unresolved_questions": ["What is the production contract version?"],
        }

    assessment = run_analysis_workflow(request_input, principal_id="alice", provider=provider)

    assert assessment.conclusion.value == "conditionally_feasible"
    assert len(assessment.findings) == 1
    assert assessment.evidence_items[0].path == "service.py"
    assert "# Technical Feasibility Assessment" in assessment.report_markdown
    assert "## Findings" in assessment.report_markdown
    assert "Implementation effort" in assessment.report_markdown


def test_run_analysis_workflow_retries_uncited_provider_response(tmp_path):
    source_text = "def calculate():\n    return 1\n"
    (tmp_path / "module.py").write_text(source_text, encoding="utf-8")
    file_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    responses = iter(
        [
            {
                "conclusion": "feasible",
                "findings": [{"id": "f-1", "category": "fact", "statement": "Uncited", "basis": "Missing evidence."}],
                "limitations": ["The first response was incomplete."],
            },
            {
                "conclusion": "feasible",
                "findings": [
                    {
                        "id": "f-1",
                        "category": "fact",
                        "statement": "The calculator entry point exists.",
                        "basis": "The supplied module contains the function.",
                        "evidence": [
                            {
                                "id": "ev-1",
                                "kind": "code",
                                "path": "module.py",
                                "start_line": 1,
                                "end_line": 2,
                                "excerpt": source_text,
                                "hash": file_hash,
                                "description": "The function is the relevant entry point.",
                            }
                        ],
                    }
                ],
                "limitations": ["Runtime behavior was not tested."],
                "assumptions": [],
                "estimates": [],
                "suggestions": [],
                "unresolved_questions": [],
            },
        ]
    )
    prompts = []

    def provider(prompt):
        prompts.append(prompt)
        return next(responses)

    assessment = run_analysis_workflow(
        {
            "codebase_path": str(tmp_path),
            "requested_change": "Add parentheses",
            "additional_context": "",
            "save_report": False,
        },
        principal_id="alice",
        provider=provider,
    )

    assert assessment.conclusion.value == "feasible"
    assert len(prompts) == 2
    assert "CORRECTION REQUIRED" in prompts[1]


def test_display_report_outputs_complete_markdown_report():
    assessment = FeasibilityAssessment(
        assessment_id="assess-display",
        request_id="request-display",
        principal_id="alice",
        conclusion=FeasibilityConclusion.FEASIBLE,
        evaluated_scope=["service.py"],
        findings=[
            Finding(
                finding_id="finding-display",
                category=FindingCategory.FACT,
                statement="The service entry point exists.",
                basis="The supplied source contains the entry point.",
                evidence_ids=["evidence-display"],
            )
        ],
        limitations=["Runtime behavior was not tested."],
        report_markdown="# Technical Feasibility Assessment\n\n## Conclusion\nFeasible\n",
        analyzer_version="1.0.0",
        status=AssessmentStatus.COMPLETED,
    )
    output = []

    display_report(assessment, output_fn=output.append)

    assert output == [assessment.report_markdown]


def test_save_external_report_writes_copy_outside_codebase(tmp_path):
    assessment = FeasibilityAssessment(
        assessment_id="assess-copy",
        request_id="request-copy",
        principal_id="alice",
        conclusion=FeasibilityConclusion.FEASIBLE,
        evaluated_scope=["service.py"],
        findings=[
            Finding(
                finding_id="finding-copy",
                category=FindingCategory.FACT,
                statement="The service entry point exists.",
                basis="The supplied source contains the entry point.",
                evidence_ids=["evidence-copy"],
            )
        ],
        limitations=["Runtime behavior was not tested."],
        report_markdown="# Technical Feasibility Assessment\n",
        analyzer_version="1.0.0",
        status=AssessmentStatus.COMPLETED,
    )

    report_path = save_external_report(
        assessment,
        repository_root=tmp_path / "codebase",
        reports_dir=tmp_path / "reports",
    )

    assert report_path == (tmp_path / "reports" / "assess-copy.md").resolve()
    assert report_path.read_text(encoding="utf-8") == assessment.report_markdown
