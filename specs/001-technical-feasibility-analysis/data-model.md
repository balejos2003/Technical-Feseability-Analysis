# Data Model: Technical Feasibility Analysis

## AnalysisRequest

Represents one Developer request for an assessment.

- `request_id`: stable identifier.
- `principal_id`: owner used to restrict history access.
- `codebase_root`: normalized input root recorded for traceability.
- `change_description`: natural-language, technical, or mixed requested change.
- `scope_rules`: exclusions and file-size limits used for discovery.
- `created_at`: request creation timestamp.

Validation: the codebase root must be readable; the change description must be
non-empty; scope rules must be explicit in the stored request.

## EvidenceItem

Represents an observation or qualification used by a finding.

- `evidence_id`: stable identifier within an assessment.
- `kind`: `code`, `user_context`, `assumption`, `limitation`, or `conflict`.
- `path`: normalized path relative to the analyzed root when applicable.
- `start_line`, `end_line`: inclusive source range when applicable.
- `excerpt`: bounded source text for the cited range.
- `file_hash`: content hash captured during analysis when a file is cited.
- `description`: human-readable explanation of relevance.

Validation: code evidence requires a path, valid positive line range, excerpt, and
hash; non-code evidence must explain why a source span is unavailable.

## Finding

A material conclusion component linked to one or more evidence items.

- `finding_id`: stable identifier.
- `category`: `fact`, `interpretation`, `risk`, `estimate`, `suggestion`, or
  `unresolved_question`.
- `severity`: optional `low`, `medium`, or `high` impact.
- `statement`: readable finding text.
- `basis`: reasoning or calculation basis.
- `uncertainty`: uncertainty statement for estimates and interpretations.
- `evidence_ids`: supporting or qualifying evidence references.

Validation: every material finding requires at least one evidence reference or an
explicit limitation/assumption evidence item.

## FeasibilityAssessment

The complete stored result and rendered report source.

- `assessment_id`: stable identifier.
- `request_id`: associated request.
- `principal_id`: authorized reader identity.
- `conclusion`: `feasible`, `infeasible`, or `conditionally_feasible`.
- `evaluated_scope`: files and rules actually inspected.
- `findings`: ordered findings with evidence links.
- `limitations`: known missing, stale, ambiguous, or conflicting evidence.
- `report_markdown`: rendered Developer-facing report.
- `analyzer_version`: schema and analysis-provider version for reproducibility.
- `created_at`: completion timestamp.

State transitions: `received -> analyzing -> completed` or `received -> analyzing ->
failed`. Only `completed` assessments enter the queryable history; failed analyses
retain an error record only when the CLI is configured to do so.

## AnalysisHistory

An authorized view over completed assessments.

- Search indexes request description, conclusion, and evaluated scope.
- List results include assessment ID, date, short request summary, and conclusion.
- Show results return the original structured assessment and Markdown report.
- Every query requires the current `principal_id`; no cross-principal result is returned.
