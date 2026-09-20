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


def test_analysis_prompt_collects_all_requested_values():
    answers = iter([
        "./fixture-repository",
        "Add a cache to the data access path",
        "The cache must be invalidated after writes.",
        "yes",
    ])

    request_input = prompt_analysis_request(input_fn=lambda _: next(answers))

    assert request_input == {
        "codebase_path": "./fixture-repository",
        "requested_change": "Add a cache to the data access path",
        "additional_context": "The cache must be invalidated after writes.",
        "save_report": True,
    }


def test_analysis_prompt_accepts_blank_optional_context_and_no_save():
    answers = iter([".", "Refactor the parser", "", "no"])

    request_input = prompt_analysis_request(input_fn=lambda _: next(answers))

    assert request_input["additional_context"] == ""
    assert request_input["save_report"] is False
