"""Interactive terminal session for the feasibility analysis application."""

from __future__ import annotations

from collections.abc import Callable
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


def prompt_analysis_request(*, input_fn: InputFunction = input) -> AnalysisInput:
    """Collect the inputs needed to start one analysis request."""

    codebase_path = input_fn("Codebase path: ").strip()
    requested_change = input_fn("Requested change: ").strip()
    additional_context = input_fn("Optional additional context: ").strip()
    save_answer = input_fn("Save report outside the codebase? ").strip().lower()

    return {
        "codebase_path": codebase_path,
        "requested_change": requested_change,
        "additional_context": additional_context,
        "save_report": save_answer in {"yes", "y", "sim", "s"},
    }


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

    while True:
        for option in _MENU_OPTIONS:
            output_fn(option)

        try:
            choice = input_fn("Select an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("Session ended.")
            return

        if choice == "1":
            if analyze_action is not None:
                analyze_action()
        elif choice == "2":
            if history_action is not None:
                history_action()
        elif choice == "3":
            return
        else:
            output_fn("Invalid menu choice. Please select 1, 2, or 3.")


__all__ = ["prompt_analysis_request", "run_interactive_session"]