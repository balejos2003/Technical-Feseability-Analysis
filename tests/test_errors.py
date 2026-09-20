from feasibility.errors import (
    AIServiceUnavailableError,
    FeasibilityError,
    InvalidAIResponseError,
    InvalidPathError,
    UnauthorizedHistoryAccessError,
    UnreadableFileError,
)


def test_feasibility_error_serializes_structured_details():
    error = InvalidPathError("Repository path is not readable", path="/tmp/repo")

    payload = error.to_dict()
    assert payload["code"] == "invalid_path"
    assert payload["message"] == "Repository path is not readable"
    assert payload["details"]["path"] == "/tmp/repo"
    assert str(error) == "Repository path is not readable"


def test_specific_errors_have_expected_codes():
    assert InvalidPathError("x").code == "invalid_path"
    assert UnreadableFileError("x").code == "unreadable_file"
    assert AIServiceUnavailableError("x").code == "ai_unavailable"
    assert InvalidAIResponseError("x").code == "invalid_ai_output"
    assert UnauthorizedHistoryAccessError("x").code == "unauthorized_history_access"


def test_base_error_is_a_runtime_error():
    error = FeasibilityError("base failure")
    assert isinstance(error, RuntimeError)
    assert error.details == {}
