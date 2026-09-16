"""Application paths and output-safety rules."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

_APPLICATION_NAME = "technical-feasibility-analysis"
_DATA_DIR_ENV = "FEASIBILITY_DATA_DIR"


@dataclass(frozen=True)
class ApplicationPaths:
    """Locations used by the application, independent from an analyzed repository."""

    data_dir: Path
    database_path: Path
    reports_dir: Path


def default_data_dir() -> Path:
    """Return the platform-specific application data directory."""
    configured_dir = os.environ.get(_DATA_DIR_ENV)
    if configured_dir:
        return Path(configured_dir).expanduser().resolve()

    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / _APPLICATION_NAME).resolve()
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return (Path(base_dir) / _APPLICATION_NAME).expanduser().resolve()
    return (Path.home() / ".local" / "share" / _APPLICATION_NAME).resolve()


def application_paths(data_dir: Path | str | None = None) -> ApplicationPaths:
    """Resolve application storage paths without creating files or directories."""
    resolved_data_dir = (
        Path(data_dir).expanduser().resolve() if data_dir is not None else default_data_dir()
    )
    return ApplicationPaths(
        data_dir=resolved_data_dir,
        database_path=resolved_data_dir / "history.sqlite3",
        reports_dir=resolved_data_dir / "reports",
    )


def ensure_output_outside_repository(output_path: Path | str, repository_root: Path | str) -> Path:
    """Validate that an application output path is outside the analyzed repository."""
    output = Path(output_path).expanduser().resolve()
    repository = Path(repository_root).expanduser().resolve()
    try:
        output.relative_to(repository)
    except ValueError:
        return output
    raise ValueError("Application outputs must be outside the analyzed repository")
