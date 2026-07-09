"""Tests for per-user config paths and env bootstrap."""
import os
from pathlib import Path

from core.env_bootstrap import ENV_FILE_OVERRIDE_VAR, bootstrap_user_environment
from core.user_paths import AI_ENGINE_HOME, USER_DATA_DIR, USER_ENV_FILE


def test_user_paths_under_home():
    assert str(AI_ENGINE_HOME).endswith(".ai-engine")
    assert USER_ENV_FILE.parent == AI_ENGINE_HOME
    assert USER_DATA_DIR.parent == AI_ENGINE_HOME


def test_global_env_layer(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    global_env = tmp_path / ".ai-engine" / ".env"
    global_env.parent.mkdir(parents=True)
    global_env.write_text("LAYER_TEST=global\n", encoding="utf-8")
    monkeypatch.setattr("core.env_bootstrap.USER_ENV_FILE", global_env)
    monkeypatch.delenv("LAYER_TEST", raising=False)
    bootstrap_user_environment(force=True)
    assert os.getenv("LAYER_TEST") == "global"


def test_cwd_overrides_global(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    global_env = tmp_path / ".ai-engine" / ".env"
    global_env.parent.mkdir(parents=True)
    global_env.write_text("LAYER_TEST=global\nSHARED=from-global\n", encoding="utf-8")
    (work / ".env").write_text("LAYER_TEST=project\n", encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setattr("core.env_bootstrap.USER_ENV_FILE", global_env)
    monkeypatch.delenv("LAYER_TEST", raising=False)
    monkeypatch.delenv("SHARED", raising=False)
    bootstrap_user_environment(force=True)
    assert os.getenv("LAYER_TEST") == "project"
    assert os.getenv("SHARED") == "from-global"


def test_explicit_env_overrides_cwd_and_global(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    global_env = tmp_path / ".ai-engine" / ".env"
    global_env.parent.mkdir(parents=True)
    global_env.write_text("LAYER_TEST=global\n", encoding="utf-8")
    (work / ".env").write_text("LAYER_TEST=project\n", encoding="utf-8")
    profile = tmp_path / "work.env"
    profile.write_text("LAYER_TEST=profile\n", encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setattr("core.env_bootstrap.USER_ENV_FILE", global_env)
    monkeypatch.setenv(ENV_FILE_OVERRIDE_VAR, str(profile))
    monkeypatch.delenv("LAYER_TEST", raising=False)
    bootstrap_user_environment(force=True)
    assert os.getenv("LAYER_TEST") == "profile"


def test_process_env_beats_all_files(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    global_env = tmp_path / ".ai-engine" / ".env"
    global_env.parent.mkdir(parents=True)
    global_env.write_text("LAYER_TEST=global\n", encoding="utf-8")
    (work / ".env").write_text("LAYER_TEST=project\n", encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setattr("core.env_bootstrap.USER_ENV_FILE", global_env)
    monkeypatch.setenv("LAYER_TEST", "from-shell")
    bootstrap_user_environment(force=True)
    assert os.getenv("LAYER_TEST") == "from-shell"