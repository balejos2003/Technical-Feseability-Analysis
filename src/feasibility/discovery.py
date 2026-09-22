"""Bounded, read-only repository discovery for feasibility analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import validate_application_paths_outside_repository
from .models import ScopeRules


@dataclass(frozen=True)
class DiscoveredFile:
    """A readable file selected for analysis."""

    path: Path
    relative_path: str
    size_bytes: int


@dataclass(frozen=True)
class DiscoveryIssue:
    """A file the analyzer intentionally skipped or flagged."""

    kind: str
    path: str
    detail: str


@dataclass(frozen=True)
class DiscoveryResult:
    """The files selected and the issues encountered during discovery."""

    files: list[DiscoveredFile]
    issues: list[DiscoveryIssue]


def _normalize_scope_rules(scope_rules: ScopeRules | dict[str, Any] | None) -> ScopeRules:
    if scope_rules is None:
        return ScopeRules()
    return ScopeRules.from_mapping(scope_rules)


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_excluded(relative_path: Path, rules: ScopeRules) -> bool:
    parts = tuple(relative_path.parts)
    if any(part in rules.excluded_dirs for part in parts[:-1]):
        return True
    if parts and parts[0] in rules.excluded_dirs:
        return True
    if relative_path.name in rules.excluded_files:
        return True
    return False


def discover_repository(
    repository_root: str | Path,
    scope_rules: ScopeRules | dict[str, Any] | None = None,
) -> DiscoveryResult:
    """Return readable files and explicit skip reasons within a repository.

    The discovery process is intentionally read-only and bounded: it skips excluded
    directories, ignores symlinks unless configured to follow them, rejects files
    larger than the configured threshold, and reports unreadable or unsupported files
    as issues instead of silently dropping them.
    """

    root = Path(repository_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository root is not a directory: {root}")

    validate_application_paths_outside_repository(root)

    rules = _normalize_scope_rules(scope_rules)
    files: list[DiscoveredFile] = []
    issues: list[DiscoveryIssue] = []

    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)

        if path.is_symlink():
            issues.append(
                DiscoveryIssue(
                    kind="symlink_skipped",
                    path=relative.as_posix(),
                    detail="Symlinks are skipped unless explicitly allowed.",
                )
            )
            continue

        if path.is_dir():
            if _is_excluded(relative, rules):
                continue
            continue

        if not path.is_file():
            continue

        if _is_excluded(relative, rules):
            continue

        if rules.allowed_extensions and path.suffix.lower().lstrip(".") not in {
            ext.lower().lstrip(".") for ext in rules.allowed_extensions
        }:
            issues.append(
                DiscoveryIssue(
                    kind="out_of_scope",
                    path=relative.as_posix(),
                    detail="File extension is outside the allowed discovery scope.",
                )
            )
            continue

        try:
            size = path.stat().st_size
        except OSError:
            issues.append(
                DiscoveryIssue(
                    kind="unreadable",
                    path=relative.as_posix(),
                    detail="File metadata could not be read.",
                )
            )
            continue

        if size > rules.max_file_size_bytes:
            issues.append(
                DiscoveryIssue(
                    kind="too_large",
                    path=relative.as_posix(),
                    detail=f"File exceeds the configured size limit of {rules.max_file_size_bytes} bytes.",
                )
            )
            continue

        try:
            data = path.read_bytes()
        except OSError:
            issues.append(
                DiscoveryIssue(
                    kind="unreadable",
                    path=relative.as_posix(),
                    detail="File contents are unreadable or inaccessible.",
                )
            )
            continue

        if b"\x00" in data:
            issues.append(
                DiscoveryIssue(
                    kind="unreadable",
                    path=relative.as_posix(),
                    detail="File is binary or contains NUL bytes and cannot be treated as readable text.",
                )
            )
            continue

        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(
                DiscoveryIssue(
                    kind="unreadable",
                    path=relative.as_posix(),
                    detail="File is binary or not decodable as UTF-8 text.",
                )
            )
            continue

        files.append(
            DiscoveredFile(
                path=path,
                relative_path=relative.as_posix(),
                size_bytes=len(data),
            )
        )

    return DiscoveryResult(files=files, issues=issues)


__all__ = [
    "DiscoveryIssue",
    "DiscoveryResult",
    "DiscoveredFile",
    "discover_repository",
]
