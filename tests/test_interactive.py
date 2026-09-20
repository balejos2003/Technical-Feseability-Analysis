from feasibility.interactive import run_interactive_session


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
