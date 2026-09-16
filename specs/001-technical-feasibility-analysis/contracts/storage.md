# History Storage Contract

SQLite is an internal persistence contract for completed assessments and is not a
public service interface. All queries are scoped by `principal_id`.

Minimum records:

- `analysis_requests`: request identity, principal, repository scope, change text,
  scope rules, and creation time.
- `assessments`: assessment identity, request identity, principal, conclusion,
  evaluated scope, rendered report, analyzer version, and completion time.
- `evidence_items`: assessment identity, kind, relative path, line range, excerpt,
  file hash, and relevance description.
- `findings`: assessment identity, category, severity, statement, basis, uncertainty.
- `finding_evidence`: association between findings and evidence items.

Required invariants:

- Completed assessments are immutable snapshots for history consultation.
- `principal_id` is required on every assessment query and must match the stored owner.
- A show operation for another principal returns not-found semantics.
- The database location is outside the analyzed root by default.
- Schema or analyzer version is stored to explain historical differences.
