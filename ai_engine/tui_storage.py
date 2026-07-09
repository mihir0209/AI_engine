"""
Persistent storage for the AI Synapse TUI chat sessions.

Layout:
    ~/.ai-engine/chatdata/
        meta.json          # session index, last cwd, active chat
        chats/
            <id>.json      # one file per conversation
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORAGE_VERSION = 2
CHATDATA_ROOT = Path.home() / ".ai-engine" / "chatdata"
META_FILE = CHATDATA_ROOT / "meta.json"
CHATS_DIR = CHATDATA_ROOT / "chats"

_lock = threading.Lock()


def _sanitize_export_filename(title: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", title or "chat").strip().lower()
    cleaned = re.sub(r"[-\s]+", "-", cleaned).strip("-")
    return cleaned[:48] or "chat"


def export_chat_markdown(
    chat: dict[str, Any],
    *,
    model: str = "default",
    provider: str | None = None,
) -> str:
    """Render a chat as Markdown (aligned with web export format)."""
    lines = [f"# {chat.get('title', 'Chat')}\n"]
    lines.append(f"*Model: {model} | Provider: {provider or 'auto'}*\n")
    system_prompt = (chat.get("system_prompt") or "").strip()
    if system_prompt:
        lines.append(f"*System:* {system_prompt}\n")
    lines.append("---\n")
    for msg in chat.get("messages", []):
        role = str(msg.get("role", "user")).capitalize()
        content = msg.get("content", "")
        if msg.get("_image_path"):
            name = os.path.basename(msg["_image_path"])
            content = f"{content}\n\n📎 {name}"
        lines.append(f"**{role}:**\n{content}\n")
    return "\n".join(lines)


def export_chat_json(
    chat: dict[str, Any],
    *,
    chat_id: int,
    model: str = "default",
    provider: str | None = None,
) -> dict[str, Any]:
    """Serialize a chat for JSON export."""
    messages = []
    for msg in chat.get("messages", []):
        entry: dict[str, Any] = {
            "role": msg.get("role"),
            "content": msg.get("content", ""),
        }
        if msg.get("_image_path"):
            entry["image_path"] = msg["_image_path"]
        messages.append(entry)
    return {
        "chat": {
            "id": chat_id,
            "title": chat.get("title", f"Chat {chat_id}"),
            "model": model,
            "provider": provider,
            "system_prompt": chat.get("system_prompt") or "",
            "created_at": chat.get("created_at"),
            "updated_at": chat.get("updated_at"),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        "messages": messages,
    }


def write_chat_export(
    chat: dict[str, Any],
    *,
    chat_id: int,
    path: str,
    fmt: str = "markdown",
    model: str = "default",
    provider: str | None = None,
) -> str:
    """Write chat export to disk. Returns the path written."""
    target = Path(path).expanduser()
    stem = _sanitize_export_filename(chat.get("title", f"chat-{chat_id}"))
    ext = "json" if fmt == "json" else "md"
    if target.suffix.lower() in {".md", ".json"}:
        final = target
    else:
        final = target / f"{stem}-{chat_id}.{ext}"
    final.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        payload = export_chat_json(
            chat, chat_id=chat_id, model=model, provider=provider
        )
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        text = export_chat_markdown(chat, model=model, provider=provider)
    tmp = final.with_suffix(final.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    tmp.replace(final)
    return str(final)


def _normalize_cwd(path: str | None) -> str:
    if not path:
        return os.getcwd()
    expanded = os.path.abspath(os.path.expanduser(path.strip()))
    if os.path.isfile(expanded):
        return os.path.dirname(expanded)
    return expanded


class ChatStorage:
    """Read/write TUI chat history under ~/.ai-engine/chatdata."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or CHATDATA_ROOT
        self.meta_file = self.root / "meta.json"
        self.chats_dir = self.root / "chats"

    def ensure_dirs(self) -> None:
        self.chats_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any] | None:
        """Load session state. Returns None when no saved data exists."""
        if not self.meta_file.exists():
            return None
        try:
            with open(self.meta_file, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        chats: dict[int, dict[str, Any]] = {}
        for raw_id in meta.get("chat_order", []):
            try:
                chat_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            chat_path = self.chats_dir / f"{chat_id}.json"
            if not chat_path.exists():
                continue
            try:
                with open(chat_path, encoding="utf-8") as f:
                    chats[chat_id] = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

        if not chats:
            return None

        chat_counter = int(meta.get("chat_counter", max(chats.keys(), default=0)))
        current_chat_id = int(meta.get("current_chat_id", max(chats.keys())))
        if current_chat_id not in chats:
            current_chat_id = max(chats.keys())

        return {
            "chats": chats,
            "chat_counter": chat_counter,
            "current_chat_id": current_chat_id,
            "chat_order": [int(x) for x in meta.get("chat_order", []) if int(x) in chats],
            "last_cwd": _normalize_cwd(meta.get("last_cwd")),
            "current_model": meta.get("current_model", "default"),
            "current_provider": meta.get("current_provider"),
            "intent_routing_enabled": bool(meta.get("intent_routing_enabled", True)),
            "_legacy_favorite_models": list(meta.get("favorite_models", [])),
        }

    def save_session(
        self,
        *,
        chats: dict[int, dict[str, Any]],
        chat_counter: int,
        current_chat_id: int,
        chat_order: list[int],
        last_cwd: str,
        current_model: str = "default",
        current_provider: str | None = None,
        intent_routing_enabled: bool = True,
    ) -> None:
        """Persist all chats and session metadata."""
        with _lock:
            self.ensure_dirs()
            now = time.time()

            active_ids = set(chats.keys())
            order = [cid for cid in chat_order if cid in active_ids]
            for cid in chats:
                if cid not in order:
                    order.append(cid)

            for chat_id, chat in chats.items():
                payload = {
                    "id": chat_id,
                    "title": chat.get("title", f"Chat {chat_id}"),
                    "messages": chat.get("messages", []),
                    "system_prompt": chat.get("system_prompt", ""),
                    "persona_id": chat.get("persona_id", ""),
                    "favorite": bool(chat.get("favorite", False)),
                    "created_at": chat.get("created_at", now),
                    "updated_at": now,
                }
                chat_path = self.chats_dir / f"{chat_id}.json"
                tmp_path = chat_path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                tmp_path.replace(chat_path)

            # Remove stale chat files no longer in memory
            if self.chats_dir.exists():
                for stale in self.chats_dir.glob("*.json"):
                    try:
                        stale_id = int(stale.stem)
                    except ValueError:
                        continue
                    if stale_id not in active_ids:
                        stale.unlink(missing_ok=True)

            meta = {
                "version": STORAGE_VERSION,
                "chat_counter": chat_counter,
                "current_chat_id": current_chat_id,
                "chat_order": order,
                "last_cwd": _normalize_cwd(last_cwd),
                "current_model": current_model,
                "current_provider": current_provider,
                "intent_routing_enabled": intent_routing_enabled,
                "saved_at": now,
            }
            tmp_meta = self.meta_file.with_suffix(".tmp")
            with open(tmp_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            tmp_meta.replace(self.meta_file)

    def save_last_cwd(self, path: str) -> str:
        """Update only last_cwd in meta (recent wins — single value)."""
        cwd = _normalize_cwd(path)
        with _lock:
            meta: dict[str, Any] = {"version": STORAGE_VERSION, "last_cwd": cwd}
            if self.meta_file.exists():
                try:
                    with open(self.meta_file, encoding="utf-8") as f:
                        meta = json.load(f)
                except (OSError, json.JSONDecodeError):
                    pass
            meta["last_cwd"] = cwd
            self.ensure_dirs()
            tmp_meta = self.meta_file.with_suffix(".tmp")
            with open(tmp_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            tmp_meta.replace(self.meta_file)
        return cwd