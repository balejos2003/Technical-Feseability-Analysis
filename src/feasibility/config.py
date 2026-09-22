"""Application paths and output-safety rules."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

_APPLICATION_NAME = "technical-feasibility-analysis"
_DATA_DIR_ENV = "FEASIBILITY_DATA_DIR"
_PRINCIPAL_ENV = "FEASIBILITY_PRINCIPAL_ID"


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


def default_principal_id() -> str:
    """Resolve the current developer identity, defaulting to the local user or a deterministic override."""
    configured_principal = os.environ.get(_PRINCIPAL_ENV)
    if configured_principal and configured_principal.strip():
        return configured_principal.strip()

    for env_var in ("USER", "USERNAME", "LOGNAME"):
        value = os.environ.get(env_var)
        if value and value.strip():
            return value.strip()

    return "local-developer"


def resolve_principal_id(principal_id: str | None = None) -> str:
    """Return the active principal id, falling back to the local user unless an explicit value is supplied."""
    if principal_id is not None and principal_id.strip():
        return principal_id.strip()
    return default_principal_id()


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


def validate_application_paths_outside_repository(repository_root: Path | str) -> ApplicationPaths:
    """Reject application data directories that would place history or reports under the analyzed repository."""
    paths = application_paths()
    repository = Path(repository_root).expanduser().resolve()
    for candidate in (paths.data_dir, paths.database_path, paths.reports_dir):
        try:
            ensure_output_outside_repository(candidate, repository)
        except ValueError as exc:
            raise ValueError(
                f"Application outputs must be outside the analyzed repository: {candidate} is inside {repository}."
            ) from exc
    return paths


__all__ = [
    "ApplicationPaths",
    "application_paths",
    "default_data_dir",
    "default_principal_id",
    "ensure_output_outside_repository",
    "resolve_principal_id",
    "validate_application_paths_outside_repository",
]
