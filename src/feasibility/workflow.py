"""Request preparation and end-to-end assessment workflow."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .ai_analysis import invoke_analysis_provider, normalize_analysis_response
from .config import application_paths
from .context import SourceContext, prepare_source_context
from .discovery import DiscoveryResult, discover_repository
from .errors import AIServiceUnavailableError
from .models import (
    AnalysisRequest,
    EvidenceItem,
    EvidenceKind,
    FeasibilityAssessment,
    Finding,
    FindingCategory,
    ScopeRules,
)
from .reports import render_report
from .storage import save_analysis_record


@dataclass(frozen=True)
class AnalysisContext:
    """Validated request inputs and the read-only discovery result."""

    request: AnalysisRequest
    discovery: DiscoveryResult
    additional_context: str
    save_report: bool


def prepare_analysis_context(
    request_input: Mapping[str, str | bool],
    *,
    principal_id: str,
    request_id: str | None = None,
    scope_rules: ScopeRules | Mapping[str, object] | None = None,
) -> AnalysisContext:
    """Create an analysis request and discover its bounded source scope."""

    codebase_root = Path(str(request_input.get("codebase_path", ""))).expanduser().resolve()
    normalized_scope = ScopeRules.from_mapping(scope_rules)
    request = AnalysisRequest(
        request_id=request_id or str(uuid4()),
        principal_id=principal_id,
        codebase_root=str(codebase_root),
        change_description=str(request_input.get("requested_change", "")),
        scope_rules=normalized_scope,
    )
    discovery = discover_repository(codebase_root, normalized_scope)

    return AnalysisContext(
        request=request,
        discovery=discovery,
        additional_context=str(request_input.get("additional_context", "")),
        save_report=bool(request_input.get("save_report", False)),
    )


def _build_prompt_request(request: AnalysisRequest, additional_context: str) -> AnalysisRequest:
    if not additional_context or not additional_context.strip():
        return request

    combined_change = f"{request.change_description.strip()}\n\nAdditional context:\n{additional_context.strip()}"
    return AnalysisRequest(
        request_id=request.request_id,
        principal_id=request.principal_id,
        codebase_root=request.codebase_root,
        change_description=combined_change,
        scope_rules=request.scope_rules,
        created_at=request.created_at,
    )


def _evidence_items_from_payload(
    payload: Mapping[str, Any],
    *,
    source_context: SourceContext,
) -> tuple[list[EvidenceItem], dict[str, EvidenceItem]]:
    evidence_items: list[EvidenceItem] = []
    evidence_index: dict[str, EvidenceItem] = {}
    context_by_path = {item.path: item for item in source_context.items}

    for finding in payload.get("findings") or []:
        if not isinstance(finding, Mapping):
            continue
        for evidence in finding.get("evidence") or []:
            if not isinstance(evidence, Mapping):
                continue

            evidence_id = str(evidence.get("id") or "")
            if not evidence_id:
                continue
            if evidence_id in evidence_index:
                continue

            kind_value = str(evidence.get("kind") or EvidenceKind.CODE.value)
            try:
                kind = EvidenceKind(kind_value)
            except ValueError:
                kind = EvidenceKind.USER_CONTEXT

            path_value = evidence.get("path")
            start_line = evidence.get("start_line")
            end_line = evidence.get("end_line")
            hash_value = evidence.get("hash")
            if kind == EvidenceKind.CODE:
                if hash_value is None and isinstance(path_value, str):
                    context_item = context_by_path.get(path_value)
                    if context_item is not None:
                        hash_value = context_item.file_hash
                if start_line is None and isinstance(path_value, str):
                    context_item = context_by_path.get(path_value)
                    if context_item is not None:
                        start_line = context_item.start_line
                        end_line = context_item.end_line

            evidence_item = EvidenceItem(
                evidence_id=evidence_id,
                kind=kind,
                description=str(evidence.get("description") or "Evidence for the material finding."),
                path=str(path_value) if path_value is not None else None,
                start_line=int(start_line) if start_line is not None else None,
                end_line=int(end_line) if end_line is not None else None,
                excerpt=str(evidence.get("excerpt") or "") if evidence.get("excerpt") is not None else None,
                file_hash=str(hash_value) if hash_value is not None else None,
            )
            evidence_index[evidence_id] = evidence_item
            evidence_items.append(evidence_item)

    for assumption in payload.get("assumptions") or []:
        if not isinstance(assumption, str):
            continue
        assumption_id = f"assumption-{len(evidence_items) + 1}"
        evidence_item = EvidenceItem(
            evidence_id=assumption_id,
            kind=EvidenceKind.ASSUMPTION,
            description=assumption,
        )
        evidence_index[assumption_id] = evidence_item
        evidence_items.append(evidence_item)

    for limitation in payload.get("limitations") or []:
        if not isinstance(limitation, str):
            continue
        limitation_id = f"limitation-{len(evidence_items) + 1}"
        evidence_item = EvidenceItem(
            evidence_id=limitation_id,
            kind=EvidenceKind.LIMITATION,
            description=limitation,
        )
        evidence_index[limitation_id] = evidence_item
        evidence_items.append(evidence_item)

    return evidence_items, evidence_index


def run_analysis_workflow(
    request_input: Mapping[str, str | bool],
    *,
    principal_id: str,
    request_id: str | None = None,
    provider: Callable[[str], Mapping[str, Any]] | None = None,
    scope_rules: ScopeRules | Mapping[str, object] | None = None,
) -> FeasibilityAssessment:
    """Execute the complete read-only analysis workflow for one request."""

    context = prepare_analysis_context(
        request_input,
        principal_id=principal_id,
        request_id=request_id,
        scope_rules=scope_rules,
    )
    source_context = prepare_source_context(
        context.request.codebase_root,
        context.discovery,
        scope_rules=context.request.scope_rules,
    )

    payload_provider = provider or (lambda _prompt: (_ for _ in ()).throw(AIServiceUnavailableError("No AI provider configured.")))
    prompt_request = _build_prompt_request(context.request, context.additional_context)
    raw_response = invoke_analysis_provider(prompt_request, source_context, provider=payload_provider)
    normalized = normalize_analysis_response(raw_response, source_context=source_context)

    evidence_items, _ = _evidence_items_from_payload(raw_response, source_context=source_context)
    assessment = FeasibilityAssessment(
        assessment_id=request_id or str(uuid4()),
        request_id=context.request.request_id,
        principal_id=context.request.principal_id,
        conclusion=normalized.conclusion,
        evaluated_scope=[item.relative_path for item in context.discovery.files],
        findings=list(normalized.findings),
        limitations=list(normalized.limits),
        report_markdown="placeholder",
        analyzer_version="technical-feasibility-analysis/0.1.0",
        evidence_items=evidence_items,
        assumptions=list(normalized.assumptions),
        estimates=[dict(estimate) for estimate in normalized.estimates],
        suggestions=list(normalized.suggestions),
        unresolved_questions=list(normalized.unresolved_questions),
    )
    rendered_report = render_report(assessment)
    object.__setattr__(assessment, "report_markdown", rendered_report)

    save_analysis_record(context.request, assessment, database_path=application_paths().database_path)

    if context.save_report:
        report_dir = application_paths().reports_dir
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{assessment.assessment_id}.md"
        report_path.write_text(rendered_report, encoding="utf-8")

    return assessment


__all__ = [
    "AnalysisContext",
    "prepare_analysis_context",
    "run_analysis_workflow",
]