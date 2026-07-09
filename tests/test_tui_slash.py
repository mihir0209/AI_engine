"""Tests for TUI slash command matching."""
from ai_engine.tui.slash import match_slash_commands


def test_match_empty_shows_defaults():
    hits = match_slash_commands("")
    assert len(hits) >= 3
    assert hits[0].command == "help"


def test_fuzzy_match_help():
    hits = match_slash_commands("hel")
    assert any(h.command == "help" for h in hits)


def test_fuzzy_match_read():
    hits = match_slash_commands("rea")
    assert any(h.command == "read" for h in hits)


def test_persona_clear_match():
    hits = match_slash_commands("persona cl")
    assert any("persona clear" in h.command for h in hits)


def test_fuzzy_match_provider_and_image():
    hits = match_slash_commands("prov")
    assert any(h.command == "provider" for h in hits)
    hits = match_slash_commands("imag")
    assert any(h.command == "image" for h in hits)