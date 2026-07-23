"""Tests for core/config_sync.py — CDN config fetcher."""
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def config_fetcher():
    """Create a fresh ConfigFetcher for each test."""
    from core.config_sync import ConfigFetcher
    return ConfigFetcher()


@pytest.fixture
def mock_cdn_response():
    """Sample CDN config response."""
    return '''
AI_CONFIGS = {
    "groq": {
        "id": 1,
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant",
        "priority": 1,
        "enabled": True,
        "format": "openai",
    },
    "nvidia": {
        "id": 2,
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "meta/llama-3.1-8b-instruct",
        "priority": 2,
        "enabled": True,
        "format": "openai",
    },
}
'''


class TestConfigFetcher:
    def test_initialize_disabled(self, config_fetcher):
        """Test that CDN is disabled when URL is not set."""
        with patch.dict("os.environ", {}, clear=True):
            config_fetcher.initialize()
            assert config_fetcher._enabled is False

    def test_initialize_default_url(self, config_fetcher):
        """Test that 'default' URL generates jsDelivr URL."""
        with patch.dict("os.environ", {"CDN_CONFIG_URL": "default", "CDN_CONFIG_BRANCH": "main"}):
            config_fetcher.initialize()
            assert config_fetcher._enabled is True
            assert "cdn.jsdelivr.net" in config_fetcher._url
            assert "mihir0209/AI_engine" in config_fetcher._url

    def test_initialize_custom_url(self, config_fetcher):
        """Test custom CDN URL."""
        custom_url = "https://example.com/config.py"
        with patch.dict("os.environ", {"CDN_CONFIG_URL": custom_url}):
            config_fetcher.initialize()
            assert config_fetcher._enabled is True
            assert config_fetcher._url == custom_url

    def test_initialize_custom_ttl(self, config_fetcher):
        """Test custom TTL setting."""
        with patch.dict("os.environ", {"CDN_CONFIG_URL": "default", "CDN_CONFIG_TTL": "3600"}):
            config_fetcher.initialize()
            assert config_fetcher._ttl == 3600

    def test_fetch_and_apply_disabled(self, config_fetcher):
        """Test that fetch returns None when disabled."""
        assert config_fetcher._enabled is False
        result = config_fetcher.fetch_and_apply()
        assert result is None

    def test_parse_config_valid(self, config_fetcher, mock_cdn_response):
        """Test parsing valid config from CDN response."""
        result = config_fetcher._parse_config(mock_cdn_response)
        assert result is not None
        assert isinstance(result, dict)
        assert "groq" in result
        assert "nvidia" in result
        assert result["groq"]["id"] == 1
        assert result["nvidia"]["model"] == "meta/llama-3.1-8b-instruct"

    def test_parse_config_invalid(self, config_fetcher):
        """Test parsing invalid config."""
        assert config_fetcher._parse_config("not a config") is None
        assert config_fetcher._parse_config("") is None
        assert config_fetcher._parse_config("AI_CONFIGS = []") is None

    def test_parse_config_missing_required_fields(self, config_fetcher):
        """Test parsing config with missing required fields."""
        invalid_config = '''
AI_CONFIGS = {
    "bad_provider": {
        "endpoint": "https://example.com",
    }
}
'''
        result = config_fetcher._parse_config(invalid_config)
        assert result is None

    def test_save_and_load_cache(self, config_fetcher, mock_cdn_response):
        """Test saving and loading config cache."""
        configs = config_fetcher._parse_config(mock_cdn_response)
        assert configs is not None

        config_fetcher._save_cache(configs)

        # Check files exist
        from core.config_sync import CACHE_FILE, CACHE_META
        assert CACHE_FILE.exists()
        assert CACHE_META.exists()

        # Load cache
        loaded = config_fetcher._load_cache(ignore_ttl=True)
        assert loaded is not None
        assert "groq" in loaded
        assert loaded["groq"]["id"] == 1

    def test_load_cache_expired(self, config_fetcher, mock_cdn_response):
        """Test that expired cache returns None when TTL is enforced."""
        configs = config_fetcher._parse_config(mock_cdn_response)
        config_fetcher._save_cache(configs)

        # Manipulate metadata to make cache appear expired
        from core.config_sync import CACHE_META
        meta = json.loads(CACHE_META.read_text())
        meta["fetched_at"] = time.time() - 100000  # Old timestamp
        meta["ttl"] = 1  # 1 second TTL
        CACHE_META.write_text(json.dumps(meta))

        # Should return None when TTL is enforced
        loaded = config_fetcher._load_cache(ignore_ttl=False)
        assert loaded is None

    def test_load_cache_expired_ignore_ttl(self, config_fetcher, mock_cdn_response):
        """Test that expired cache loads when ignore_ttl=True."""
        configs = config_fetcher._parse_config(mock_cdn_response)
        config_fetcher._save_cache(configs)

        from core.config_sync import CACHE_META
        meta = json.loads(CACHE_META.read_text())
        meta["fetched_at"] = time.time() - 100000
        meta["ttl"] = 1
        CACHE_META.write_text(json.dumps(meta))

        loaded = config_fetcher._load_cache(ignore_ttl=True)
        assert loaded is not None
        assert "groq" in loaded

    def test_get_status_disabled(self, config_fetcher):
        """Test status when disabled."""
        status = config_fetcher.get_status()
        assert status["enabled"] is False

    def test_get_status_enabled_cached(self, config_fetcher, mock_cdn_response):
        """Test status when enabled and cached."""
        config_fetcher._enabled = True
        config_fetcher._url = "https://example.com/config.py"

        configs = config_fetcher._parse_config(mock_cdn_response)
        config_fetcher._save_cache(configs)

        status = config_fetcher.get_status()
        assert status["enabled"] is True
        assert status["cached"] is True
        assert "providers" in status

    def test_fetch_from_cdn_timeout(self, config_fetcher):
        """Test fetch handles timeout gracefully."""
        config_fetcher._enabled = True
        config_fetcher._url = "https://example.com/config.py"

        with patch("requests.get") as mock_get:
            from requests.exceptions import Timeout
            mock_get.side_effect = Timeout("Request timed out")
            result = config_fetcher._fetch_from_cdn()
            assert result is None

    def test_fetch_from_cdn_connection_error(self, config_fetcher):
        """Test fetch handles connection error gracefully."""
        config_fetcher._enabled = True
        config_fetcher._url = "https://example.com/config.py"

        with patch("requests.get") as mock_get:
            from requests.exceptions import ConnectionError
            mock_get.side_effect = ConnectionError("No internet")
            result = config_fetcher._fetch_from_cdn()
            assert result is None

    def test_fetch_from_cdn_http_error(self, config_fetcher):
        """Test fetch handles HTTP errors gracefully."""
        config_fetcher._enabled = True
        config_fetcher._url = "https://example.com/config.py"

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            result = config_fetcher._fetch_from_cdn()
            assert result is None

    def test_fetch_from_cdn_success(self, config_fetcher, mock_cdn_response):
        """Test successful fetch from CDN."""
        config_fetcher._enabled = True
        config_fetcher._url = "https://example.com/config.py"

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_cdn_response
            mock_get.return_value = mock_response
            result = config_fetcher._fetch_from_cdn()
            assert result is not None
            assert "groq" in result

    def test_lock_file_prevents_concurrent_fetch(self, config_fetcher):
        """Test that lock file prevents concurrent fetches."""
        from core.config_sync import LOCK_FILE

        config_fetcher._enabled = True
        config_fetcher._url = "https://example.com/config.py"

        # Create a recent lock file
        LOCK_FILE.write_text("12345")

        result = config_fetcher._fetch_from_cdn()
        assert result is None

        # Cleanup
        LOCK_FILE.unlink(missing_ok=True)
