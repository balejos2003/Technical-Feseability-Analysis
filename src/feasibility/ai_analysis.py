"""AI analysis provider contracts and validation for feasibility assessment."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable, Mapping
import json
import os
from typing import Any

from .context import SourceContext
from .errors import AIServiceUnavailableError
from .models import (
    AnalysisRequest,
    EvidenceItem,
    EvidenceKind,
    FeasibilityAssessment,
    FeasibilityConclusion,
    Finding,
    FindingCategory,
    Severity,
)


Provider = Callable[[str], Mapping[str, Any]]


def _normalize_enum_value(value: Any) -> Any:
    """Normalize provider enum text while preserving non-string values."""

    return value.strip().lower().replace(" ", "_") if isinstance(value, str) else value


def build_openai_provider(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> Provider:
    """Build the configured OpenAI provider without exposing credentials to prompts."""

    resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not resolved_api_key:
        raise AIServiceUnavailableError(
            "No OpenAI API key is configured. Set OPENAI_API_KEY before starting an analysis."
        )

    resolved_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on environment packaging
        raise AIServiceUnavailableError(
            "The OpenAI dependency is not installed.",
        ) from exc

    client = OpenAI(api_key=resolved_api_key)

    def provider(prompt: str) -> Mapping[str, Any]:
        try:
            response = client.chat.completions.create(
                model=resolved_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only a valid JSON object matching the requested analysis contract.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("The AI provider returned an empty response.")
            payload = json.loads(content)
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise AIServiceUnavailableError("The OpenAI analysis provider is unavailable.") from exc
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("The OpenAI provider returned invalid JSON.") from exc
        except Exception as exc:  # pragma: no cover - provider SDK-specific failures
            error_type = type(exc).__name__
            status_code = getattr(exc, "status_code", None)
            status_text = f" (HTTP {status_code})" if status_code else ""
            raise AIServiceUnavailableError(
                "The OpenAI analysis provider failed "
                f"with {error_type}{status_text}: {exc}. "
                "Check the API key, project billing/credits, model access, and network connection."
            ) from exc

        if not isinstance(payload, Mapping):
            raise TypeError("The OpenAI provider must return a JSON object.")
        return dict(payload)

    return provider


@dataclass(frozen=True)
class AnalysisEvidenceRef:
    """Evidence reference emitted by the analysis provider."""

    id: str
    kind: EvidenceKind | str
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    excerpt: str | None = None
    hash: str | None = None
    description: str = ""

    def to_evidence_item(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=self.id,
            kind=self.kind,
            description=self.description or "Evidence from the analysis context.",
            path=self.path,
            start_line=self.start_line,
            end_line=self.end_line,
            excerpt=self.excerpt,
            file_hash=self.hash,
        )


@dataclass(frozen=True)
class AnalysisEstimate:
    """A labeled estimate or forecast returned by the analysis provider."""

    label: str
    value: str
    basis: str
    uncertainty: str | None = None


@dataclass(frozen=True)
class AnalysisResponse:
    """Normalized AI output for a completed feasibility evaluation."""

    conclusion: FeasibilityConclusion
    findings: list[Finding]
    limits: list[str]
    assumptions: list[str]
    estimates: list[dict[str, str]]
    suggestions: list[str]
    unresolved_questions: list[str] = field(default_factory=list)


def build_analysis_prompt(
    *,
    repository_root: str,
    change_description: str,
    scope_summary: str,
    context: str,
) -> str:
    """Build a bounded prompt aimed at reasoning over supplied source context."""

    return (
        "You are assessing the technical feasibility of a proposed change in a read-only codebase.\n"
        f"Repository root: {repository_root}\n"
        f"Requested change: {change_description}\n"
        f"Scope summary: {scope_summary}\n\n"
        "Analyze only the supplied source context and evidence. Do not modify the repository.\n"
        "Explain your reasoning in plain language, distinguish fact from interpretation, and cite evidence\n"
        "for every material finding.\n\n"
        "Required output contract:\n"
        "- conclusion: feasible | infeasible | conditionally_feasible\n"
        "- findings: list of material findings with category, statement, basis, uncertainty, severity, and evidence\n"
        "- limitations: list of missing, stale, or ambiguous evidence\n"
        "- assumptions: list of explicit assumptions used during assessment\n"
        "- estimates: list of labeled estimates with value, basis, and uncertainty\n"
        "- suggestions: list of actionable suggestions\n"
        "- unresolved_questions: list of open questions\n\n"
        "Evidence rule: every finding must include at least one evidence object.\n"
        "Use only files, line ranges, excerpts, and hashes present in the supplied context.\n"
        "If a claim cannot be supported by the supplied context, do not create a finding;\n"
        "record it as a limitation, assumption, or unresolved question instead.\n"
        "Example finding shape:\n"
        '{"id":"f-1","category":"fact","statement":"...",'
        '"basis":"...","evidence":[{"id":"ev-1","kind":"code",'
        '"path":"src/example.py","start_line":1,"end_line":2,'
        '"excerpt":"...","hash":"<context hash>","description":"..."}]}\n\n'
        "Provided context:\n"
        f"{context}\n"
    )


def invoke_analysis_provider(
    request: AnalysisRequest,
    source_context: SourceContext,
    *,
    provider: Provider,
) -> dict[str, Any]:
    """Build the bounded analysis prompt and invoke the injected AI provider.

    The provider receives only the rendered source snapshot and request metadata.
    Response normalization is intentionally deferred to ``normalize_analysis_response``.
    """

    scope_summary = (
        f"{len(source_context.items)} files included, "
        f"{len(source_context.issues)} discovery issues, "
        f"{source_context.total_chars}/{source_context.max_context_chars} characters"
    )
    prompt = build_analysis_prompt(
        repository_root=request.codebase_root,
        change_description=request.change_description,
        scope_summary=scope_summary,
        context=source_context.as_text(),
    )

    try:
        response = provider(prompt)
    except (ConnectionError, OSError, TimeoutError) as exc:
        raise AIServiceUnavailableError(
            "The AI analysis provider is unavailable",
            provider=type(provider).__name__,
        ) from exc

    if not isinstance(response, Mapping):
        raise TypeError("AI provider must return a mapping response")
    return dict(response)


def _coerce_conclusion(value: Any) -> FeasibilityConclusion:
    try:
        return FeasibilityConclusion(_normalize_enum_value(value))
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Unsupported conclusion: {value}") from exc


def _to_finding(item: dict[str, Any], *, index: int | None = None) -> Finding:
    finding_label = item.get("id") or (f"#{index + 1}" if index is not None else "<unknown>")
    evidence_values = item.get("evidence") or []
    if not isinstance(evidence_values, list) or not evidence_values:
        raise ValueError(
            f"Finding {finding_label} requires at least one evidence item. "
            "The AI response was rejected because every material finding must cite supplied evidence."
        )

    evidence_ids = []
    for evidence in evidence_values:
        if not isinstance(evidence, dict):
            continue
        evidence_id = evidence.get("id")
        if evidence_id:
            evidence_ids.append(str(evidence_id))

    if not evidence_ids:
        raise ValueError(f"Finding {finding_label} requires evidence ids")

    return Finding(
        finding_id=str(item.get("id") or "finding"),
        category=_normalize_enum_value(item.get("category", FindingCategory.INTERPRETATION.value)),
        statement=str(item.get("statement") or ""),
        basis=str(item.get("basis") or ""),
        uncertainty=item.get("uncertainty"),
        severity=_normalize_enum_value(item.get("severity")),
        evidence_ids=evidence_ids,
    )


def _validate_context_evidence(
    findings: list[dict[str, Any]],
    source_context: SourceContext,
) -> None:
    context_by_path = {item.path: item for item in source_context.items}
    for finding in findings:
        for evidence in finding.get("evidence") or []:
            if not isinstance(evidence, dict) or evidence.get("kind") != EvidenceKind.CODE.value:
                continue

            path = str(evidence.get("path") or "")
            context_item = context_by_path.get(path)
            if context_item is None:
                raise ValueError(f"Evidence path is outside the supplied context: {path}")

            start_line = evidence.get("start_line")
            end_line = evidence.get("end_line")
            if start_line is None or end_line is None:
                raise ValueError(f"Evidence range is missing from the supplied context: {path}")
            if start_line < context_item.start_line or end_line > context_item.end_line:
                raise ValueError(f"Evidence range is outside the supplied context: {path}")

            if evidence.get("hash") and evidence["hash"] != context_item.file_hash:
                raise ValueError(f"Evidence hash does not match the supplied context: {path}")


def normalize_analysis_response(
    payload: dict[str, Any],
    *,
    source_context: SourceContext | None = None,
) -> AnalysisResponse:
    """Normalize and validate a provider response structure."""

    if not isinstance(payload, dict):
        raise ValueError("AI response must be a dictionary")

    conclusion = _coerce_conclusion(payload.get("conclusion"))
    findings = payload.get("findings") or []
    if not isinstance(findings, list) or not findings:
        raise ValueError("AI response requires at least one finding")

    normalized_findings = [_to_finding(item, index=index) for index, item in enumerate(findings)]
    if source_context is not None:
        _validate_context_evidence(findings, source_context)

    if "limitations" not in payload:
        raise ValueError("AI response requires limitations")
    limitations = payload.get("limitations") or []
    if not isinstance(limitations, list):
        raise ValueError("limitations must be a list")

    assumptions = payload.get("assumptions") or []
    if not isinstance(assumptions, list):
        raise ValueError("assumptions must be a list")

    estimates = payload.get("estimates") or []
    if not isinstance(estimates, list):
        raise ValueError("estimates must be a list")
    for estimate in estimates:
        if not isinstance(estimate, dict):
            raise ValueError("Each estimate must be a mapping")
        if not estimate.get("label") or not estimate.get("value") or not estimate.get("basis"):
            raise ValueError("Each estimate requires label, value, and basis")

    suggestions = payload.get("suggestions") or []
    if not isinstance(suggestions, list):
        raise ValueError("suggestions must be a list")

    unresolved_questions = payload.get("unresolved_questions") or []
    if not isinstance(unresolved_questions, list):
        raise ValueError("unresolved_questions must be a list")

    return AnalysisResponse(
        conclusion=conclusion,
        findings=normalized_findings,
        limits=list(limitations),
        assumptions=list(assumptions),
        estimates=[dict(estimate) for estimate in estimates],
        suggestions=list(suggestions),
        unresolved_questions=list(unresolved_questions),
    )


__all__ = [
    "AnalysisEstimate",
    "AnalysisEvidenceRef",
    "AnalysisResponse",
    "build_analysis_prompt",
    "build_openai_provider",
    "invoke_analysis_provider",
    "normalize_analysis_response",
]
