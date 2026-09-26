# Quickstart Validation Guide

## Prerequisites

- Python 3.11 or newer.
- Project dependencies installed from the eventual project dependency manifest.
- A fixture repository containing at least three supported language files, one syntax
  error, one unsupported-language file, and one excluded directory.

The scenarios below use `python -m feasibility` as the planned entry point. The
program is interactive: all inputs are collected with `input()`, without arguments or
flags.

## Scenario 1: Analyze without modifying the codebase

```bash
PYTHONPATH=src python -m feasibility
```

Answer the prompts with:

```text
1. Analyze a change
Codebase path: ./fixtures/mixed-repo
Requested change: Add a caching layer to the data access path
Optional additional context: <blank>
Save report outside the codebase? yes
```

Expected outcomes:

- The command returns a `feasible`, `infeasible`, or `conditionally_feasible` result.
- The Markdown report contains scope, assumptions, limitations, findings, estimates,
  suggestions, and unresolved questions.
- Each material finding contains a relative file path, inclusive line range, excerpt,
  and file hash, or an explicit non-code limitation.
- The fixture repository has no changed source files, metadata, temporary files, or
  generated cache entries.

## Scenario 2: Store and retrieve history

```bash
PYTHONPATH=src python -m feasibility
```

Choose `2. Consult analysis history`, then select one of the history actions:

```text
1. List recent analyses
2. Search analyses
3. Open an analysis by identifier
4. Return to main menu
```

Expected outcomes:

- Completed assessments appear in `history list` with date, summary, and conclusion.
- Search returns matching assessments and excludes unrelated assessments.
- `history show` reproduces the original request, scope, evidence, conclusion, and
  Markdown report.
- A second test principal cannot list, search, or show the first principal's records.

## Scenario 3: Unsupported and incomplete evidence

```bash
PYTHONPATH=src python -m feasibility
```

Choose `1. Analyze a change` and provide `./fixtures/unsupported-repo` plus
`Replace the parser with a new implementation` when prompted.

Expected outcomes:

- Unsupported files are identified as limitations rather than silently ignored.
- Missing or conflicting evidence is visible in the report.
- The result does not make an unconditional feasibility claim when material evidence
  is unavailable.

## Scenario 4: Read-only and performance checks

Run the analysis against a fixture with a known file count and total size, record the
elapsed time, and compare the repository snapshot before and after. Repeat with a
read-only-mounted fixture where the platform permits it.

Acceptance thresholds:

- No source, metadata, cache, or temporary-file changes under the analyzed root.
- A small fixture starts within 2 seconds.
- The defined complete-request fixture meets the 5-minute target in at least 90% of
  repeated runs.
- History lookup completes within 2 seconds for a seeded set of 10,000 assessments.

## Execution Record

Validated on 2026-09-26 from the repository root with Python 3.11+ and the project
virtual environment:

- **Scenario 1**: prompts, fixture discovery, and safe provider failure passed. The
  complete assessment could not run because `OPENAI_API_KEY` was intentionally absent
  from the validation environment. The application reported the missing provider and
  did not create an incomplete assessment.
- **Scenario 2**: the interactive history menu passed list, search, open, return, and
  unavailable-record behavior. Seeded history tests also confirmed original report
  retrieval and principal isolation. The empty-history prompt says `No analyses found
  for this principal.` as expected for a new database.
- **Scenario 3**: `tests/fixtures/unsupported-repo` with `allowed_extensions=("py",)`
  discovered `src/parser.py` and reported `README.md` and
  `vendor/foreign-language.xyz` as `out_of_scope`. A binary NUL-byte case remains
  covered by the discovery tests because the fixture is kept text-only.
- **Scenario 4**: discovery and bounded context preparation completed without changing
  any fixture file; the mixed fixture contained 7 discovered files and a 1,260-character
  context. The 2-second startup, 5-minute completion, and 10,000-record lookup targets
  were not benchmarked in this run and remain open for T040.

The quickstart examples use `tests/fixtures/mixed-repo` and
`tests/fixtures/unsupported-repo` in this repository. A real AI-backed run additionally
requires `OPENAI_API_KEY` and may set `OPENAI_MODEL`.
