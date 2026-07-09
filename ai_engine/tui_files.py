"""Fuzzy file indexing for @attach and /read suggestions in the TUI."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from rapidfuzz import fuzz, process as rf_process
except ImportError:
    rf_process = None
    fuzz = None

_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".eggs",
}


@dataclass(frozen=True, slots=True)
class FileHit:
    path: str
    label: str
    score: float


def build_file_index(
    root: str,
    *,
    max_files: int = 4000,
    max_depth: int = 5,
) -> list[str]:
    """Collect file paths under *root* for fuzzy matching."""
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        return []

    results: list[str] = []
    root_str = str(root_path)

    def walk(current: Path, depth: int) -> None:
        if len(results) >= max_files or depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for entry in entries:
            if len(results) >= max_files:
                return
            name = entry.name
            if name.startswith(".") and name not in {".env", ".env.example"}:
                continue
            try:
                if entry.is_dir():
                    if name in _SKIP_DIR_NAMES:
                        continue
                    walk(entry, depth + 1)
                elif entry.is_file():
                    results.append(str(entry))
            except OSError:
                continue

    walk(root_path, 0)
    results.sort(key=lambda p: p.lower())
    return results


def match_files(
    query: str,
    paths: list[str],
    *,
    root: str | None = None,
    limit: int = 8,
) -> list[FileHit]:
    """Fuzzy-match file paths. *query* may be a partial name or path fragment."""
    q = query.strip()
    if not paths:
        return []

    root_path = Path(root).expanduser().resolve() if root else None
    labels: list[str] = []
    for path in paths:
        if root_path is not None:
            try:
                labels.append(str(Path(path).resolve().relative_to(root_path)))
            except ValueError:
                labels.append(os.path.basename(path))
        else:
            labels.append(path)

    if not q:
        return [
            FileHit(path=paths[i], label=labels[i], score=1.0)
            for i in range(min(limit, len(paths)))
        ]

    if rf_process is not None and fuzz is not None:
        hits = rf_process.extract(
            q,
            labels,
            scorer=fuzz.WRatio,
            limit=limit,
            score_cutoff=30,
        )
        if hits:
            return [
                FileHit(path=paths[idx], label=labels[idx], score=score / 100.0)
                for _, score, idx in hits
            ]

    tokens = q.lower().split()
    results: list[FileHit] = []
    for path, label in zip(paths, labels):
        hay = f"{label} {path}".lower()
        if all(tok in hay for tok in tokens):
            results.append(FileHit(path=path, label=label, score=0.7))
        if len(results) >= limit:
            break
    return results