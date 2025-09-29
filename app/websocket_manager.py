from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except:
                    # Remove broken connection
                    self.disconnect(connection, user_id)
    
    async def broadcast_job_update(self, job_data: dict, user_id: str):
        """Broadcast job update to specific user"""
        message = {
            "type": "job_update",
            "data": job_data
        }
        await self.send_personal_message(json.dumps(message), user_id)
    
    async def broadcast_error(self, error_data: dict, user_id: str):
        """Broadcast error to specific user"""
        message = {
            "type": "error",
            "data": error_data
        }
        await self.send_personal_message(json.dumps(message), user_id)

# Global WebSocket manager
websocket_manager = ConnectionManager()
