from feasibility.ai_analysis import (
    AnalysisResponse,
    build_analysis_prompt,
    normalize_analysis_response,
)
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
