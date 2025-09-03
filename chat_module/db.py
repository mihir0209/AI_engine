"""
Database models and operations for chat functionality
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class ChatDB:
    def __init__(self, db_path: str = "chat_data.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Create chats table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    model TEXT,
                    provider TEXT,
                    system_prompt TEXT,
                    context_mode TEXT DEFAULT 'window',
                    summary TEXT,
                    is_temporary BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('system','user','assistant')),
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    tokens INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_to INTEGER,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                    FOREIGN KEY (response_to) REFERENCES messages(id)
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages(chat_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chats_updated ON chats(updated_at DESC)")
            
            conn.commit()
            logger.info("Chat database initialized")

    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_chat(self, title: str, model: str = None, provider: str = None, 
                   system_prompt: str = None, is_temporary: bool = False) -> int:
        """Create a new chat and return chat ID"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO chats (title, model, provider, system_prompt, is_temporary, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (title, model, provider, system_prompt, is_temporary))
            chat_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Created chat {chat_id}: {title}")
            return chat_id

    def get_chat(self, chat_id: int) -> Optional[Dict]:
        """Get chat by ID"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
            return dict(row) if row else None

    def get_chats(self, include_temporary: bool = False, limit: int = 50) -> List[Dict]:
        """Get list of chats"""
        with self.get_connection() as conn:
            query = """
                SELECT c.*, 
                       (SELECT content FROM messages WHERE chat_id = c.id ORDER BY created_at DESC LIMIT 1) as last_message,
                       (SELECT COUNT(*) FROM messages WHERE chat_id = c.id) as message_count
                FROM chats c 
                WHERE (? OR is_temporary = 0)
                ORDER BY updated_at DESC 
                LIMIT ?
            """
            rows = conn.execute(query, (include_temporary, limit)).fetchall()
            return [dict(row) for row in rows]

    def add_message(self, chat_id: int, role: str, content: str, 
                   metadata: Dict = None, tokens: int = 0, response_to: int = None) -> int:
        """Add message to chat"""
        if metadata is None:
            metadata = {}
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO messages (chat_id, role, content, metadata, tokens, response_to)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chat_id, role, content, json.dumps(metadata), tokens, response_to))
            
            message_id = cursor.lastrowid
            
            # Update chat timestamp
            conn.execute("UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (chat_id,))
            conn.commit()
            
            logger.debug(f"Added message {message_id} to chat {chat_id}: {role}")
            return message_id

    def get_messages(self, chat_id: int, limit: int = 100, after_id: int = None) -> List[Dict]:
        """Get messages for a chat"""
        with self.get_connection() as conn:
            if after_id:
                query = """
                    SELECT * FROM messages 
                    WHERE chat_id = ? AND id > ? 
                    ORDER BY created_at ASC 
                    LIMIT ?
                """
                rows = conn.execute(query, (chat_id, after_id, limit)).fetchall()
            else:
                query = """
                    SELECT * FROM messages 
                    WHERE chat_id = ? 
                    ORDER BY created_at ASC 
                    LIMIT ?
                """
                rows = conn.execute(query, (chat_id, limit)).fetchall()
            
            messages = []
            for row in rows:
                msg = dict(row)
                try:
                    msg['metadata'] = json.loads(msg['metadata']) if msg['metadata'] else {}
                except json.JSONDecodeError:
                    msg['metadata'] = {}
                messages.append(msg)
            
            return messages

    def get_context_messages(self, chat_id: int, max_tokens: int = 4000) -> List[Dict]:
        """Get messages for context with token budgeting"""
        messages = self.get_messages(chat_id)
        
        # Simple token budgeting - include newest messages that fit
        context_messages = []
        total_tokens = 0
        
        # Add messages in reverse order (newest first) until token limit
        for msg in reversed(messages):
            msg_tokens = msg['tokens'] or len(msg['content']) // 4  # Rough estimate
            if total_tokens + msg_tokens <= max_tokens:
                context_messages.insert(0, msg)
                total_tokens += msg_tokens
            else:
                break
                
        return context_messages

    def update_chat(self, chat_id: int, **kwargs) -> bool:
        """Update chat properties"""
        if not kwargs:
            return False
            
        # Build dynamic update query
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['title', 'model', 'provider', 'system_prompt', 'context_mode', 'summary']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
            
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(chat_id)
        
        with self.get_connection() as conn:
            query = f"UPDATE chats SET {', '.join(fields)} WHERE id = ?"
            conn.execute(query, values)
            conn.commit()
            return True

    def delete_chat(self, chat_id: int) -> bool:
        """Delete chat and all its messages"""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info(f"Deleted chat {chat_id}")
            return deleted

    def cleanup_temporary_chats(self, max_age_hours: int = 24):
        """Clean up old temporary chats"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM chats 
                WHERE is_temporary = 1 
                AND created_at < datetime('now', '-{} hours')
            """.format(max_age_hours))
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} temporary chats")
            return deleted

    def get_chat_stats(self) -> Dict:
        """Get database statistics"""
        with self.get_connection() as conn:
            stats = {}
            
            # Chat counts
            stats['total_chats'] = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
            stats['permanent_chats'] = conn.execute("SELECT COUNT(*) FROM chats WHERE is_temporary = 0").fetchone()[0]
            stats['temporary_chats'] = conn.execute("SELECT COUNT(*) FROM chats WHERE is_temporary = 1").fetchone()[0]
            
            # Message counts
            stats['total_messages'] = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            stats['user_messages'] = conn.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'").fetchone()[0]
            stats['assistant_messages'] = conn.execute("SELECT COUNT(*) FROM messages WHERE role = 'assistant'").fetchone()[0]
            
            return stats
