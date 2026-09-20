import feasibility.__main__ as entrypoint


def test_main_starts_interactive_session(monkeypatch):
    calls = []

    monkeypatch.setattr(
        entrypoint,
        "run_interactive_session",
        lambda: calls.append("started"),
    )

    entrypoint.main()

    assert calls == ["started"]
