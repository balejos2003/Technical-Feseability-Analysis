# Research: Technical Feasibility Analysis

## Decision: Let the AI interpret source structure directly

**Rationale**: The requested workflow prioritizes broad language coverage and simple
maintenance over deterministic syntax parsing. The system will discover files, read
bounded source context, and provide paths, line ranges, excerpts, and hashes to the AI.
The AI will infer modules, dependencies, control flow, and likely impact from the
material it receives. The analysis provider remains behind an interface so the
interpretation mechanism can evolve without changing history or report contracts.

**Alternatives considered**: Tree-sitter and language-specific parsers would provide
more deterministic syntax structure but add grammar dependencies and maintenance for
each supported language. Regular expressions would be cheaper but too fragile as the
primary structural representation. Language servers could provide richer semantics but
would introduce environment and process dependencies outside the desired simple v1.

## Decision: Use an interactive Python script and SQLite storage

**Rationale**: `input()` keeps the interaction understandable for a Developer who
does not need to learn argument or flag syntax. A guided menu is sufficient for the
small local workflow and is easy to maintain. `sqlite3` is sufficient for durable
history, structured filtering, and reopening reports without introducing a database
service. The database must live in an application data location, never inside the
analyzed repository by default.

**Alternatives considered**: Argument parsing is efficient for automation but adds
syntax and validation surface that the requested v1 explicitly excludes. A web
interface adds deployment and authentication scope. A JSON-file history is easy to
start with but makes filtering, access isolation, and schema evolution less reliable.
A server database is unnecessary for the single-user local v1 target.

## Decision: Render Markdown reports with structured evidence records

**Rationale**: Markdown is readable in terminals and editors, can be saved as text, and
supports headings and navigable sections. Every finding will reference a normalized
relative path, inclusive line range, source excerpt, evidence type, and file hash. The
structured representation remains the source for both rendering and history storage.

**Alternatives considered**: Plain prose alone is easier to render but weakens
navigation and consistent evidence placement. HTML introduces a presentation runtime
not required by the CLI. Raw JSON is useful for automation but is not the primary
Developer-facing report.

## Decision: Identify local history access with a principal identifier

**Rationale**: SQLite does not provide application-level authorization. Each stored
assessment records a `principal_id`, and every list, search, and show operation filters
by the current principal. The CLI may default to the local OS user identity while
allowing an explicit principal for deterministic tests.

**Alternatives considered**: Trusting every local process would make tests and future
shared storage unsafe. A full account system is outside the local CLI scope.

## Decision: Enforce bounded read-only discovery

**Rationale**: Discovery uses explicit exclusions, file-size limits, symlink policy, and
bounded file counts. The analyzer writes only to its configured report/database output
locations and verifies that those locations are outside the analyzed root unless the
Developer explicitly chooses otherwise.

**Alternatives considered**: Unbounded recursive scanning is simpler but makes the
five-minute outcome and resource use unverifiable. Copying the repository first adds
storage and does not eliminate the need for read-only checks.

## Validation questions resolved

- Supported languages are adapter-driven; the initial package should ship a documented
  baseline of readable text files and report unreadable, binary, or out-of-scope files
  explicitly.
- The primary analysis provider remains an interface boundary, because the feature
  requirements define the report behavior but not a specific local or remote model.
- Performance validation uses a named fixture profile in the quickstart rather than an
  undefined repository size.
