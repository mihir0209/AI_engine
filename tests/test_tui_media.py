"""Tests for TUI media helpers."""
import base64
from pathlib import Path
from unittest.mock import MagicMock, patch


from ai_engine.tui.media import (
    _is_allowed_image_url,
    extract_image_from_text,
    persist_image_ref,
)
from ai_engine.tui.routing import model_name_matches, provider_priority


def test_model_name_matches_variants():
    assert model_name_matches("anthropic/claude-3.5-sonnet", "claude-3.5-sonnet")
    assert model_name_matches("openrouter/anthropic/claude-3.5-sonnet", "claude-3.5-sonnet")
    assert not model_name_matches("", "gpt-4o")


def test_provider_priority_returns_int():
    assert isinstance(provider_priority("openrouter"), int)


def test_allowed_image_url_blocks_private_hosts():
    assert not _is_allowed_image_url("http://127.0.0.1/secret.png")
    assert not _is_allowed_image_url("https://evil.example.com/a.png")
    assert _is_allowed_image_url("https://openrouter.ai/files/x.png")


def test_persist_image_ref_data_uri(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_engine.tui.media.GENERATED_DIR", tmp_path)
    tiny = base64.b64encode(b"png").decode()
    path = persist_image_ref(f"data:image/png;base64,{tiny}", stem="test")
    assert path is not None
    assert Path(path).exists()


def test_persist_image_ref_blocks_disallowed_url():
    assert persist_image_ref("https://internal.corp.local/img.png") is None


def test_persist_image_ref_local_file(tmp_path):
    img = tmp_path / "local.png"
    img.write_bytes(b"data")
    assert persist_image_ref(str(img)) == str(img)


def test_extract_image_from_text_data_uri(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_engine.tui.media.GENERATED_DIR", tmp_path)
    tiny = base64.b64encode(b"png").decode()
    content = f"Here is your image: data:image/png;base64,{tiny}"
    path = extract_image_from_text(content)
    assert path is not None
    assert Path(path).exists()


@patch("ai_engine.tui.media.requests.get")
def test_fetch_url_image_size_cap(mock_get, tmp_path, monkeypatch):
    monkeypatch.setattr("ai_engine.tui.media.GENERATED_DIR", tmp_path)
    monkeypatch.setattr("ai_engine.tui.media._MAX_DOWNLOAD_BYTES", 32)
    resp = MagicMock()
    resp.__enter__.return_value = resp
    resp.raise_for_status.return_value = None
    resp.iter_content.return_value = [b"x" * 20, b"y" * 20]
    mock_get.return_value = resp
    assert persist_image_ref("https://openrouter.ai/big.bin") is None
