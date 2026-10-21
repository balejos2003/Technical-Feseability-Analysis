import json

import pytest

from feasibility import ai_analysis
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


def test_build_api_provider_uses_generic_key_endpoint_and_model(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}]}).encode()

    def fake_urlopen(request, timeout, context):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        captured["context"] = context
        return Response()

    monkeypatch.setattr(ai_analysis, "urlopen", fake_urlopen)
    provider = ai_analysis.build_api_provider(
        provider_name="openai-compatible",
        api_key="provider-key",
        base_url="https://provider.example/v1",
        model="provider-model",
    )

    assert provider("Analyze this") == {"ok": True}
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer provider-key"
    assert captured["body"]["model"] == "provider-model"
    assert captured["timeout"] == 120
    assert captured["context"].verify_mode.name == "CERT_REQUIRED"


def test_build_api_provider_requires_explicit_provider_and_model(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.setenv("AI_API_KEY", "test-key")

    with pytest.raises(Exception, match="AI_PROVIDER"):
        ai_analysis.build_api_provider()

    monkeypatch.setenv("AI_PROVIDER", "openai-compatible")
    with pytest.raises(Exception, match="AI_MODEL"):
        ai_analysis.build_api_provider()


def test_build_api_provider_supports_anthropic_and_gemini_response_shapes(monkeypatch):
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    responses = iter([
        {"content": [{"text": '{"provider": "anthropic"}'}]},
        {"candidates": [{"content": {"parts": [{"text": '{"provider": "gemini"}'}]}}]},
    ])

    def fake_urlopen(request, timeout, context):
        requests.append(request)
        return Response(next(responses))

    monkeypatch.setattr(ai_analysis, "urlopen", fake_urlopen)

    anthropic = ai_analysis.build_api_provider(
        provider_name="anthropic",
        api_key="anthropic-key",
        model="claude-sonnet",
    )
    gemini = ai_analysis.build_api_provider(
        provider_name="gemini",
        api_key="gemini-key",
        model="gemini-2.5-pro",
    )

    assert anthropic("Analyze this") == {"provider": "anthropic"}
    assert gemini("Analyze this") == {"provider": "gemini"}
    assert requests[0].full_url == "https://api.anthropic.com/v1/messages"
    assert requests[0].headers["X-api-key"] == "anthropic-key"
    assert requests[1].full_url.startswith(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key="
    )


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


def test_normalize_analysis_response_maps_critical_severity_to_high():
    payload = {
        "conclusion": "feasible",
        "findings": [
            {
                "id": "f-critical",
                "category": "risk",
                "statement": "The change may affect a critical path.",
                "basis": "The supplied source shows a shared execution path.",
                "severity": "critical",
                "evidence": [{"id": "ev-critical", "kind": "assumption"}],
            }
        ],
        "limitations": ["Runtime behavior was not tested."],
        "assumptions": [],
        "estimates": [],
        "suggestions": [],
    }

    result = normalize_analysis_response(payload)

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

    result = normalize_analysis_response(payload)

    assert result.estimates == []
    assert result.limits[-1] == (
        "Estimate 1 was omitted because its label, value, or basis was missing."
    )


def test_normalize_estimates_preserves_valid_entries_and_omits_invalid_entries():
    payload = {
        "conclusion": "conditionally_feasible",
        "findings": [
            {
                "id": "f-estimates",
                "category": "interpretation",
                "statement": "The change is bounded.",
                "basis": "The supplied source shows one affected module.",
                "evidence": [{"id": "ev-estimates", "kind": "assumption"}],
            }
        ],
        "limitations": [],
        "assumptions": [],
        "estimates": [
            {"label": "Effort", "value": "2 days", "basis": "One module."},
            {"label": "Confidence", "value": "medium"},
            {"label": "Risk window", "value": "1 week", "basis": "One integration point."},
        ],
        "suggestions": [],
    }

    result = normalize_analysis_response(payload)

    assert result.estimates == [
        {"label": "Effort", "value": "2 days", "basis": "One module."},
        {"label": "Risk window", "value": "1 week", "basis": "One integration point."},
    ]
    assert result.limits == [
        "Estimate 2 was omitted because its label, value, or basis was missing."
    ]


def test_prompt_declares_empty_estimates_and_omission_behavior():
    prompt = build_analysis_prompt(
        repository_root="/tmp/repo",
        change_description="Update the service",
        scope_summary="one file inspected",
        context="File: src/service.py lines 1-2\nreturn 1",
    )

    assert "estimates: [] is valid" in prompt
    assert "omit only that estimate" in prompt


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


def test_prompt_forbids_evidence_from_truncated_or_excluded_files():
    prompt = build_analysis_prompt(
        repository_root="/tmp/repo",
        change_description="Update the service",
        scope_summary="one file included, one file truncated",
        context="File: src/service.py lines 1-2\nreturn 1",
    )

    assert "Do not cite excluded, truncated, undiscovered, or implied files" in prompt
