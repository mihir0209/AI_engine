"""Tests for image generation helper and parsing."""
from unittest.mock import MagicMock

from core.image_generation import _parse_image_content, generate_image


class TestParseImageContent:
    def test_markdown_url(self):
        data = _parse_image_content("![img](https://example.com/a.png)", "cat")
        assert data[0]["url"] == "https://example.com/a.png"
        assert data[0]["revised_prompt"] == "cat"

    def test_data_uri(self):
        # minimal fake b64
        import base64
        raw = base64.b64encode(b"fake").decode()
        content = f"data:image/png;base64,{raw}"
        data = _parse_image_content(content, "p")
        assert "b64_json" in data[0]

    def test_bare_url(self):
        data = _parse_image_content("here https://cdn.example.com/x.webp ok", "p")
        assert data and "webp" in data[0]["url"]


class TestGenerateImage:
    def test_empty_prompt(self):
        r = generate_image(prompt="")
        assert r["data"] == []
        assert "error" in r

    def test_success_with_mock_engine(self):
        engine = MagicMock()
        result = MagicMock()
        result.success = True
        result.content = "![x](https://img.example.com/out.png)"
        engine.chat_completion.return_value = result

        # Bypass capability discovery by providing slash model
        r = generate_image(
            prompt="a cat",
            model="openrouter/flux",
            engine=engine,
            provider="openrouter",
        )
        assert r["data"]
        assert r["data"][0]["url"] == "https://img.example.com/out.png"

    def test_engine_failure(self):
        engine = MagicMock()
        result = MagicMock()
        result.success = False
        result.error_message = "fail"
        result.content = None
        engine.chat_completion.return_value = result
        r = generate_image(prompt="x", model="openrouter/flux", engine=engine, provider="openrouter")
        assert r["data"] == []
        assert "fail" in r.get("error", "")
