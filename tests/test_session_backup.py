"""Tests for session management and database backup"""
import pytest
import tempfile
import shutil
import os
import time
import sqlite3


@pytest.fixture
def session_manager():
    from session_backup import SessionManager
    return SessionManager(session_timeout=2)


@pytest.fixture
def backup_utils():
    from session_backup import DatabaseBackup
    temp_dir = tempfile.mkdtemp()
    db = DatabaseBackup(backup_dir=temp_dir)
    yield db
    shutil.rmtree(temp_dir)


# === Session Manager Tests ===

def test_create_session(session_manager):
    session = session_manager.create_session(user_id="user_1")
    assert session.id.startswith("sess_")
    assert session.user_id == "user_1"


def test_get_session(session_manager):
    session = session_manager.create_session(user_id="user_1")
    retrieved = session_manager.get_session(session.id)
    assert retrieved is not None
    assert retrieved.user_id == "user_1"


def test_validate_session(session_manager):
    session = session_manager.create_session(user_id="user_1")
    assert session_manager.validate_session(session.id) is True


def test_session_expiration(session_manager):
    session = session_manager.create_session(user_id="user_1")
    time.sleep(2.5)
    assert session_manager.get_session(session.id) is None


def test_update_activity(session_manager):
    session = session_manager.create_session(user_id="user_1")
    old_expires = session.expires_at
    
    time.sleep(0.5)
    session_manager.update_activity(session.id)
    
    updated = session_manager.get_session(session.id)
    assert updated.expires_at != old_expires


def test_destroy_session(session_manager):
    session = session_manager.create_session(user_id="user_1")
    assert session_manager.destroy_session(session.id) is True
    assert session_manager.get_session(session.id) is None


def test_destroy_user_sessions(session_manager):
    session_manager.create_session(user_id="user_1")
    session_manager.create_session(user_id="user_1")
    session_manager.create_session(user_id="user_2")
    
    count = session_manager.destroy_user_sessions("user_1")
    assert count == 2
    assert len(session_manager.get_user_sessions("user_1")) == 0
    assert len(session_manager.get_user_sessions("user_2")) == 1


def test_cleanup_expired(session_manager):
    session_manager.create_session(user_id="user_1")
    session_manager.create_session(user_id="user_2")
    
    time.sleep(2.5)
    cleaned = session_manager.cleanup_expired()
    assert cleaned >= 2


def test_get_stats(session_manager):
    session_manager.create_session(user_id="user_1")
    session_manager.create_session(user_id="user_2")
    
    stats = session_manager.get_stats()
    assert stats["total_sessions"] == 2
    assert stats["unique_users"] == 2


# === Database Backup Tests ===

def test_backup_sqlite(backup_utils):
    # Create test database
    db_path = os.path.join(backup_utils.backup_dir, "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'test')")
    conn.commit()
    conn.close()
    
    backup_path = backup_utils.backup_sqlite(db_path)
    assert os.path.exists(backup_path)
    
    # Verify backup
    conn = sqlite3.connect(backup_path)
    result = conn.execute("SELECT * FROM test").fetchone()
    conn.close()
    assert result == (1, 'test')


def test_backup_json(backup_utils):
    data = {"key": "value", "number": 42}
    path = backup_utils.backup_json(data, "test_backup.json")
    
    assert os.path.exists(path)
    with open(path) as f:
        loaded = json.load(f)
    assert loaded == data


def test_list_backups(backup_utils):
    # Create some backup files
    for i in range(3):
        with open(os.path.join(backup_utils.backup_dir, f"backup_{i}.db"), "w") as f:
            f.write("test")
    
    backups = backup_utils.list_backups()
    assert len(backups) == 3


def test_cleanup_old_backups(backup_utils):
    # Create many backup files
    for i in range(10):
        with open(os.path.join(backup_utils.backup_dir, f"backup_{i}.db"), "w") as f:
            f.write("test")
    
    removed = backup_utils.cleanup_old_backups(keep_count=3)
    assert removed == 7
    
    backups = backup_utils.list_backups()
    assert len(backups) == 3


import json
