import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from collections import defaultdict, deque
import uuid

from fastapi import WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from decouple import config

from .models import WebSocketMessage, WebSocketMessageType, ProgressUpdate
from .auth import auth_handler

# Configure logging
logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"

class ConnectionMetadata:
    """Metadata for WebSocket connections"""
    
    def __init__(self, websocket: WebSocket, user_id: str, user_role: str):
        self.websocket = websocket
        self.user_id = user_id
        self.user_role = user_role
        self.connection_id = str(uuid.uuid4())
        self.state = ConnectionState.CONNECTING
        self.connected_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.last_activity = datetime.now()
        self.message_count = 0
        self.reconnect_attempts = 0
        self.subscriptions: Set[str] = set()
        
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
        self.message_count += 1
    
    def update_heartbeat(self):
        """Update heartbeat timestamp"""
        self.last_heartbeat = datetime.now()
    
    def is_alive(self, timeout: int = 30) -> bool:
        """Check if connection is still alive"""
        return (datetime.now() - self.last_heartbeat).total_seconds() < timeout
    
    def can_reconnect(self, max_attempts: int = 5, timeout: int = 300) -> bool:
        """Check if reconnection is allowed"""
        if self.reconnect_attempts >= max_attempts:
            reconnect_timeout = (datetime.now() - self.connected_at).total_seconds()
            return reconnect_timeout < timeout
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "connection_id": self.connection_id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "state": self.state.value,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": self.message_count,
            "subscriptions": list(self.subscriptions)
        }

class RateLimiter:
    """Rate limiting for WebSocket messages"""
    
    def __init__(self, max_messages: int = 100, time_window: int = 60):
        self.max_messages = max_messages
        self.time_window = time_window
        self.message_history: Dict[str, deque] = {}
    
    def is_allowed(self, connection_id: str) -> bool:
        """Check if message is allowed under rate limit"""
        now = time.time()
        
        if connection_id not in self.message_history:
            self.message_history[connection_id] = deque()
        
        # Remove old messages outside the time window
        while (self.message_history[connection_id] and 
               self.message_history[connection_id][0] < now - self.time_window):
            self.message_history[connection_id].popleft()
        
        # Check if under limit
        if len(self.message_history[connection_id]) < self.max_messages:
            self.message_history[connection_id].append(now)
            return True
        
        return False
    
    def cleanup_old_entries(self, max_age: int = 3600):
        """Clean up old rate limit entries"""
        now = time.time()
        expired_connections = []
        
        for connection_id, history in self.message_history.items():
            if not history or history[-1] < now - max_age:
                expired_connections.append(connection_id)
        
        for connection_id in expired_connections:
            del self.message_history[connection_id]

class WebSocketManager:
    """Enhanced WebSocket connection manager with authentication and rate limiting"""
    
    def __init__(self):
        self.active_connections: Dict[str, ConnectionMetadata] = {}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)
        self.rate_limiter = RateLimiter(max_messages=200, time_window=60)
        self.heartbeat_interval = 30  # seconds
        self.connection_timeout = 300  # 5 minutes
        self.max_connections_per_user = 5
        self.max_message_size = 1024 * 1024  # 1MB
        
        # Message queues for disconnected users
        self.message_queues: Dict[str, List[Dict]] = defaultdict(list)
        self.max_queue_size = 100
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
    
    async def start_background_tasks(self):
        """Start background maintenance tasks"""
        if not self.cleanup_task:
            self.cleanup_task = asyncio.create_task(self._cleanup_task())
        if not self.heartbeat_task:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_task())
    
    async def stop_background_tasks(self):
        """Stop background tasks"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
    
    async def authenticate_connection(self, websocket: WebSocket, token: str) -> Optional[Dict[str, Any]]:
        """Authenticate WebSocket connection using JWT token"""
        try:
            payload = auth_handler.verify_token(token)
            if not payload or payload.get("type") != "access":
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return None
            
            user_id = payload.get("sub")
            if not user_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return None
            
            # Get user details from database
            from .database.supabase_client import supabase
            user = await supabase.get_user_by_id(user_id)
            if not user:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return None
            
            return {
                "user_id": user_id,
                "user_role": user.get("role", "user"),
                "user_data": user
            }
            
        except JWTError as e:
            logger.warning(f"JWT authentication failed: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return None
    
    async def connect(self, websocket: WebSocket, token: str) -> Optional[str]:
        """Establish authenticated WebSocket connection"""
        try:
            # Authenticate user
            auth_data = await self.authenticate_connection(websocket, token)
            if not auth_data:
                return None
            
            user_id = auth_data["user_id"]
            user_role = auth_data["user_role"]
            
            # Check connection limits
            if not self._can_accept_connection(user_id):
                await websocket.close(
                    code=status.WS_1013_TRY_AGAIN_LATER,
                    reason="Too many connections"
                )
                return None
            
            # Accept connection
            await websocket.accept()
            
            # Create connection metadata
            connection_meta = ConnectionMetadata(websocket, user_id, user_role)
            connection_meta.state = ConnectionState.CONNECTED
            
            # Store connection
            self.active_connections[connection_meta.connection_id] = connection_meta
            self.user_connections[user_id].add(connection_meta.connection_id)
            
            # Send queued messages if any
            await self._flush_message_queue(user_id, connection_meta.connection_id)
            
            # Send connection confirmation
            await self._send_message(
                connection_meta.connection_id,
                WebSocketMessage(
                    type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                    data={
                        "type": "connection_established",
                        "message": "WebSocket connection established",
                        "connection_id": connection_meta.connection_id,
                        "user_id": user_id
                    },
                    timestamp=datetime.now()
                ).dict()
            )
            
            logger.info(f"WebSocket connected: {connection_meta.connection_id} for user {user_id}")
            
            return connection_meta.connection_id
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return None
    
    def disconnect(self, connection_id: str, reason: str = "normal"):
        """Disconnect WebSocket connection"""
        if connection_id in self.active_connections:
            connection_meta = self.active_connections[connection_id]
            user_id = connection_meta.user_id
            
            # Update state
            connection_meta.state = ConnectionState.DISCONNECTED
            
            # Remove from user connections
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # Remove from active connections
            del self.active_connections[connection_id]
            
            logger.info(f"WebSocket disconnected: {connection_id} for user {user_id}, reason: {reason}")
    
    async def handle_message(self, connection_id: str, message_data: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        try:
            if connection_id not in self.active_connections:
                return
            
            connection_meta = self.active_connections[connection_id]
            
            # Rate limiting
            if not self.rate_limiter.is_allowed(connection_id):
                await self._send_error(
                    connection_id,
                    "rate_limit_exceeded",
                    "Too many messages, please slow down"
                )
                return
            
            # Update activity
            connection_meta.update_activity()
            
            # Validate message structure
            if not self._validate_message(message_data):
                await self._send_error(
                    connection_id,
                    "invalid_message",
                    "Invalid message format"
                )
                return
            
            # Process message based on type
            message_type = message_data.get("type")
            
            if message_type == "heartbeat":
                await self._handle_heartbeat(connection_id)
            elif message_type == "subscribe":
                await self._handle_subscription(connection_id, message_data)
            elif message_type == "unsubscribe":
                await self._handle_unsubscription(connection_id, message_data)
            elif message_type == "ping":
                await self._handle_ping(connection_id)
            else:
                await self._send_error(
                    connection_id,
                    "unknown_message_type",
                    f"Unknown message type: {message_type}"
                )
                
        except Exception as e:
            logger.error(f"Error handling message for {connection_id}: {e}")
            await self._send_error(connection_id, "processing_error", "Error processing message")
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Broadcast message to all connections of a specific user"""
        try:
            if user_id not in self.user_connections:
                # Queue message for when user reconnects
                self._queue_message(user_id, message)
                return
            
            disconnected_connections = []
            
            for connection_id in self.user_connections[user_id]:
                if connection_id in self.active_connections:
                    connection_meta = self.active_connections[connection_id]
                    if connection_meta.state == ConnectionState.CONNECTED:
                        try:
                            await self._send_message(connection_id, message)
                        except Exception:
                            disconnected_connections.append(connection_id)
                else:
                    disconnected_connections.append(connection_id)
            
            # Clean up disconnected connections
            for connection_id in disconnected_connections:
                self.disconnect(connection_id, "cleanup")
                
        except Exception as e:
            logger.error(f"Error broadcasting to user {user_id}: {e}")
    
    async def broadcast_to_admins(self, message: Dict[str, Any]):
        """Broadcast message to all admin users"""
        try:
            admin_connections = [
                conn for conn in self.active_connections.values()
                if conn.user_role == "admin" and conn.state == ConnectionState.CONNECTED
            ]
            
            for connection_meta in admin_connections:
                try:
                    await self._send_message(connection_meta.connection_id, message)
                except Exception as e:
                    logger.warning(f"Failed to send to admin {connection_meta.user_id}: {e}")
                    self.disconnect(connection_meta.connection_id, "send_error")
                    
        except Exception as e:
            logger.error(f"Error broadcasting to admins: {e}")
    
    async def broadcast_progress_update(self, job_id: str, progress_data: Dict[str, Any], user_id: str):
        """Broadcast progress update for a job"""
        message = WebSocketMessage(
            type=WebSocketMessageType.PROGRESS_UPDATE,
            data={
                "job_id": job_id,
                "progress": progress_data
            },
            timestamp=datetime.now(),
            job_id=job_id,
            user_id=user_id
        ).dict()
        
        await self.broadcast_to_user(user_id, message)
    
    async def broadcast_job_status(self, job_id: str, status_data: Dict[str, Any], user_id: str):
        """Broadcast job status update"""
        message = WebSocketMessage(
            type=WebSocketMessageType.JOB_STATUS,
            data=status_data,
            timestamp=datetime.now(),
            job_id=job_id,
            user_id=user_id
        ).dict()
        
        await self.broadcast_to_user(user_id, message)
    
    async def broadcast_system_alert(self, alert_data: Dict[str, Any], user_ids: List[str] = None):
        """Broadcast system alert to specified users or all admins"""
        message = WebSocketMessage(
            type=WebSocketMessageType.SYSTEM_NOTIFICATION,
            data={
                "type": "system_alert",
                "alert": alert_data
            },
            timestamp=datetime.now()
        ).dict()
        
        if user_ids:
            for user_id in user_ids:
                await self.broadcast_to_user(user_id, message)
        else:
            await self.broadcast_to_admins(message)
    
    # Internal methods
    def _can_accept_connection(self, user_id: str) -> bool:
        """Check if user can establish new connection"""
        current_connections = len(self.user_connections.get(user_id, []))
        return current_connections < self.max_connections_per_user
    
    def _validate_message(self, message_data: Dict) -> bool:
        """Validate WebSocket message structure"""
        try:
            if not isinstance(message_data, dict):
                return False
            
            if "type" not in message_data:
                return False
            
            # Check message size
            message_size = len(json.dumps(message_data))
            if message_size > self.max_message_size:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _queue_message(self, user_id: str, message: Dict[str, Any]):
        """Queue message for disconnected user"""
        if user_id in self.message_queues and len(self.message_queues[user_id]) >= self.max_queue_size:
            # Remove oldest message
            self.message_queues[user_id].pop(0)
        
        self.message_queues[user_id].append({
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _flush_message_queue(self, user_id: str, connection_id: str):
        """Flush queued messages to reconnected user"""
        if user_id in self.message_queues and self.message_queues[user_id]:
            for queued_message in self.message_queues[user_id]:
                try:
                    await self._send_message(connection_id, queued_message["message"])
                except Exception as e:
                    logger.warning(f"Failed to send queued message to {connection_id}: {e}")
            
            # Clear queue after sending
            del self.message_queues[user_id]
    
    async def _send_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to specific connection with error handling"""
        if connection_id not in self.active_connections:
            return
        
        connection_meta = self.active_connections[connection_id]
        
        if connection_meta.state != ConnectionState.CONNECTED:
            return
        
        try:
            await connection_meta.websocket.send_json(message)
            connection_meta.update_activity()
            
        except Exception as e:
            logger.warning(f"Failed to send message to {connection_id}: {e}")
            self.disconnect(connection_id, "send_error")
    
    async def _send_error(self, connection_id: str, error_type: str, message: str):
        """Send error message to connection"""
        error_message = WebSocketMessage(
            type=WebSocketMessageType.ERROR,
            data={
                "error_type": error_type,
                "message": message
            },
            timestamp=datetime.now()
        ).dict()
        
        await self._send_message(connection_id, error_message)
    
    # Message handlers
    async def _handle_heartbeat(self, connection_id: str):
        """Handle heartbeat message"""
        if connection_id in self.active_connections:
            self.active_connections[connection_id].update_heartbeat()
            
            # Send heartbeat response
            response = WebSocketMessage(
                type=WebSocketMessageType.HEARTBEAT,
                data={"status": "alive"},
                timestamp=datetime.now()
            ).dict()
            
            await self._send_message(connection_id, response)
    
    async def _handle_subscription(self, connection_id: str, message_data: Dict):
        """Handle subscription request"""
        if connection_id in self.active_connections:
            subscription = message_data.get("channel")
            if subscription:
                self.active_connections[connection_id].subscriptions.add(subscription)
                
                response = WebSocketMessage(
                    type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                    data={
                        "type": "subscription_added",
                        "channel": subscription
                    },
                    timestamp=datetime.now()
                ).dict()
                
                await self._send_message(connection_id, response)
    
    async def _handle_unsubscription(self, connection_id: str, message_data: Dict):
        """Handle unsubscription request"""
        if connection_id in self.active_connections:
            subscription = message_data.get("channel")
            if subscription in self.active_connections[connection_id].subscriptions:
                self.active_connections[connection_id].subscriptions.remove(subscription)
    
    async def _handle_ping(self, connection_id: str):
        """Handle ping message"""
        response = WebSocketMessage(
            type=WebSocketMessageType.SYSTEM_NOTIFICATION,
            data={"type": "pong"},
            timestamp=datetime.now()
        ).dict()
        
        await self._send_message(connection_id, response)
    
    # Background tasks
    async def _cleanup_task(self):
        """Background task to clean up stale connections and rate limits"""
        while True:
            try:
                # Clean up stale connections
                current_time = datetime.now()
                stale_connections = []
                
                for connection_id, connection_meta in self.active_connections.items():
                    time_since_activity = (current_time - connection_meta.last_activity).total_seconds()
                    if time_since_activity > self.connection_timeout:
                        stale_connections.append(connection_id)
                
                for connection_id in stale_connections:
                    self.disconnect(connection_id, "timeout")
                
                # Clean up rate limiter
                self.rate_limiter.cleanup_old_entries()
                
                # Clean up old message queues (older than 1 hour)
                current_time_iso = current_time.isoformat()
                for user_id in list(self.message_queues.keys()):
                    self.message_queues[user_id] = [
                        msg for msg in self.message_queues[user_id]
                        if (current_time - datetime.fromisoformat(msg["timestamp"])).total_seconds() < 3600
                    ]
                    if not self.message_queues[user_id]:
                        del self.message_queues[user_id]
                
                await asyncio.sleep(60)  # Run every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
                await asyncio.sleep(60)
    
    async def _heartbeat_task(self):
        """Background task to send heartbeats and check connection health"""
        while True:
            try:
                current_time = datetime.now()
                dead_connections = []
                
                for connection_id, connection_meta in self.active_connections.items():
                    # Check if connection is still alive
                    if not connection_meta.is_alive():
                        dead_connections.append(connection_id)
                    else:
                        # Send heartbeat to active connections
                        heartbeat_msg = WebSocketMessage(
                            type=WebSocketMessageType.HEARTBEAT,
                            data={"type": "ping"},
                            timestamp=current_time
                        ).dict()
                        
                        try:
                            await self._send_message(connection_id, heartbeat_msg)
                        except Exception:
                            dead_connections.append(connection_id)
                
                # Remove dead connections
                for connection_id in dead_connections:
                    self.disconnect(connection_id, "heartbeat_failed")
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat task error: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    # Utility methods
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        total_connections = len(self.active_connections)
        connected_users = len(self.user_connections)
        
        connections_by_role = defaultdict(int)
        for connection_meta in self.active_connections.values():
            connections_by_role[connection_meta.user_role] += 1
        
        return {
            "total_connections": total_connections,
            "connected_users": connected_users,
            "connections_by_role": dict(connections_by_role),
            "message_queues_size": len(self.message_queues),
            "rate_limiter_entries": len(self.rate_limiter.message_history)
        }
    
    def get_user_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """Get connection information for a user"""
        if user_id not in self.user_connections:
            return []
        
        connections = []
        for connection_id in self.user_connections[user_id]:
            if connection_id in self.active_connections:
                connections.append(self.active_connections[connection_id].to_dict())
        
        return connections
    
    async def disconnect_user(self, user_id: str, reason: str = "admin_action"):
        """Disconnect all connections for a user"""
        if user_id in self.user_connections:
            connection_ids = list(self.user_connections[user_id])
            for connection_id in connection_ids:
                self.disconnect(connection_id, reason)

# Global WebSocket manager instance
websocket_manager = WebSocketManager()
