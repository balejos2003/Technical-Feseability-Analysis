from feasibility.ai_analysis import (
    AnalysisResponse,
    build_analysis_prompt,
    invoke_analysis_provider,
    normalize_analysis_response,
)
from feasibility.context import prepare_source_context
from feasibility.discovery import discover_repository
from feasibility.models import AnalysisRequest
from feasibility.models import EvidenceKind, FeasibilityConclusion, FindingCategory


def test_build_analysis_prompt_includes_required_fields():
    prompt = build_analysis_prompt(
        repository_root="/tmp/repo",
        change_description="Add a new API client",
        scope_summary="two files inspected",
        context="File A\nFile B",
    )

    assert "Add a new API client" in prompt
    assert "two files inspected" in prompt
    assert "File A" in prompt
    assert "evidence" in prompt.lower()


def test_normalize_analysis_response_validates_structure():
    payload = {
        "conclusion": "conditionally_feasible",
        "findings": [
            {
                "id": "f-1",
                "category": "interpretation",
                "statement": "The change is feasible with a small adapter layer.",
                "basis": "The code shows a single extension point.",
                "uncertainty": "Low uncertainty.",
                "severity": "medium",
                "evidence": [
                    {
                        "id": "ev-1",
                        "kind": "code",
                        "path": "src/api.py",
                        "start_line": 10,
                        "end_line": 12,
                        "excerpt": "client = ApiClient()",
                        "hash": "abc123",
                        "description": "The adapter point is clearly visible here.",
                    }
                ],
            }
        ],
        "limitations": ["No runtime proof yet."],
        "assumptions": ["The API contract is stable."],
        "estimates": [
            {
                "label": "Implementation effort",
                "value": "2-4 days",
                "basis": "Small code path and limited integration points.",
                "uncertainty": "Medium.",
            }
        ],
        "suggestions": ["Add a small adapter and review the contract."],
        "unresolved_questions": ["What is the production API version?"],
    }

    result = normalize_analysis_response(payload)
    assert result.conclusion == FeasibilityConclusion.CONDITIONALLY_FEASIBLE
    assert result.findings[0].category == FindingCategory.INTERPRETATION
    assert result.findings[0].evidence_ids == ["ev-1"]
    assert result.estimates[0]["label"] == "Implementation effort"
    assert result.limits == ["No runtime proof yet."]


def test_normalize_analysis_response_accepts_case_variations_from_provider():
    payload = {
        "conclusion": "Feasible",
        "findings": [
            {
                "id": "f-case",
                "category": "Fact",
                "statement": "The entry point exists.",
                "basis": "The supplied source contains it.",
                "severity": "High",
                "evidence": [{"id": "ev-case", "kind": "Code"}],
            }
        ],
        "limitations": ["Runtime behavior was not tested."],
        "assumptions": [],
        "estimates": [],
        "suggestions": [],
    }

    result = normalize_analysis_response(payload)

    assert result.conclusion == FeasibilityConclusion.FEASIBLE
    assert result.findings[0].category == FindingCategory.FACT
    assert result.findings[0].severity.value == "high"


def test_normalize_analysis_response_rejects_missing_evidence():
    payload = {
        "conclusion": "feasible",
        "findings": [
            {
                "id": "f-1",
                "category": "fact",
                "statement": "The repository already has enough abstractions.",
                "basis": "It is plainly obvious.",
                "evidence": [],
            }
        ],
        "limitations": ["No proof available."],
        "assumptions": [],
        "estimates": [],
        "suggestions": [],
    }

    try:
        normalize_analysis_response(payload)
        assert False, "Expected ValueError for uncited material finding"
    except ValueError:
        pass


def test_invoke_analysis_provider_builds_prompt_from_bounded_context(tmp_path):
    source_file = tmp_path / "module.py"
    source_file.write_text("def calculate():\n    return 1\n", encoding="utf-8")
    discovery = discover_repository(tmp_path)
    source_context = prepare_source_context(tmp_path, discovery)
    request = AnalysisRequest(
        request_id="request-1",
        principal_id="developer-1",
        codebase_root=str(tmp_path),
        change_description="Add caching to calculate",
    )
    prompts = []

    def provider(prompt):
        prompts.append(prompt)
        return {"conclusion": "feasible"}

    response = invoke_analysis_provider(request, source_context, provider=provider)

    assert response == {"conclusion": "feasible"}
    assert len(prompts) == 1
    assert "Add caching to calculate" in prompts[0]
    assert "module.py lines 1-2" in prompts[0]
    assert "Do not modify the repository" in prompts[0]


def test_normalize_rejects_missing_limitations():
    payload = {
        "conclusion": "feasible",
        "findings": [
            {
                "id": "f-1",
                "category": "fact",
                "statement": "The entry point exists.",
                "basis": "The supplied source contains the entry point.",
                "evidence": [{"id": "ev-1", "kind": "code"}],
            }
        ],
        "assumptions": [],
        "estimates": [],
        "suggestions": [],
    }

    try:
        normalize_analysis_response(payload)
        assert False, "Expected ValueError for missing limitations"
    except ValueError as exc:
        assert "limitations" in str(exc)


def test_normalize_rejects_estimate_without_label():
    payload = {
        "conclusion": "conditionally_feasible",
        "findings": [
            {
                "id": "f-1",
                "category": "estimate",
                "statement": "The change is small.",
                "basis": "Only one module is involved.",
                "evidence": [{"id": "ev-1", "kind": "code"}],
            }
        ],
        "limitations": ["Runtime behavior was not tested."],
        "assumptions": [],
        "estimates": [{"value": "1 day", "basis": "One module."}],
        "suggestions": [],
    }

    try:
        normalize_analysis_response(payload)
        assert False, "Expected ValueError for unlabeled estimate"
    except ValueError as exc:
        assert "label" in str(exc)


def test_normalize_rejects_evidence_outside_supplied_context(tmp_path):
    source_file = tmp_path / "module.py"
    source_file.write_text("value = 1\n", encoding="utf-8")
    source_context = prepare_source_context(tmp_path, discover_repository(tmp_path))
    payload = {
        "conclusion": "feasible",
        "findings": [
            {
                "id": "f-1",
                "category": "fact",
                "statement": "The unrelated file controls the behavior.",
                "basis": "The provider cited a file outside the supplied context.",
                "evidence": [
                    {
                        "id": "ev-1",
                        "kind": "code",
                        "path": "outside.py",
                        "start_line": 1,
                        "end_line": 1,
                        "excerpt": "value = 2",
                        "hash": "not-from-context",
                    }
                ],
            }
        ],
        "limitations": ["The context was bounded."],
        "assumptions": [],
        "estimates": [],
        "suggestions": [],
    }

    try:
        normalize_analysis_response(payload, source_context=source_context)
        assert False, "Expected ValueError for evidence outside context"
    except ValueError as exc:
        assert "context" in str(exc)
