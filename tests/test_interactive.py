import hashlib

from feasibility.interactive import prompt_analysis_request, run_interactive_session
from feasibility.models import ScopeRules
from feasibility.workflow import prepare_analysis_context, run_analysis_workflow


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
