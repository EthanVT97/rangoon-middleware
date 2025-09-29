from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import asyncio
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        # Send connection confirmation
        await self.send_personal_message({
            "type": "connection_established",
            "message": "WebSocket connection established",
            "timestamp": datetime.now().isoformat()
        }, user_id)
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Send message to specific user"""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)
            
            # Remove broken connections
            for connection in disconnected:
                self.disconnect(connection, user_id)
    
    async def broadcast_job_update(self, job_data: dict, user_id: str):
        """Broadcast job update to specific user"""
        message = {
            "type": "job_update",
            "data": job_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal_message(message, user_id)
    
    async def broadcast_progress_update(self, job_id: str, progress: dict, user_id: str):
        """Broadcast progress update"""
        message = {
            "type": "progress_update",
            "job_id": job_id,
            "progress": progress,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal_message(message, user_id)
    
    async def broadcast_error(self, error_data: dict, user_id: str):
        """Broadcast error to specific user"""
        message = {
            "type": "error",
            "data": error_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal_message(message, user_id)
    
    async def broadcast_system_message(self, message: str, user_id: str):
        """Broadcast system message"""
        message_data = {
            "type": "system_message",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal_message(message_data, user_id)
    
    def get_connected_users(self) -> List[str]:
        """Get list of connected user IDs"""
        return list(self.active_connections.keys())
    
    def get_connection_count(self, user_id: str) -> int:
        """Get number of connections for a user"""
        return len(self.active_connections.get(user_id, []))

# Global WebSocket manager
websocket_manager = ConnectionManager()
