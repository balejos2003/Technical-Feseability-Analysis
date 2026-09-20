"""Application-level error types used across discovery, analysis, and history flows."""

from __future__ import annotations

from typing import Any


class FeasibilityError(RuntimeError):
    """Base application exception for feasibility-analysis errors."""

    code = "feasibility_error"

    def __init__(self, message: str, **details: Any):
        super().__init__(message)
        self.message = message
        self.details = details

    @property
    def detail(self) -> dict[str, Any]:
        return dict(self.details)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


class InvalidPathError(FeasibilityError):
    """Raised when a repository or output path is invalid or unsafe."""

    code = "invalid_path"


class UnreadableFileError(FeasibilityError):
    """Raised when a file cannot be read or is not a supported text input."""

    code = "unreadable_file"


class AIServiceUnavailableError(FeasibilityError):
    """Raised when the configured AI service is unavailable or times out."""

    code = "ai_unavailable"


class InvalidAIResponseError(FeasibilityError):
    """Raised when a provider response is structurally invalid."""

    code = "invalid_ai_output"


class UnauthorizedHistoryAccessError(FeasibilityError):
    """Raised when a principal attempts to access another principal's history."""

    code = "unauthorized_history_access"


__all__ = [
    "AIServiceUnavailableError",
    "FeasibilityError",
    "InvalidAIResponseError",
    "InvalidPathError",
    "UnauthorizedHistoryAccessError",
    "UnreadableFileError",
]
