"""Interactive terminal session for the feasibility analysis application."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], Any]
ActionFunction = Callable[[], Any]

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
    principal_id: str,
    request_id: str | None = None,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
    scope_rules: Any = None,
) -> Any:
    """Collect analysis inputs and prepare their read-only discovery context."""

    from .workflow import prepare_analysis_context

    request_input = prompt_analysis_request(input_fn=input_fn, output_fn=output_fn)
    return prepare_analysis_context(
        request_input,
        principal_id=principal_id,
        request_id=request_id,
        scope_rules=scope_rules,
    )


def run_analysis_interaction(
    *,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
    principal_id: str = "local-developer",
) -> Any:
    """Prepare one interactive request and display its discovered scope."""

    context = prepare_interactive_analysis(
        principal_id=principal_id,
        input_fn=input_fn,
        output_fn=output_fn,
    )
    output_fn("Analysis request prepared.")
    output_fn(f"Discovered files: {len(context.discovery.files)}")
    output_fn(f"Discovery issues: {len(context.discovery.issues)}")
    return context


def run_interactive_session(
    *,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
    analyze_action: ActionFunction | None = None,
    history_action: ActionFunction | None = None,
) -> None:
    """Run the main menu until the Developer chooses to exit.

    Action callbacks keep this menu independent from request intake and history
    navigation, which are implemented by their respective workflow tasks.
    """

    if analyze_action is None:
        analyze_action = lambda: run_analysis_interaction(
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
                if history_action is not None:
                    history_action()
            except (EOFError, KeyboardInterrupt):
                output_fn("Session ended.")
                return
        elif choice == "3":
            return
        else:
            output_fn("Invalid menu choice. Please select 1, 2, or 3.")


__all__ = [
    "prepare_interactive_analysis",
    "prompt_analysis_request",
    "run_analysis_interaction",
    "run_interactive_session",
]