"""Tests for TUI fuzzy file matching."""
from pathlib import Path

from ai_engine.tui.files import build_file_index, match_files


def test_build_file_index_finds_files(tmp_path):
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / "beta.py").write_text("b", encoding="utf-8")
    paths = build_file_index(str(tmp_path), max_depth=3)
    names = {Path(p).name for p in paths}
    assert "alpha.txt" in names
    assert "beta.py" in names


def test_match_files_fuzzy(tmp_path):
    (tmp_path / "readme.md").write_text("#", encoding="utf-8")
    (tmp_path / "config.py").write_text("x", encoding="utf-8")
    paths = build_file_index(str(tmp_path))
    hits = match_files("config", paths, root=str(tmp_path))
    assert hits
    assert any(Path(h.path).name == "config.py" for h in hits)
