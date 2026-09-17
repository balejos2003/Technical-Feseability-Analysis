"""Shared data models for the technical feasibility analysis workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable


class EvidenceKind(str, Enum):
    """Type of evidence used to justify a material finding."""

    CODE = "code"
    USER_CONTEXT = "user_context"
    ASSUMPTION = "assumption"
    LIMITATION = "limitation"
    CONFLICT = "conflict"


class FindingCategory(str, Enum):
    """Category for a material conclusion or observation."""

    FACT = "fact"
    INTERPRETATION = "interpretation"
    RISK = "risk"
    ESTIMATE = "estimate"
    SUGGESTION = "suggestion"
    UNRESOLVED_QUESTION = "unresolved_question"


class Severity(str, Enum):
    """Impact level for findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FeasibilityConclusion(str, Enum):
    """Overall conclusion for a completed feasibility assessment."""

    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    CONDITIONALLY_FEASIBLE = "conditionally_feasible"


class AssessmentStatus(str, Enum):
    """Lifecycle status for an analysis assessment."""

    RECEIVED = "received"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ScopeRules:
    """Explicit discovery and read-only constraints used in a request."""

    excluded_dirs: tuple[str, ...] = (
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
    )
    excluded_files: tuple[str, ...] = ()
    max_file_size_bytes: int = 1_000_000
    follow_symlinks: bool = False
    allowed_extensions: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Any | None) -> "ScopeRules":
        """Normalize mappings or already-typed scope rules."""

        if isinstance(value, cls):
            return value
        if value is None:
            return cls()
        if isinstance(value, dict):
            return cls(
                excluded_dirs=tuple(value.get("excluded_dirs", cls().excluded_dirs)),
                excluded_files=tuple(value.get("excluded_files", cls().excluded_files)),
                max_file_size_bytes=int(value.get("max_file_size_bytes", cls().max_file_size_bytes)),
                follow_symlinks=bool(value.get("follow_symlinks", cls().follow_symlinks)),
                allowed_extensions=tuple(value.get("allowed_extensions", cls().allowed_extensions)),
            )
        raise TypeError("scope_rules must be a ScopeRules instance or mapping")


@dataclass(frozen=True)
class AnalysisRequest:
    """One developer request for a technical feasibility assessment."""

    request_id: str
    principal_id: str
    codebase_root: str
    change_description: str
    scope_rules: ScopeRules = field(default_factory=ScopeRules)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope_rules", ScopeRules.from_mapping(self.scope_rules))
        if not self.request_id or not self.request_id.strip():
            raise ValueError("request_id must be non-empty")
        if not self.principal_id or not self.principal_id.strip():
            raise ValueError("principal_id must be non-empty")
        if not self.codebase_root or not self.codebase_root.strip():
            raise ValueError("codebase_root must be non-empty")
        if not self.change_description or not self.change_description.strip():
            raise ValueError("change_description must be non-empty")
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))


@dataclass(frozen=True)
class EvidenceItem:
    """Source-backed evidence supporting or qualifying a finding."""

    evidence_id: str
    kind: EvidenceKind | str
    description: str
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    excerpt: str | None = None
    file_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.evidence_id.strip():
            raise ValueError("evidence_id must be non-empty")
        if not self.description or not self.description.strip():
            raise ValueError("description must be non-empty")
        object.__setattr__(self, "kind", EvidenceKind(self.kind))

        if self.kind == EvidenceKind.CODE:
            if not self.path or not self.path.strip():
                raise ValueError("code evidence requires a path")
            if self.start_line is None or self.end_line is None:
                raise ValueError("code evidence requires both start_line and end_line")
            if self.start_line <= 0 or self.end_line <= 0:
                raise ValueError("code evidence line numbers must be positive")
            if self.start_line > self.end_line:
                raise ValueError("start_line cannot be larger than end_line")
            if not self.excerpt or not self.excerpt.strip():
                raise ValueError("code evidence requires an excerpt")
            if not self.file_hash or not self.file_hash.strip():
                raise ValueError("code evidence requires a file hash")
        else:
            if self.path is not None and not self.path.strip():
                object.__setattr__(self, "path", None)


@dataclass(frozen=True)
class Finding:
    """A material conclusion linked to one or more evidence items."""

    finding_id: str
    category: FindingCategory | str
    statement: str
    basis: str
    uncertainty: str | None = None
    severity: Severity | str | None = None
    evidence_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.finding_id or not self.finding_id.strip():
            raise ValueError("finding_id must be non-empty")
        if not self.statement or not self.statement.strip():
            raise ValueError("statement must be non-empty")
        if not self.basis or not self.basis.strip():
            raise ValueError("basis must be non-empty")
        object.__setattr__(self, "category", FindingCategory(self.category))
        if self.severity is not None:
            object.__setattr__(self, "severity", Severity(self.severity))
        if not self.evidence_ids:
            raise ValueError("material findings require at least one evidence reference")
        if any(not evidence_id or not evidence_id.strip() for evidence_id in self.evidence_ids):
            raise ValueError("evidence_ids may not contain blank values")


@dataclass(frozen=True)
class FeasibilityAssessment:
    """Stored assessment that can be rendered into a developer-facing report."""

    assessment_id: str
    request_id: str
    principal_id: str
    conclusion: FeasibilityConclusion | str
    evaluated_scope: list[str]
    findings: list[Finding]
    limitations: list[str]
    report_markdown: str
    analyzer_version: str
    created_at: datetime = field(default_factory=utc_now)
    status: AssessmentStatus = AssessmentStatus.COMPLETED

    def __post_init__(self) -> None:
        if not self.assessment_id or not self.assessment_id.strip():
            raise ValueError("assessment_id must be non-empty")
        if not self.request_id or not self.request_id.strip():
            raise ValueError("request_id must be non-empty")
        if not self.principal_id or not self.principal_id.strip():
            raise ValueError("principal_id must be non-empty")
        object.__setattr__(self, "conclusion", FeasibilityConclusion(self.conclusion))
        object.__setattr__(self, "status", AssessmentStatus(self.status))
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))
        if not self.report_markdown or not self.report_markdown.strip():
            raise ValueError("report_markdown must be non-empty")
        if not self.evaluated_scope:
            raise ValueError("evaluated_scope must include inspected paths or rules")
        if self.status == AssessmentStatus.COMPLETED and not self.findings:
            raise ValueError("completed assessments require at least one finding")


@dataclass(frozen=True)
class HistoryListEntry:
    """Authorized summary record used for listing prior analyses."""

    assessment_id: str
    principal_id: str
    created_at: datetime
    summary: str
    conclusion: FeasibilityConclusion | str

    def __post_init__(self) -> None:
        if not self.assessment_id or not self.assessment_id.strip():
            raise ValueError("assessment_id must be non-empty")
        if not self.principal_id or not self.principal_id.strip():
            raise ValueError("principal_id must be non-empty")
        if not self.summary or not self.summary.strip():
            raise ValueError("summary must be non-empty")
        object.__setattr__(self, "conclusion", FeasibilityConclusion(self.conclusion))
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))


@dataclass(frozen=True)
class HistoryDetail:
    """Immutable structured record returned when a user opens a historical result."""

    assessment: FeasibilityAssessment
    markdown_report: str

    def __post_init__(self) -> None:
        if not self.markdown_report or not self.markdown_report.strip():
            raise ValueError("markdown_report must be non-empty")


__all__ = [
    "AnalysisRequest",
    "AssessmentStatus",
    "EvidenceItem",
    "EvidenceKind",
    "FeasibilityAssessment",
    "FeasibilityConclusion",
    "Finding",
    "FindingCategory",
    "HistoryDetail",
    "HistoryListEntry",
    "ScopeRules",
    "Severity",
    "utc_now",
]
