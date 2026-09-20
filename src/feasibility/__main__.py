"""Executable entry point for the interactive feasibility analysis session."""

from .interactive import run_interactive_session


def main() -> None:
    """Start the interactive application without command-line arguments."""

    run_interactive_session()


if __name__ == "__main__":
    main()