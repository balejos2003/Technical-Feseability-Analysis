"""Request preparation and end-to-end assessment workflow."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .ai_analysis import invoke_analysis_provider, normalize_analysis_response
from .config import application_paths, validate_application_paths_outside_repository
from .context import SourceContext, prepare_source_context
from .discovery import DiscoveryResult, discover_repository
from .evidence import validate_assessment_traceability
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

            kind_value = str(evidence.get("kind") or EvidenceKind.CODE.value).strip().lower().replace(" ", "_")
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


def _namespace_assessment_records(
    assessment_id: str,
    findings: list[Finding],
    evidence_items: list[EvidenceItem],
) -> tuple[list[Finding], list[EvidenceItem]]:
    """Give persisted child records identifiers unique to their assessment."""

    evidence_ids = {
        item.evidence_id: f"{assessment_id}:{item.evidence_id}" for item in evidence_items
    }
    namespaced_evidence = [
        EvidenceItem(
            evidence_id=evidence_ids[item.evidence_id],
            kind=item.kind,
            description=item.description,
            path=item.path,
            start_line=item.start_line,
            end_line=item.end_line,
            excerpt=item.excerpt,
            file_hash=item.file_hash,
        )
        for item in evidence_items
    ]
    namespaced_findings = [
        Finding(
            finding_id=f"{assessment_id}:{finding.finding_id}",
            category=finding.category,
            statement=finding.statement,
            basis=finding.basis,
            uncertainty=finding.uncertainty,
            severity=finding.severity,
            evidence_ids=[evidence_ids[evidence_id] for evidence_id in finding.evidence_ids],
        )
        for finding in findings
    ]
    return namespaced_findings, namespaced_evidence


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
    validate_application_paths_outside_repository(context.request.codebase_root)
    source_context = prepare_source_context(
        context.request.codebase_root,
        context.discovery,
        scope_rules=context.request.scope_rules,
    )

    payload_provider = provider or (lambda _prompt: (_ for _ in ()).throw(AIServiceUnavailableError("No AI provider configured.")))
    prompt_request = _build_prompt_request(context.request, context.additional_context)
    raw_response = invoke_analysis_provider(prompt_request, source_context, provider=payload_provider)
    try:
        normalized = normalize_analysis_response(raw_response, source_context=source_context)
    except ValueError as exc:
        error_message = str(exc)
        recoverable_evidence_error = any(
            marker in error_message
            for marker in (
                "requires at least one evidence item",
                "outside the supplied context",
                "range is missing from the supplied context",
                "range is outside the supplied context",
                "hash does not match the supplied context",
            )
        )
        if not recoverable_evidence_error:
            raise

        correction = (
            "\n\nCORRECTION REQUIRED: Your previous response cited evidence that was missing, "
            "outside, truncated, or inconsistent with the supplied context. Return the complete "
            "JSON response again. Every finding must include evidence from an exact File entry "
            "in the supplied context, with an inclusive line range, excerpt, and matching hash. "
            "If evidence is unavailable, omit that finding and put the issue in limitations or "
            "unresolved_questions. Do not cite excluded, truncated, undiscovered, or implied files.\n"
        )
        raw_response = invoke_analysis_provider(
            prompt_request,
            source_context,
            provider=lambda prompt: payload_provider(prompt + correction),
        )
        normalized = normalize_analysis_response(raw_response, source_context=source_context)

    assessment_id = request_id or str(uuid4())
    evidence_items, _ = _evidence_items_from_payload(raw_response, source_context=source_context)
    namespaced_findings, namespaced_evidence = _namespace_assessment_records(
        assessment_id,
        normalized.findings,
        evidence_items,
    )
    assessment = FeasibilityAssessment(
        assessment_id=assessment_id,
        request_id=context.request.request_id,
        principal_id=context.request.principal_id,
        conclusion=normalized.conclusion,
        evaluated_scope=[item.relative_path for item in context.discovery.files],
        findings=namespaced_findings,
        limitations=list(normalized.limits),
        report_markdown="placeholder",
        analyzer_version="technical-feasibility-analysis/0.1.0",
        evidence_items=namespaced_evidence,
        assumptions=list(normalized.assumptions),
        estimates=[dict(estimate) for estimate in normalized.estimates],
        suggestions=list(normalized.suggestions),
        unresolved_questions=list(normalized.unresolved_questions),
    )
    validate_assessment_traceability(assessment)
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