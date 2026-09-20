"""Request preparation and bounded discovery workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from .discovery import DiscoveryResult, discover_repository
from .models import AnalysisRequest, ScopeRules


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


__all__ = ["AnalysisContext", "prepare_analysis_context"]