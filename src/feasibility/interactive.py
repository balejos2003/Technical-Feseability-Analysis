"""Interactive terminal session for the feasibility analysis application."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .ai_analysis import Provider, build_openai_provider
from .config import application_paths, ensure_output_outside_repository, resolve_principal_id
from .errors import FeasibilityError
from .history import get_history_detail, list_history, search_history
from .models import FeasibilityAssessment
from .workflow import prepare_analysis_context, run_analysis_workflow


InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], Any]
ActionFunction = Callable[[], Any]

_HISTORY_UNAVAILABLE_MESSAGE = "Analysis unavailable."

AnalysisInput = dict[str, str | bool]

_MENU_OPTIONS = (
    "1. Analyze a change",
    "2. Consult analysis history",
    "3. Exit",
)


def _prompt_codebase_path(
    input_fn: InputFunction,
    output_fn: OutputFunction,
) -> str:
    while True:
        codebase_path = input_fn("Codebase path: ").strip()
        path = Path(codebase_path).expanduser()
        if codebase_path and path.is_dir():
            return codebase_path
        if codebase_path and path.is_file():
            output_fn("Codebase path must be a directory, not a file. Please try again.")
        else:
            output_fn("Codebase path is unavailable. Please try again.")


def _prompt_required_change(
    input_fn: InputFunction,
    output_fn: OutputFunction,
) -> str:
    while True:
        requested_change = input_fn("Requested change: ").strip()
        if requested_change:
            return requested_change
        output_fn("Requested change cannot be blank. Please try again.")


def _prompt_save_preference(
    input_fn: InputFunction,
    output_fn: OutputFunction,
) -> bool:
    while True:
        save_answer = input_fn("Save report outside the codebase? ").strip().lower()
        if save_answer in {"yes", "y", "sim", "s"}:
            return True
        if save_answer in {"no", "n", "nao", "não"}:
            return False
        output_fn("Please answer yes or no.")


def _prompt_review_acknowledgment(
    input_fn: InputFunction,
    output_fn: OutputFunction,
) -> bool:
    while True:
        review_answer = input_fn("Have you reviewed this assessment and acknowledged it is advisory? ").strip().lower()
        if review_answer in {"yes", "y", "sim", "s"}:
            return True
        if review_answer in {"no", "n", "nao", "não"}:
            return False
        output_fn("Please answer yes or no.")


def _prompt_result_retention(
    input_fn: InputFunction,
    output_fn: OutputFunction,
) -> bool:
    while True:
        retain_answer = input_fn("Do you want to retain this result for future reference? ").strip().lower()
        if retain_answer in {"yes", "y", "sim", "s"}:
            return True
        if retain_answer in {"no", "n", "nao", "não"}:
            return False
        output_fn("Please answer yes or no.")


def prompt_analysis_request(
    *,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
) -> AnalysisInput:
    """Collect the inputs needed to start one analysis request."""

    codebase_path = _prompt_codebase_path(input_fn, output_fn)
    requested_change = _prompt_required_change(input_fn, output_fn)
    additional_context = input_fn("Optional additional context: ").strip()

    return {
        "codebase_path": codebase_path,
        "requested_change": requested_change,
        "additional_context": additional_context,
        "save_report": _prompt_save_preference(input_fn, output_fn),
    }


def prepare_interactive_analysis(
    *,
    principal_id: str | None = None,
    request_id: str | None = None,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
    scope_rules: Any = None,
    request_input: AnalysisInput | None = None,
) -> Any:
    """Collect analysis inputs and prepare their read-only discovery context."""

    request_input = request_input or prompt_analysis_request(input_fn=input_fn, output_fn=output_fn)
    effective_principal = resolve_principal_id(principal_id)
    return prepare_analysis_context(
        request_input,
        principal_id=effective_principal,
        request_id=request_id,
        scope_rules=scope_rules,
    )


def display_report(
    assessment: FeasibilityAssessment,
    *,
    output_fn: OutputFunction = print,
) -> None:
    """Display the complete developer-facing Markdown report."""

    output_fn(assessment.report_markdown)


def save_external_report(
    assessment: FeasibilityAssessment,
    *,
    repository_root: str | Path,
    reports_dir: str | Path | None = None,
) -> Path:
    """Write a report copy to an application directory outside the codebase."""

    destination_dir = Path(reports_dir).expanduser().resolve() if reports_dir else application_paths().reports_dir
    destination = ensure_output_outside_repository(
        destination_dir / f"{assessment.assessment_id}.md",
        repository_root,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(assessment.report_markdown, encoding="utf-8")
    return destination


def run_analysis_interaction(
    *,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
    principal_id: str | None = None,
    assessment: FeasibilityAssessment | None = None,
    provider: Provider | None = None,
) -> FeasibilityAssessment | None:
    """Run one interactive analysis and display its completed report."""

    effective_principal = resolve_principal_id(principal_id)
    request_input = prompt_analysis_request(input_fn=input_fn, output_fn=output_fn)

    context = prepare_interactive_analysis(
        principal_id=effective_principal,
        input_fn=input_fn,
        output_fn=output_fn,
        request_input=request_input,
    )
    output_fn("Analysis request prepared.")
    output_fn(f"Discovered files: {len(context.discovery.files)}")
    output_fn(f"Discovery issues: {len(context.discovery.issues)}")
    try:
        completed_assessment = assessment or run_analysis_workflow(
            request_input,
            principal_id=effective_principal,
            provider=provider or build_openai_provider(),
        )
    except FeasibilityError as exc:
        output_fn(f"Analysis failed: {exc.message}")
        return None
    except (TypeError, ValueError) as exc:
        output_fn(f"Analysis failed: {exc}")
        return None

    display_report(completed_assessment, output_fn=output_fn)

    reviewed = _prompt_review_acknowledgment(input_fn=input_fn, output_fn=output_fn)
    if not reviewed:
        output_fn("You reviewed this assessment and chose to delay the final retention decision.")
        return completed_assessment

    output_fn("You reviewed this assessment and acknowledged that it is advisory.")
    retain_result = _prompt_result_retention(input_fn=input_fn, output_fn=output_fn)
    if not retain_result:
        output_fn("You reviewed this assessment and chose not to retain it for future reference.")
        return completed_assessment

    if context.save_report:
        report_path = save_external_report(
            completed_assessment,
            repository_root=context.request.codebase_root,
        )
        output_fn(f"Report copy saved to: {report_path}")
    output_fn("You reviewed this assessment and retained it for future reference.")
    return completed_assessment


def _print_history_entries(
    entries: list[Any],
    *,
    output_fn: OutputFunction,
) -> None:
    if not entries:
        output_fn("No matching analyses found.")
        return

    for entry in entries:
        output_fn(
            f"{entry.assessment_id} | {entry.created_at.isoformat()} | "
            f"{entry.summary} | {entry.conclusion}"
        )


def run_history_menu(
    *,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
    principal_id: str | None = None,
    database_path: str | None = None,
) -> None:
    """Run the history submenu for listing, searching, and reopening previous assessments."""

    effective_principal = resolve_principal_id(principal_id)
    history_menu = (
        "1. List recent analyses",
        "2. Search analyses",
        "3. Open an analysis by identifier",
        "4. Return to main menu",
    )

    while True:
        for option in history_menu:
            output_fn(option)

        try:
            choice = input_fn("Select an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("Session ended.")
            return

        if choice == "1":
            entries = list_history(effective_principal, database_path=database_path)
            if not entries:
                output_fn("No analyses found for this principal.")
            else:
                _print_history_entries(entries, output_fn=output_fn)
        elif choice == "2":
            query = input_fn("Search term: ").strip()
            entries = search_history(effective_principal, query, database_path=database_path)
            if not entries:
                output_fn("No matching analyses found.")
            else:
                _print_history_entries(entries, output_fn=output_fn)
        elif choice == "3":
            assessment_id = input_fn("Assessment identifier: ").strip()
            if not assessment_id:
                output_fn(_HISTORY_UNAVAILABLE_MESSAGE)
                continue

            detail = get_history_detail(assessment_id, effective_principal, database_path=database_path)
            if detail is None:
                output_fn(_HISTORY_UNAVAILABLE_MESSAGE)
                continue

            output_fn(detail.markdown_report)
        elif choice == "4":
            return
        else:
            output_fn("Invalid history menu choice. Please select 1, 2, 3, or 4.")


def run_interactive_session(
    *,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
    analyze_action: ActionFunction | None = None,
    history_action: ActionFunction | None = None,
    provider: Provider | None = None,
) -> None:
    """Run the main menu until the Developer chooses to exit.

    Action callbacks keep this menu independent from request intake and history
    navigation, which are implemented by their respective workflow tasks.
    """

    if analyze_action is None:
        analyze_action = lambda: run_analysis_interaction(
            input_fn=input_fn,
            output_fn=output_fn,
            provider=provider,
        )
    if history_action is None:
        history_action = lambda: run_history_menu(
            input_fn=input_fn,
            output_fn=output_fn,
        )

    while True:
        for option in _MENU_OPTIONS:
            output_fn(option)

        try:
            choice = input_fn("Select an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("Session ended.")
            return

        if choice == "1":
            try:
                analyze_action()
            except (EOFError, KeyboardInterrupt):
                output_fn("Session ended.")
                return
        elif choice == "2":
            try:
                history_action()
            except (EOFError, KeyboardInterrupt):
                output_fn("Session ended.")
                return
        elif choice == "3":
            return
        else:
            output_fn("Invalid menu choice. Please select 1, 2, or 3.")


__all__ = [
    "display_report",
    "prepare_interactive_analysis",
    "prompt_analysis_request",
    "run_analysis_interaction",
    "run_history_menu",
    "run_interactive_session",
    "save_external_report",
]