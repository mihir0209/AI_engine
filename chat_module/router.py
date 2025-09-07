"""
FastAPI router for chat functionality
"""
import asyncio
import json
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .db import ChatDB
from .websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Global engine instance - will be set by server
_global_engine = None

def set_global_engine(engine):
    """Set the global AI_engine instance to avoid creating duplicates"""
    global _global_engine
    _global_engine = engine

def get_global_engine():
    """Get the global AI_engine instance, create new one if not set"""
    global _global_engine
    if _global_engine is not None:
        return _global_engine
    
    # Fallback: create new instance (for backward compatibility)
    # Import here to avoid circular imports and reduce import-time side effects
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from ai_engine import AI_engine
    return AI_engine()

# Pydantic models for API
class CreateChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    model: Optional[str] = None
    provider: Optional[str] = None
    system_prompt: Optional[str] = None
    is_temporary: bool = False
    force_provider: bool = False  # New field to force specific provider usage

class SendMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|system)$")
    content: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UpdateChatRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    system_prompt: Optional[str] = None
    force_provider: Optional[bool] = None  # New field to update force provider setting

class ChatResponse(BaseModel):
    id: int
    title: str
    model: Optional[str]
    provider: Optional[str]
    system_prompt: Optional[str]
    context_mode: str
    summary: Optional[str]
    is_temporary: bool
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

# Initialize components
chat_db = ChatDB()
websocket_manager = WebSocketManager()

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
            force_provider=request.force_provider
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
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        
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
                "type": "error",
                "message": "Chat not found"
            }))
            return
        
        # Add user message
        user_message_id = chat_db.add_message(
            chat_id=chat_id,
            role="user",
            content=message_data["content"],
            metadata=message_data.get("metadata", {})
        )
        
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
        # Import ai_engine here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        
        # Get context messages
        context_messages = chat_db.get_context_messages(chat_id)
        
        # Format messages for AI Engine
        formatted_messages = []
        for msg in context_messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Use global AI Engine instance
        ai = get_global_engine()
        
        # Get response with correct parameter names and forced provider usage
        start_time = time.time()
        
        # Determine autodecide behavior and force provider based on chat settings
        chat = chat_db.get_chat(chat_id)
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
            # Save assistant message
            chat_db.add_message(
                chat_id=chat_id,
                role="assistant",
                content=result.content,
                metadata={
                    "provider": result.provider_used,
                    "model": result.model_used,
                    "response_time": response_time,
                    "timestamp": datetime.now().isoformat()
                },
                tokens=len(result.content) // 4,  # Rough estimate
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
        # Save error message
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
        # Import ai_engine here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))

        # Get context messages
        context_messages = chat_db.get_context_messages(chat_id)

        # Format messages for AI Engine
        formatted_messages = [{"role": msg["role"], "content": msg["content"]} for msg in context_messages]

        # Get chat settings for force provider
        chat = chat_db.get_chat(chat_id)
        force_provider_setting = chat.get('force_provider', False) if chat else False

        # Immediate client update so UI knows we're processing
        await websocket.send_text(json.dumps({"type": "ai_thinking", "provider": provider, "model": model}))

        ai = get_global_engine()
        logger.info(f"Starting threaded AI call for chat={chat_id} user_msg={user_message_id} provider={provider} model={model} force={force_provider_setting}")

        # Determine autodecide behavior and force provider based on chat settings
        use_autodecide = provider is None and not force_provider_setting

        # Start AI call in thread with correct parameter names
        ai_task = asyncio.create_task(asyncio.to_thread(ai.chat_completion, 
            messages=formatted_messages, 
            model=model, 
            autodecide=use_autodecide,
            preferred_provider=provider,
            force_provider=force_provider_setting and provider is not None
        ))

        # Keepalive loop while AI call runs
        keepalive_interval = 5.0
        last_keepalive = time.time()
        timeout = 120.0
        start_time = time.time()

        while not ai_task.done():
            now = time.time()
            if now - last_keepalive >= keepalive_interval:
                try:
                    await websocket.send_text(json.dumps({"type": "ai_typing_keepalive"}))
                except Exception:
                    logger.warning(f"Failed to send keepalive for chat {chat_id}")
                    # If we can't reach the client, cancel the AI task and persist an error
                    try:
                        ai_task.cancel()
                    except Exception:
                        logger.exception("Failed to cancel AI task after keepalive failure")
                    try:
                        await websocket.send_text(json.dumps({"type": "ai_error", "content": "Client disconnected or send failed"}))
                    except Exception:
                        # ignore, we're already in a failure path
                        pass
                    chat_db.add_message(chat_id=chat_id, role="assistant", content="Error: client disconnected during processing", metadata={"error": True})
                    return
                last_keepalive = now

            if now - start_time > timeout:
                logger.error(f"AI call timed out for chat {chat_id}")
                ai_task.cancel()
                try:
                    await websocket.send_text(json.dumps({"type": "ai_error", "content": "AI provider timed out"}))
                except Exception:
                    pass
                chat_db.add_message(chat_id=chat_id, role="assistant", content="Error: AI provider timed out", metadata={"error": True})
                return

            await asyncio.sleep(0.25)

        # Retrieve result (defensive: ensure task completed)
        if not ai_task.done():
            logger.error(f"AI task not completed for chat {chat_id} when expected; cancelling")
            try:
                ai_task.cancel()
            except Exception:
                pass
            try:
                await websocket.send_text(json.dumps({"type": "ai_error", "content": "AI call did not complete"}))
            except Exception:
                pass
            chat_db.add_message(chat_id=chat_id, role="assistant", content="Error: AI call did not complete", metadata={"error": True})
            return

        try:
            result = ai_task.result()
        except asyncio.CancelledError:
            logger.error(f"AI task cancelled for chat {chat_id}")
            try:
                await websocket.send_text(json.dumps({"type": "ai_error", "content": "AI call cancelled"}))
            except Exception:
                pass
            return
        except Exception as e:
            logger.exception(f"AI call raised exception for chat {chat_id}: {e}")
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

            # Stream response content
            chunk_size = 10
            for i in range(0, len(response_content), chunk_size):
                chunk = response_content[i:i+chunk_size]
                await websocket.send_text(json.dumps({"type": "ai_chunk", "content": chunk, "is_final": i + chunk_size >= len(response_content)}))
                await asyncio.sleep(0.02)

            # Persist assistant message
            assistant_message_id = chat_db.add_message(
                chat_id=chat_id,
                role="assistant",
                content=response_content,
                metadata={"provider": provider_used, "model": model_used, "response_time": response_time, "timestamp": datetime.now().isoformat()},
                tokens=(len(response_content) // 4) if response_content else 0,
                response_to=user_message_id
            )

            # Notify client of completion
            await websocket.send_text(json.dumps({"type": "ai_complete", "message_id": assistant_message_id, "provider": provider_used, "model": model_used, "response_time": response_time}))
        else:
            error_msg = getattr(result, 'error_message', 'Unknown error') if result is not None else 'AI call failed'
            logger.error(f"AI returned error for chat {chat_id}: {error_msg}")
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
