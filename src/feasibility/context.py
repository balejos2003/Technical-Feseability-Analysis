"""Bounded source context preparation for AI feasibility analysis."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .discovery import DiscoveryIssue, DiscoveryResult, DiscoveredFile
from .models import ScopeRules


@dataclass(frozen=True)
class SourceContextItem:
    """A bounded source excerpt with traceability metadata."""

    path: str
    start_line: int
    end_line: int
    excerpt: str
    file_hash: str
    truncated: bool = False


@dataclass(frozen=True)
class SourceContext:
    """Read-only source snapshot and discovery metadata supplied to the AI."""

    repository_root: str
    items: tuple[SourceContextItem, ...]
    issues: tuple[DiscoveryIssue, ...]
    excluded_dirs: tuple[str, ...]
    excluded_files: tuple[str, ...]
    total_chars: int
    max_context_chars: int
    truncated_files: tuple[str, ...] = ()

    def as_text(self) -> str:
        """Render the bounded context in a stable, human-readable form."""

        sections = [
            f"Repository root: {self.repository_root}",
            f"Excluded directories: {', '.join(self.excluded_dirs) or '(none)'}",
            f"Excluded files: {', '.join(self.excluded_files) or '(none)'}",
        ]
        for item in self.items:
            suffix = " [truncated]" if item.truncated else ""
            sections.append(
                f"\nFile: {item.path} lines {item.start_line}-{item.end_line}"
                f" (sha256:{item.file_hash}){suffix}\n{item.excerpt}"
            )
        if self.issues:
            sections.append("\nDiscovery issues:")
            sections.extend(
                f"- {issue.kind}: {issue.path} ({issue.detail})" for issue in self.issues
            )
        return "\n".join(sections)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_source(discovered_file: DiscoveredFile) -> tuple[str, str]:
    data = discovered_file.path.read_bytes()
    return data.decode("utf-8"), _hash_bytes(data)


def _bounded_excerpt(text: str, budget: int) -> tuple[str, int, bool]:
    lines = text.splitlines()
    if not lines or budget <= 0:
        return "", 0, bool(text)

    full_excerpt = "\n".join(lines)
    if len(full_excerpt) <= budget:
        return full_excerpt, len(lines), False

    excerpt = full_excerpt[:budget].rstrip("\n")
    line_count = excerpt.count("\n") + (1 if excerpt else 0)
    return excerpt, line_count, True


def prepare_source_context(
    repository_root: str | Path,
    discovery: DiscoveryResult,
    *,
    scope_rules: ScopeRules | dict[str, object] | None = None,
    max_context_chars: int = 100_000,
) -> SourceContext:
    """Prepare bounded source excerpts from an existing discovery result."""

    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be positive")

    root = Path(repository_root).expanduser().resolve()
    rules = ScopeRules.from_mapping(scope_rules)
    items: list[SourceContextItem] = []
    truncated_files: list[str] = []
    total_chars = 0

    for discovered_file in discovery.files:
        if total_chars >= max_context_chars:
            truncated_files.append(discovered_file.relative_path)
            continue

        text, file_hash = _read_source(discovered_file)
        remaining = max_context_chars - total_chars
        excerpt, line_count, truncated = _bounded_excerpt(text, remaining)
        if not excerpt:
            truncated_files.append(discovered_file.relative_path)
            continue

        item = SourceContextItem(
            path=discovered_file.relative_path,
            start_line=1,
            end_line=line_count,
            excerpt=excerpt,
            file_hash=file_hash,
            truncated=truncated,
        )
        items.append(item)
        total_chars += len(excerpt)
        if truncated:
            truncated_files.append(discovered_file.relative_path)

    return SourceContext(
        repository_root=str(root),
        items=tuple(items),
        issues=tuple(discovery.issues),
        excluded_dirs=rules.excluded_dirs,
        excluded_files=rules.excluded_files,
        total_chars=total_chars,
        max_context_chars=max_context_chars,
        truncated_files=tuple(truncated_files),
    )


__all__ = ["SourceContext", "SourceContextItem", "prepare_source_context"]
