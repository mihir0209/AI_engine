"""
Session management and database backup utilities for AI Engine
"""
import os
import json
import shutil
import sqlite3
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading


@dataclass
class Session:
    """User session"""
    id: str
    user_id: str
    tenant_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class SessionManager:
    """Manages user sessions"""

    def __init__(self, session_timeout: int = 3600):
        self.sessions: Dict[str, Session] = {}
        self.session_timeout = session_timeout
        self._lock = threading.Lock()
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]

    def create_session(
        self,
        user_id: str,
        tenant_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        metadata: Dict = None
    ) -> Session:
        """Create a new session"""
        import uuid

        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        expires_at = (datetime.now() + timedelta(seconds=self.session_timeout)).isoformat()

        session = Session(
            id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )

        with self._lock:
            self.sessions[session_id] = session

            # Track user sessions
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = []
            self.user_sessions[user_id].append(session_id)

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session and not self._is_expired(session):
                return session
            elif session:
                # Clean up expired session
                self._remove_session(session_id)
            return None

    def validate_session(self, session_id: str) -> bool:
        """Validate if session is active"""
        return self.get_session(session_id) is not None

    def update_activity(self, session_id: str):
        """Update last activity time"""
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].last_active = datetime.now().isoformat()
                # Extend expiration
                self.sessions[session_id].expires_at = (
                    datetime.now() + timedelta(seconds=self.session_timeout)
                ).isoformat()

    def destroy_session(self, session_id: str) -> bool:
        """Destroy a session"""
        with self._lock:
            return self._remove_session(session_id)

    def destroy_user_sessions(self, user_id: str) -> int:
        """Destroy all sessions for a user"""
        with self._lock:
            session_ids = self.user_sessions.get(user_id, [])
            count = 0
            for sid in session_ids[:]:
                if self._remove_session(sid):
                    count += 1
            return count

    def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all active sessions for a user"""
        with self._lock:
            session_ids = self.user_sessions.get(user_id, [])
            return [self.sessions[sid] for sid in session_ids if sid in self.sessions]

    def cleanup_expired(self) -> int:
        """Clean up expired sessions"""
        with self._lock:
            expired = []
            for sid, session in self.sessions.items():
                if self._is_expired(session):
                    expired.append(sid)

            for sid in expired:
                self._remove_session(sid)

            return len(expired)

    def _is_expired(self, session: Session) -> bool:
        """Check if session is expired"""
        if not session.expires_at:
            return False
        return datetime.fromisoformat(session.expires_at) < datetime.now()

    def _remove_session(self, session_id: str) -> bool:
        """Remove a session"""
        if session_id not in self.sessions:
            return False

        session = self.sessions.pop(session_id)

        # Remove from user sessions
        if session.user_id in self.user_sessions:
            if session_id in self.user_sessions[session.user_id]:
                self.user_sessions[session.user_id].remove(session_id)

        return True

    def get_stats(self) -> Dict:
        """Get session statistics"""
        with self._lock:
            return {
                "total_sessions": len(self.sessions),
                "unique_users": len(self.user_sessions),
                "expired_sessions": sum(1 for s in self.sessions.values() if self._is_expired(s))
            }


class DatabaseBackup:
    """Database backup and restore utilities"""

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)

    def backup_sqlite(self, db_path: str, backup_name: str = None) -> str:
        """Create a backup of SQLite database"""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")

        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            db_name = os.path.basename(db_path).replace(".db", "")
            backup_name = f"{db_name}_{timestamp}.db"

        backup_path = os.path.join(self.backup_dir, backup_name)

        # Use SQLite backup API for consistent backup
        source_conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_path)

        try:
            source_conn.backup(backup_conn)
            return backup_path
        finally:
            source_conn.close()
            backup_conn.close()

    def backup_json(self, data: Dict, filename: str) -> str:
        """Backup JSON data to file"""
        backup_path = os.path.join(self.backup_dir, filename)
        with open(backup_path, "w") as f:
            json.dump(data, f, indent=2)
        return backup_path

    def restore_sqlite(self, backup_path: str, target_path: str) -> bool:
        """Restore SQLite database from backup"""
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        # Create backup of current database if it exists
        if os.path.exists(target_path):
            self.backup_sqlite(target_path, f"pre_restore_{os.path.basename(target_path)}")

        # Copy backup to target
        shutil.copy2(backup_path, target_path)
        return True

    def list_backups(self, pattern: str = "*.db") -> List[Dict]:
        """List available backups"""
        import glob

        backups = []
        for backup_file in glob.glob(os.path.join(self.backup_dir, pattern)):
            stat = os.stat(backup_file)
            backups.append({
                "filename": os.path.basename(backup_file),
                "path": backup_file,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })

        return sorted(backups, key=lambda x: x["created"], reverse=True)

    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """Remove old backups, keeping only the most recent"""
        backups = self.list_backups()

        if len(backups) <= keep_count:
            return 0

        removed = 0
        for backup in backups[keep_count:]:
            os.remove(backup["path"])
            removed += 1

        return removed


# Global instances
session_manager = SessionManager()
database_backup = DatabaseBackup()
