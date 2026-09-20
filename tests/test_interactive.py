from feasibility.interactive import prompt_analysis_request, run_interactive_session


def test_session_exits_from_main_menu():
    inputs = iter(["3"])
    output = []

    run_interactive_session(input_fn=lambda _: next(inputs), output_fn=output.append)

    assert output == [
        "1. Analyze a change",
        "2. Consult analysis history",
        "3. Exit",
    ]


def test_invalid_menu_choice_keeps_session_open():
    inputs = iter(["invalid", "3"])
    output = []

    run_interactive_session(input_fn=lambda _: next(inputs), output_fn=output.append)

    assert "Invalid menu choice. Please select 1, 2, or 3." in output
    assert output.count("1. Analyze a change") == 2


def test_analysis_prompt_collects_all_requested_values(tmp_path):
    answers = iter([
        str(tmp_path),
        "Add a cache to the data access path",
        "The cache must be invalidated after writes.",
        "yes",
    ])

    request_input = prompt_analysis_request(input_fn=lambda _: next(answers))

    assert request_input == {
        "codebase_path": str(tmp_path),
        "requested_change": "Add a cache to the data access path",
        "additional_context": "The cache must be invalidated after writes.",
        "save_report": True,
    }


def test_analysis_prompt_accepts_blank_optional_context_and_no_save():
    answers = iter([".", "Refactor the parser", "", "no"])

    request_input = prompt_analysis_request(input_fn=lambda _: next(answers))

    assert request_input["additional_context"] == ""
    assert request_input["save_report"] is False


def test_analysis_prompt_retries_unavailable_path_and_blank_change(tmp_path):
    answers = iter([
        str(tmp_path / "missing"),
        str(tmp_path),
        "",
        "Add validation",
        "",
        "no",
    ])
    output = []

    request_input = prompt_analysis_request(
        input_fn=lambda _: next(answers),
        output_fn=output.append,
    )

    assert request_input["codebase_path"] == str(tmp_path)
    assert request_input["requested_change"] == "Add validation"
    assert "Codebase path is unavailable. Please try again." in output
    assert "Requested change cannot be blank. Please try again." in output


def test_session_ends_cleanly_when_interrupted():
    output = []

    def interrupted_input(_: str) -> str:
        raise KeyboardInterrupt

    run_interactive_session(input_fn=interrupted_input, output_fn=output.append)

    assert output[-1] == "Session ended."
