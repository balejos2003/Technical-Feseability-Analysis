"""Evidence capture and validation for traceable findings."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .models import EvidenceItem, EvidenceKind


@dataclass(frozen=True)
class EvidenceCapture:
    """A captured source span and its metadata for a material finding."""

    evidence_id: str
    kind: EvidenceKind
    path: str
    start_line: int
    end_line: int
    excerpt: str
    file_hash: str
    description: str

    @property
    def as_evidence_item(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=self.evidence_id,
            kind=self.kind,
            description=self.description,
            path=self.path,
            start_line=self.start_line,
            end_line=self.end_line,
            excerpt=self.excerpt,
            file_hash=self.file_hash,
        )


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_evidence(
    repository_root: str | Path,
    path: str,
    *,
    start_line: int,
    end_line: int,
    evidence_id: str | None = None,
    description: str | None = None,
    kind: EvidenceKind | str = EvidenceKind.CODE,
) -> EvidenceCapture:
    """Capture a bounded, source-backed evidence span from within a repository."""

    if start_line <= 0 or end_line <= 0:
        raise ValueError("Line numbers must be positive")
    if start_line > end_line:
        raise ValueError("start_line cannot be greater than end_line")

    root = Path(repository_root).expanduser().resolve()
    file_path = (root / path).resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"Evidence file not found: {path}")
    if not file_path.is_file():
        raise ValueError(f"Evidence path is not a file: {path}")

    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if start_line > len(lines) or end_line > len(lines):
        raise ValueError("Evidence range exceeds file length")

    excerpt_lines = lines[start_line - 1 : end_line]
    excerpt = "\n".join(excerpt_lines)
    relative_path = file_path.relative_to(root).as_posix()

    return EvidenceCapture(
        evidence_id=evidence_id or f"ev-{start_line}-{end_line}",
        kind=EvidenceKind(kind),
        path=relative_path,
        start_line=start_line,
        end_line=end_line,
        excerpt=excerpt,
        file_hash=_file_hash(file_path),
        description=description or f"Evidence captured from {relative_path}.",
    )


__all__ = ["EvidenceCapture", "capture_evidence"]
