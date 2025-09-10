"""
WebSocket connection manager for chat functionality
"""
import json
import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Dictionary to store active connections by chat_id
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, chat_id: int):
        """Accept WebSocket connection and add to chat room"""
        await websocket.accept()
        
        if chat_id not in self.active_connections:
            self.active_connections[chat_id] = []
        
        self.active_connections[chat_id].append(websocket)
        logger.info(f"WebSocket connected to chat {chat_id}")

    def disconnect(self, websocket: WebSocket, chat_id: int):
        """Remove WebSocket connection from chat room"""
        if chat_id in self.active_connections:
            try:
                self.active_connections[chat_id].remove(websocket)
                if not self.active_connections[chat_id]:
                    del self.active_connections[chat_id]
                logger.info(f"WebSocket disconnected from chat {chat_id}")
            except ValueError:
                # WebSocket was not in the list
                pass

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast_to_chat(self, message: str, chat_id: int):
        """Send message to all connections in a chat room"""
        if chat_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[chat_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to chat {chat_id}: {e}")
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for connection in disconnected:
                self.disconnect(connection, chat_id)

    async def send_typing_indicator(self, chat_id: int, is_typing: bool = True):
        """Send typing indicator to chat room"""
        message = json.dumps({
            "type": "typing_indicator",
            "is_typing": is_typing
        })
        await self.broadcast_to_chat(message, chat_id)

    async def notify_chat_deleted(self, chat_id: int):
        """Notify all clients that a chat has been deleted and close connections to that chat"""
        # First, handle connections specifically for this chat
        if chat_id in self.active_connections:
            connections = self.active_connections[chat_id].copy()  # Copy to avoid modification during iteration
            for connection in connections:
                try:
                    await connection.send_text(json.dumps({
                        "type": "chat_deleted", 
                        "chat_id": chat_id, 
                        "message": "This chat has been automatically deleted"
                    }))
                    # Close the WebSocket connection
                    await connection.close()
                except Exception as e:
                    logger.error(f"Error notifying chat {chat_id} deletion: {e}")
            
            # Remove all connections for this chat
            del self.active_connections[chat_id]
            logger.info(f"Closed all WebSocket connections for deleted chat {chat_id}")
        
        # Broadcast to all other clients to update their chat lists
        message = json.dumps({
            "type": "chat_deleted",
            "chat_id": chat_id
        })
        await self.broadcast_to_all(message)

    async def broadcast_to_all(self, message: str):
        """Send message to all active connections across all chats"""
        disconnected = []
        for chat_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to all connections: {e}")
                    disconnected.append((connection, chat_id))
        
        # Remove disconnected connections
        for connection, chat_id in disconnected:
            self.disconnect(connection, chat_id)

    def get_connection_count(self, chat_id: int) -> int:
        """Get number of active connections for a chat"""
        return len(self.active_connections.get(chat_id, []))

    def get_total_connections(self) -> int:
        """Get total number of active connections"""
        return sum(len(connections) for connections in self.active_connections.values())

    def get_active_chats(self) -> List[int]:
        """Get list of chat IDs with active connections"""
        return list(self.active_connections.keys())
