"""Interactive terminal session for the feasibility analysis application."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], Any]
ActionFunction = Callable[[], Any]

_MENU_OPTIONS = (
    "1. Analyze a change",
    "2. Consult analysis history",
    "3. Exit",
)


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


__all__ = ["run_interactive_session"]