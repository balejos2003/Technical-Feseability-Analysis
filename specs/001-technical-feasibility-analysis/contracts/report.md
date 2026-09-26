# Report Contract

The report is Markdown with stable headings so a Developer can navigate it in a
terminal or editor and locate evidence for each material claim.

```text
# Technical Feasibility Assessment
## Request
## Conclusion
## Evaluated Scope
## Findings
### Finding <id>: <category>
#### Evidence
## Estimates
## Suggestions
## Risks and Limitations
## Assumptions
## Unresolved Questions
## Developer Review
```

Each finding's Evidence subsection MUST include one or more references in this form:

```text
- Evidence: <relative/path> lines <start>-<end> (sha256:<hash>)
  <bounded source excerpt>
  Relevance: <why this evidence supports or qualifies the finding>
```

For non-code evidence, the reference MUST identify the source as `user_context`,
`assumption`, `limitation`, or `conflict` and explain why no source span exists.

The Conclusion section MUST use exactly one of `Feasible`, `Infeasible`, or
`Conditionally feasible`. Estimates and suggestions MUST be labeled and MUST include
basis and uncertainty when available. An incomplete estimate MUST be omitted and the
omission MUST be recorded as a limitation; an empty estimates section is valid. The
Developer Review section MUST state that the result is advisory and that no codebase
change was applied by the analysis.
