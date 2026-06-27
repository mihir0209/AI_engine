"""
FastAPI router for chat functionality
"""
import asyncio
import base64
import json
import logging
import time
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, Field

from .db import ChatDB
from .websocket_manager import WebSocketManager
from config import verbose_print

logger = logging.getLogger(__name__)

IMAGE_REF_PATTERN = r'!\[([^\]]*)\]\(([^)]+)\)'
FILE_REF_PATTERN = r'\[File: ([^\]]+)\]\(([^)]+)\)'

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.txt', '.md', '.json', '.csv', '.py', '.js', '.ts', '.html', '.css', '.yaml', '.yml', '.xml'}
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

# Global engine instance - will be set by server
_global_engine = None

def set_global_engine(engine):
    global _global_engine
    _global_engine = engine

def get_global_engine():
    global _global_engine
    if _global_engine is not None:
        return _global_engine
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from core.ai_engine import AI_engine
    return AI_engine()

# Initialize components
chat_db = ChatDB()
websocket_manager = WebSocketManager()

import re

MIME_MAP = {
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.gif': 'image/gif', '.webp': 'image/webp',
}

def _read_file_content(file_path: str, max_chars: int = 8000) -> str:
    """Read content of an uploaded text file for AI context"""
    try:
        from pathlib import Path
        p = Path(file_path)
        if not p.exists():
            return "[File not found]"
        ext = p.suffix.lower()
        if ext in MIME_MAP:
            return "[Image file - cannot read as text]"
        content = p.read_text(encoding='utf-8', errors='replace')
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n... (truncated, {len(content)} total chars)"
        return content
    except Exception:
        return "[Could not read file]"

def _encode_image_base64(file_path: str) -> tuple:
    """Encode an image file to base64 data URI. Returns (data_uri, mime_type) or (None, None)"""
    try:
        from pathlib import Path
        p = Path(file_path)
        if not p.exists():
            return None, None
        ext = p.suffix.lower()
        mime = MIME_MAP.get(ext, 'image/png')
        data = p.read_bytes()
        b64 = base64.b64encode(data).decode('utf-8')
        return f"data:{mime};base64,{b64}", mime
    except Exception:
        return None, None

def _prepare_messages_for_ai(formatted_messages: list, provider: str, model: str = None) -> tuple:
    """Prepare messages for AI: handle file content injection, image encoding, and vision stripping.
    Returns (messages, has_images, vision_warning)
    """
    from core.capabilities import capability_manager
    vision_ok = capability_manager.supports_vision(provider or '', model)

    has_images = any(re.search(IMAGE_REF_PATTERN, msg.get('content', '')) for msg in formatted_messages)
    has_files = any(re.search(FILE_REF_PATTERN, msg.get('content', '')) for msg in formatted_messages)

    if not has_images and not has_files:
        return formatted_messages, False, None

    processed = []
    for msg in formatted_messages:
        content = msg.get('content', '')

        # Inject file contents for text files
        file_matches = list(re.finditer(FILE_REF_PATTERN, content))
        if file_matches:
            for match in reversed(file_matches):
                file_url = match.group(2)
                file_path = file_url.lstrip('/')
                text_content = _read_file_content(file_path)
                placeholder = match.group(0)
                content = content.replace(placeholder, f"{placeholder}\n\n```\n{text_content}\n```")

        # Handle images
        image_matches = list(re.finditer(IMAGE_REF_PATTERN, content))
        if image_matches:
            if vision_ok:
                # Encode images as base64 for vision models
                for match in reversed(image_matches):
                    file_url = match.group(2)
                    file_path = file_url.lstrip('/')
                    data_uri, mime = _encode_image_base64(file_path)
                    if data_uri:
                        alt_text = match.group(1) or 'uploaded image'
                        img_md = match.group(0)
                        replacement = f"![{alt_text}]({data_uri})"
                        content = content.replace(img_md, replacement)
            else:
                # Strip images for non-vision models
                for match in reversed(image_matches):
                    img_md = match.group(0)
                    content = content.replace(img_md, '[Image attached - not supported by current model]')
                vision_providers = capability_manager.get_vision_providers()
                warning = f"Images removed: {provider or 'current provider'} does not support vision. Use: {', '.join(vision_providers[:3])}"
                processed.append({**msg, 'content': content})
                return processed, True, warning

        processed.append({**msg, 'content': content})

    return processed, has_images, None

# Pydantic models for API
class CreateChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    model: Optional[str] = None
    provider: Optional[str] = None
    system_prompt: Optional[str] = None
    is_temporary: bool = False
    force_provider: bool = False
    temporary_timer_minutes: int = Field(default=5, ge=1, le=60)

class SendMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|system)$")
    content: str = Field(..., min_length=1, max_length=100000)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EditMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    chat_id: Optional[int] = None
    limit: int = Field(default=50, ge=1, le=200)

class UpdateChatRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    system_prompt: Optional[str] = None
    force_provider: Optional[bool] = None

class ChatResponse(BaseModel):
    id: int
    title: str
    model: Optional[str]
    provider: Optional[str]
    system_prompt: Optional[str]
    context_mode: str
    summary: Optional[str]
    is_temporary: bool
    temporary_timer_minutes: int
    force_provider: bool
    created_at: str
    updated_at: str
    message_count: Optional[int] = None
    last_message: Optional[str] = None

class MessageResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    metadata: Dict[str, Any]
    tokens: int
    created_at: str
    response_to: Optional[int]

# Background task for cleaning up temporary chats
_cleanup_running = True

async def cleanup_expired_temporary_chats():
    """Background task to delete temporary chats after their configured timer expires"""
    global _cleanup_running
    while _cleanup_running:
        try:
            expired_chats = chat_db.get_expired_temporary_chats()

            for chat in expired_chats:
                chat_id = chat['id']
                timer_minutes = chat.get('temporary_timer_minutes', 5)
                verbose_print(f"Auto-deleting expired temporary chat {chat_id} (timer: {timer_minutes} minutes)")

                # Delete the chat from database
                success = chat_db.delete_chat(chat_id)

                if success:
                    # Notify all connected clients via WebSocket
                    await websocket_manager.notify_chat_deleted(chat_id)
                    verbose_print(f"Successfully auto-deleted temporary chat {chat_id}")
                else:
                    verbose_print(f"Failed to auto-delete temporary chat {chat_id}")

        except Exception as e:
            logger.error(f"Error in cleanup_expired_temporary_chats: {e}")

        # Sleep for 30 seconds before next check
        await asyncio.sleep(30)

# Start the cleanup task
cleanup_task = None

def start_cleanup_task():
    """Start the background cleanup task"""
    global cleanup_task
    if cleanup_task is None:
        cleanup_task = asyncio.create_task(cleanup_expired_temporary_chats())

def stop_cleanup_task():
    """Stop the background cleanup task (for clean shutdown/testing)"""
    global _cleanup_running, cleanup_task
    _cleanup_running = False
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
    cleanup_task = None

# Create router
router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.get("/chats", response_model=List[ChatResponse])
async def get_chats(include_temporary: bool = False, limit: int = 50):
    """Get list of chats"""
    try:
        chats = chat_db.get_chats(include_temporary=include_temporary, limit=limit)
        return [ChatResponse(**chat) for chat in chats]
    except Exception as e:
        logger.error(f"Error getting chats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chats")

@router.post("/chats", response_model=Dict[str, Any])
async def create_chat(request: CreateChatRequest):
    """Create a new chat"""
    try:
        chat_id = chat_db.create_chat(
            title=request.title,
            model=request.model,
            provider=request.provider,
            system_prompt=request.system_prompt,
            is_temporary=request.is_temporary,
            force_provider=request.force_provider,
            temporary_timer_minutes=request.temporary_timer_minutes
        )

        chat = chat_db.get_chat(chat_id)
        return {
            "success": True,
            "chat_id": chat_id,
            "chat": ChatResponse(**chat)
        }
    except Exception as e:
        logger.error(f"Error creating chat: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chat")

@router.get("/chats/{chat_id}", response_model=Dict[str, Any])
async def get_chat(chat_id: int, limit: int = 100):
    """Get chat with messages"""
    try:
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        messages = chat_db.get_messages(chat_id, limit=limit)

        return {
            "chat": ChatResponse(**chat),
            "messages": [MessageResponse(**msg) for msg in messages]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat")

@router.post("/chats/{chat_id}/messages", response_model=Dict[str, Any])
async def send_message(chat_id: int, request: SendMessageRequest, background_tasks: BackgroundTasks):
    """Send a message to a chat"""
    try:
        # Verify chat exists
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Add user message immediately
        message_id = chat_db.add_message(
            chat_id=chat_id,
            role=request.role,
            content=request.content,
            metadata=request.metadata
        )

        # If it's a user message, trigger AI response
        if request.role == "user":
            background_tasks.add_task(
                process_ai_response,
                chat_id=chat_id,
                user_message_id=message_id,
                model=chat.get('model'),
                provider=chat.get('provider')
            )

        return {
            "success": True,
            "message_id": message_id,
            "status": "queued" if request.role == "user" else "saved"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message to chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

@router.put("/chats/{chat_id}", response_model=Dict[str, Any])
async def update_chat(chat_id: int, request: UpdateChatRequest):
    """Update chat properties"""
    try:
        # Verify chat exists
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Update with non-None values
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if update_data:
            success = chat_db.update_chat(chat_id, **update_data)
            if not success:
                raise HTTPException(status_code=400, detail="No valid fields to update")

        updated_chat = chat_db.get_chat(chat_id)
        return {
            "success": True,
            "chat": ChatResponse(**updated_chat)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update chat")

@router.post("/chats/{chat_id}/convert-to-permanent")
async def convert_chat_to_permanent(chat_id: int, new_title: Optional[str] = None):
    """Convert a temporary chat to permanent"""
    try:
        # Verify chat exists and is temporary
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        if not chat['is_temporary']:
            raise HTTPException(status_code=400, detail="Chat is already permanent")

        # Convert to permanent
        success = chat_db.convert_chat_to_permanent(chat_id, new_title)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to convert chat")

        # Get updated chat
        updated_chat = chat_db.get_chat(chat_id)
        return {
            "success": True,
            "message": "Chat converted to permanent",
            "chat": ChatResponse(**updated_chat)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting chat {chat_id} to permanent: {e}")
        raise HTTPException(status_code=500, detail="Failed to convert chat")

@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: int):
    """Delete a chat"""
    try:
        success = chat_db.delete_chat(chat_id)
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")

        return {"success": True, "message": "Chat deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chat")

@router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: int, limit: int = 100, after_id: Optional[int] = None):
    """Get messages for a chat"""
    try:
        # Verify chat exists
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        messages = chat_db.get_messages(chat_id, limit=limit, after_id=after_id)
        return [MessageResponse(**msg) for msg in messages]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages for chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")

@router.get("/stats")
async def get_stats():
    """Get chat statistics"""
    try:
        stats = chat_db.get_chat_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

@router.put("/messages/{message_id}")
async def edit_message(message_id: int, request: EditMessageRequest):
    """Edit a message's content"""
    try:
        message = chat_db.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        success = chat_db.edit_message(message_id, request.content)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to edit message")

        updated_message = chat_db.get_message(message_id)
        return {"success": True, "message": MessageResponse(**updated_message)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to edit message")

@router.post("/chats/{chat_id}/regenerate/{message_id}")
async def regenerate_response(chat_id: int, message_id: int, background_tasks: BackgroundTasks):
    """Regenerate assistant response from a specific user message"""
    try:
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        message = chat_db.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        if message['role'] != 'user':
            raise HTTPException(status_code=400, detail="Can only regenerate from user messages")

        # Delete messages after this one
        deleted_count = chat_db.delete_messages_after(chat_id, message_id)

        # Trigger new AI response
        background_tasks.add_task(
            process_ai_response,
            chat_id=chat_id,
            user_message_id=message_id,
            model=chat.get('model'),
            provider=chat.get('provider')
        )

        return {
            "success": True,
            "message": f"Regenerating response (deleted {deleted_count} messages)",
            "deleted_count": deleted_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating response for chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to regenerate response")

@router.post("/search")
async def search_messages(request: SearchRequest):
    """Search messages across chats"""
    try:
        messages = chat_db.search_messages(
            query=request.query,
            chat_id=request.chat_id,
            limit=request.limit
        )
        return {
            "success": True,
            "query": request.query,
            "results": [MessageResponse(**msg) for msg in messages],
            "total": len(messages)
        }
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to search messages")

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), chat_id: Optional[int] = None):
    """Upload a file (text or image)"""
    try:
        # Check file size
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")

        # Get file extension
        file_ext = Path(file.filename).suffix.lower() if file.filename else ""

        # Validate file type
        all_allowed = ALLOWED_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS
        if file_ext not in all_allowed:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{file_ext}' not allowed. Allowed: {', '.join(sorted(all_allowed))}"
            )

        # Generate unique filename
        file_hash = hashlib.md5(content).hexdigest()[:8]
        safe_filename = f"{file_hash}_{int(time.time())}{file_ext}"
        file_path = UPLOAD_DIR / safe_filename

        # Save file
        with open(file_path, "wb") as f:
            f.write(content)

        # Determine file type
        is_image = file_ext in ALLOWED_IMAGE_EXTENSIONS
        file_type = "image" if is_image else "document"

        # Read content for text files
        file_content = None
        if not is_image and file_ext in ALLOWED_EXTENSIONS:
            try:
                file_content = content.decode('utf-8')
            except UnicodeDecodeError:
                file_content = None

        result = {
            "success": True,
            "filename": file.filename,
            "saved_as": safe_filename,
            "path": str(file_path),
            "size": len(content),
            "type": file_type,
            "extension": file_ext
        }

        # If chat_id provided, add file reference as message
        if chat_id:
            chat = chat_db.get_chat(chat_id)
            if chat:
                file_url = f"/uploads/{safe_filename}"
                file_ref = f"[File: {file.filename}]({file_url})"
                if is_image:
                    file_ref = f"![{file.filename}]({file_url})"

                metadata = {
                    "file_upload": True,
                    "filename": file.filename,
                    "file_path": str(file_path),
                    "file_url": file_url,
                    "file_type": file_type,
                    "file_size": len(content)
                }

                msg_id = chat_db.add_message(
                    chat_id=chat_id,
                    role="user",
                    content=file_ref,
                    metadata=metadata
                )
                result["message_id"] = msg_id

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")

@router.get("/uploads/{filename}")
async def get_upload(filename: str):
    """Get uploaded file info"""
    # Security: prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = UPLOAD_DIR / filename
    if not file_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    stat = file_path.stat()
    file_ext = file_path.suffix.lower()

    return {
        "filename": filename,
        "path": str(file_path),
        "size": stat.st_size,
        "type": "image" if file_ext in ALLOWED_IMAGE_EXTENSIONS else "document",
        "extension": file_ext,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
    }

@router.post("/chats/{chat_id}/branch/{message_id}")
async def create_branch(chat_id: int, message_id: int):
    """Create a new branch from a specific message"""
    try:
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        new_branch_id = chat_db.create_branch(chat_id, message_id)

        return {
            "success": True,
            "branch_id": new_branch_id,
            "message": f"Created branch {new_branch_id} from message {message_id}"
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating branch for chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create branch")

@router.get("/chats/{chat_id}/branches")
async def get_branches(chat_id: int):
    """Get all branches for a chat"""
    try:
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        branches = chat_db.get_branches(chat_id)
        return {"success": True, "branches": branches}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting branches for chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get branches")

@router.get("/chats/{chat_id}/branches/{branch_id}")
async def get_branch_messages(chat_id: int, branch_id: int):
    """Get messages for a specific branch"""
    try:
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        messages = chat_db.get_branch_messages(chat_id, branch_id)
        return {"success": True, "branch_id": branch_id, "messages": [MessageResponse(**msg) for msg in messages]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting branch messages for chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get branch messages")

@router.post("/chats/{chat_id}/branches/{branch_id}/switch")
async def switch_branch(chat_id: int, branch_id: int):
    """Switch to a different branch"""
    try:
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        success = chat_db.switch_branch(chat_id, branch_id)
        return {"success": success, "message": f"Switched to branch {branch_id}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching branch for chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to switch branch")

@router.get("/chats/{chat_id}/export")
async def export_chat(chat_id: int, format: str = "markdown"):
    """Export chat conversation in Markdown or JSON format"""
    try:
        chat = chat_db.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        messages = chat_db.get_messages(chat_id, limit=1000)

        if format == "json":
            return {
                "chat": {
                    "id": chat["id"],
                    "title": chat["title"],
                    "model": chat.get("model"),
                    "provider": chat.get("provider"),
                    "created_at": chat.get("created_at"),
                    "updated_at": chat.get("updated_at")
                },
                "messages": [
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                        "created_at": msg.get("created_at"),
                        "metadata": msg.get("metadata", {})
                    }
                    for msg in messages
                ]
            }
        else:  # markdown
            lines = [f"# {chat['title']}\n"]
            lines.append(f"*Model: {chat.get('model', 'auto')} | Provider: {chat.get('provider', 'auto')}*\n")
            lines.append("---\n")

            for msg in messages:
                role = msg["role"].capitalize()
                content = msg["content"]
                lines.append(f"**{role}:**\n{content}\n")

            return {"export": "\n".join(lines), "format": "markdown"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting chat {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to export chat")

@router.websocket("/chats/{chat_id}/stream")
async def websocket_endpoint(websocket: WebSocket, chat_id: int):
    """WebSocket endpoint for real-time chat streaming"""
    await websocket_manager.connect(websocket, chat_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "user_message":
                await handle_websocket_message(websocket, chat_id, message_data)
            elif message_data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, chat_id)
    except Exception as e:
        logger.error(f"WebSocket error for chat {chat_id}: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
        websocket_manager.disconnect(websocket, chat_id)

async def handle_websocket_message(websocket: WebSocket, chat_id: int, message_data: Dict):
    """Handle incoming WebSocket message"""
    try:
        # Verify chat exists
        chat = chat_db.get_chat(chat_id)
        if not chat:
            await websocket.send_text(json.dumps({
                "type": "chat_deleted",
                "message": "Chat no longer exists"
            }))
            await websocket.close()
            return

        # Add user message
        try:
            user_message_id = chat_db.add_message(
                chat_id=chat_id,
                role="user",
                content=message_data["content"],
                metadata=message_data.get("metadata", {})
            )
        except ValueError as e:
            if "does not exist" in str(e) or "was deleted" in str(e):
                await websocket.send_text(json.dumps({
                    "type": "chat_deleted",
                    "message": "Chat was deleted while sending message"
                }))
                await websocket.close()
                return
            raise

        # Send confirmation
        await websocket.send_text(json.dumps({
            "type": "message_saved",
            "message_id": user_message_id
        }))

        # Process AI response with streaming
        await process_ai_response_stream(
            websocket=websocket,
            chat_id=chat_id,
            user_message_id=user_message_id,
            model=message_data.get('model') or chat.get('model'),
            provider=message_data.get('provider') or chat.get('provider')
        )

    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))

async def process_ai_response(chat_id: int, user_message_id: int, model: str = None, provider: str = None):
    """Process AI response in background (for REST API)"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

        chat = chat_db.get_chat(chat_id)
        context_messages = chat_db.get_context_messages(chat_id)

        formatted_messages = []
        if chat and chat.get('system_prompt'):
            formatted_messages.append({"role": "system", "content": chat['system_prompt']})
        for msg in context_messages:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})

        formatted_messages, has_images, vision_warning = _prepare_messages_for_ai(
            formatted_messages, provider, model)

        ai = get_global_engine()
        start_time = time.time()

        force_provider_setting = chat.get('force_provider', False) if chat else False
        use_autodecide = provider is None and not force_provider_setting

        result = await asyncio.to_thread(ai.chat_completion,
            messages=formatted_messages,
            model=model,
            autodecide=use_autodecide,
            preferred_provider=provider,
            force_provider=force_provider_setting and provider is not None
        )
        response_time = time.time() - start_time

        if result.success:
            metadata = {
                "provider": result.provider_used,
                "model": result.model_used,
                "response_time": response_time,
                "timestamp": datetime.now().isoformat()
            }
            if vision_warning:
                metadata["vision_warning"] = vision_warning
            chat_db.add_message(
                chat_id=chat_id,
                role="assistant",
                content=result.content,
                metadata=metadata,
                tokens=len(result.content) // 4,
                response_to=user_message_id
            )
        else:
            # Save error message
            chat_db.add_message(
                chat_id=chat_id,
                role="assistant",
                content=f"Error: {result.error_message or 'Unknown error occurred'}",
                metadata={
                    "error": True,
                    "provider": provider,
                    "model": model,
                    "response_time": response_time
                },
                response_to=user_message_id
            )

    except Exception as e:
        logger.error(f"Error processing AI response for chat {chat_id}: {e}")
        chat_db.add_message(
            chat_id=chat_id,
            role="assistant",
            content=f"System Error: {str(e)}",
            metadata={"error": True, "system_error": True},
            response_to=user_message_id
        )

async def process_ai_response_stream(websocket: WebSocket, chat_id: int, user_message_id: int,
                                     model: str = None, provider: str = None):
    """Process AI response with streaming (for WebSocket).

    Offloads the AI call to a thread, sends periodic typing keepalives so the client
    sees progress, enforces a timeout, streams chunks when the call completes, and
    persists the assistant message.
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

        context_messages = chat_db.get_context_messages(chat_id)
        chat = chat_db.get_chat(chat_id)

        formatted_messages = []
        if chat and chat.get('system_prompt'):
            formatted_messages.append({"role": "system", "content": chat['system_prompt']})
        for msg in context_messages:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})

        formatted_messages, has_images, vision_warning = _prepare_messages_for_ai(
            formatted_messages, provider, model)

        force_provider_setting = chat.get('force_provider', False) if chat else False

        if vision_warning:
            await websocket.send_text(json.dumps({"type": "vision_warning", "message": vision_warning}))

        await websocket.send_text(json.dumps({"type": "ai_thinking", "provider": provider, "model": model}))

        ai = get_global_engine()
        verbose_print(f"Starting AI call for chat={chat_id} user_msg={user_message_id} provider={provider} model={model} force={force_provider_setting}")

        use_autodecide = provider is None and not force_provider_setting

        # Use non-streaming completion + simulated chunking (reliable across all providers)
        start_time = time.time()
        try:
            result = await asyncio.to_thread(ai.chat_completion,
                messages=formatted_messages,
                model=model,
                autodecide=use_autodecide,
                preferred_provider=provider,
                force_provider=force_provider_setting and provider is not None
            )
        except Exception as e:
            logger.exception(f"AI call exception for chat {chat_id}: {e}")
            try:
                await websocket.send_text(json.dumps({"type": "ai_error", "content": str(e)}))
            except Exception:
                pass
            chat_db.add_message(chat_id=chat_id, role="assistant", content=f"System Error: {str(e)}", metadata={"error": True})
            return

        response_time = time.time() - start_time

        if result and getattr(result, 'success', False):
            response_content = getattr(result, 'content', '')
            provider_used = getattr(result, 'provider_used', provider)
            model_used = getattr(result, 'model_used', model)

            # Stream content word by word for real-time feel
            words = response_content.split(' ')
            buffer = ""
            for word in words:
                buffer += (" " if buffer else "") + word
                await websocket.send_text(json.dumps({"type": "ai_chunk", "content": buffer + " ", "is_final": False}))
                buffer = ""
                await asyncio.sleep(0.01)

            # Send final empty chunk to signal completion
            await websocket.send_text(json.dumps({"type": "ai_chunk", "content": "", "is_final": True}))

            # Persist assistant message
            try:
                assistant_message_id = chat_db.add_message(
                    chat_id=chat_id,
                    role="assistant",
                    content=response_content,
                    metadata={"provider": provider_used, "model": model_used, "response_time": response_time, "timestamp": datetime.now().isoformat()},
                    tokens=(len(response_content) // 4) if response_content else 0,
                    response_to=user_message_id
                )
                await websocket.send_text(json.dumps({"type": "ai_complete", "message_id": assistant_message_id, "provider": provider_used, "model": model_used, "response_time": response_time}))
            except ValueError as e:
                if "does not exist" in str(e) or "was deleted" in str(e):
                    logger.warning(f"Chat {chat_id} was deleted while processing AI response")
                    await websocket.send_text(json.dumps({"type": "chat_deleted", "message": "Chat was deleted"}))
                    await websocket.close()
                    return
                raise
        else:
            error_msg = getattr(result, 'error_message', 'No response from provider') if result else 'No response from provider'
            logger.error(f"AI error for chat {chat_id}: {error_msg}")
            try:
                await websocket.send_text(json.dumps({"type": "ai_error", "content": f"Error: {error_msg}"}))
            except Exception:
                pass
            chat_db.add_message(chat_id=chat_id, role="assistant", content=f"Error: {error_msg}", metadata={"error": True}, response_to=user_message_id)

    except Exception as e:
        logger.exception(f"Error processing AI response stream for chat {chat_id}: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "ai_error", "content": f"System Error: {str(e)}"}))
        except Exception:
            pass
        chat_db.add_message(chat_id=chat_id, role="assistant", content=f"System Error: {str(e)}", metadata={"error": True, "system_error": True}, response_to=user_message_id)
