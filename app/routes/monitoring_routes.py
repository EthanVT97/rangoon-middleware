from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import Dict, Any, List
import json
import asyncio
import logging
from datetime import datetime, timedelta
import uuid

from app.auth import get_current_active_user, get_current_admin_user, optional_auth
from app.websocket_manager import websocket_manager
from app.monitoring import live_monitor
from app.database.supabase_client import supabase
from app.erp_integration import erp_integration
from app.models import WebSocketMessage, WebSocketMessageType, SuccessResponse, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

class WebSocketAuthenticator:
    """WebSocket authentication and authorization"""
    
    @staticmethod
    async def authenticate_websocket(websocket: WebSocket, token: str) -> Dict[str, Any]:
        """Authenticate WebSocket connection"""
        try:
            from app.auth import auth_handler
            user_data = await auth_handler.get_token_data(token)
            if not user_data or not user_data.user_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return None
            return user_data
        except Exception as e:
            logger.warning(f"WebSocket authentication failed: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Authenticated WebSocket for real-time monitoring"""
    try:
        # Get token from query parameters
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Authenticate user
        user_data = await WebSocketAuthenticator.authenticate_websocket(websocket, token)
        if not user_data:
            return
        
        user_id = user_data.user_id
        
        # Connect to WebSocket manager
        connection_id = await websocket_manager.connect(websocket, token)
        if not connection_id:
            await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
            return
        
        logger.info(f"WebSocket connected: {connection_id} for user {user_id}")
        
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    message_type = message.get("type")
                    
                    # Handle different message types
                    if message_type == "ping":
                        await websocket_manager.send_personal_message(
                            WebSocketMessage(
                                type=WebSocketMessageType.HEARTBEAT,
                                data={"type": "pong"},
                                timestamp=datetime.now()
                            ).dict(),
                            connection_id
                        )
                    
                    elif message_type == "subscribe_job":
                        job_id = message.get("job_id")
                        await _handle_job_subscription(connection_id, user_id, job_id)
                    
                    elif message_type == "unsubscribe_job":
                        job_id = message.get("job_id")
                        await _handle_job_unsubscription(connection_id, job_id)
                    
                    elif message_type == "get_metrics":
                        await _handle_metrics_request(connection_id, user_id)
                    
                    elif message_type == "list_subscriptions":
                        await _handle_list_subscriptions(connection_id, user_id)
                    
                    else:
                        # Handle unknown message types through WebSocket manager
                        await websocket_manager.handle_message(connection_id, message)
                        
                except json.JSONDecodeError:
                    await websocket_manager.send_personal_message(
                        WebSocketMessage(
                            type=WebSocketMessageType.ERROR,
                            data={
                                "error_type": "invalid_message",
                                "message": "Invalid JSON format"
                            },
                            timestamp=datetime.now()
                        ).dict(),
                        connection_id
                    )
                
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    await websocket_manager.send_personal_message(
                        WebSocketMessage(
                            type=WebSocketMessageType.ERROR,
                            data={
                                "error_type": "processing_error",
                                "message": "Error processing message"
                            },
                            timestamp=datetime.now()
                        ).dict(),
                        connection_id
                    )
                        
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id}")
            
        except Exception as e:
            logger.error(f"WebSocket error for {connection_id}: {e}")
            
        finally:
            websocket_manager.disconnect(connection_id, "normal")
            
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass

async def _handle_job_subscription(connection_id: str, user_id: str, job_id: str):
    """Handle job subscription request"""
    try:
        # Verify user has access to this job
        job = await supabase.get_job_by_id(job_id)
        if not job:
            await websocket_manager.send_personal_message(
                WebSocketMessage(
                    type=WebSocketMessageType.ERROR,
                    data={
                        "error_type": "job_not_found",
                        "message": f"Job {job_id} not found"
                    },
                    timestamp=datetime.now()
                ).dict(),
                connection_id
            )
            return
        
        if job["created_by"] != user_id:
            await websocket_manager.send_personal_message(
                WebSocketMessage(
                    type=WebSocketMessageType.ERROR,
                    data={
                        "error_type": "access_denied",
                        "message": "Access denied to this job"
                    },
                    timestamp=datetime.now()
                ).dict(),
                connection_id
            )
            return
        
        # Subscribe to job updates
        await websocket_manager.send_personal_message(
            WebSocketMessage(
                type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                data={
                    "type": "subscription_added",
                    "job_id": job_id,
                    "message": f"Subscribed to job {job_id}"
                },
                timestamp=datetime.now()
            ).dict(),
            connection_id
        )
        
        # Send current job status
        job_details = await live_monitor.get_job_details(job_id)
        await websocket_manager.send_personal_message(
            WebSocketMessage(
                type=WebSocketMessageType.JOB_STATUS,
                data=job_details,
                timestamp=datetime.now(),
                job_id=job_id
            ).dict(),
            connection_id
        )
        
    except Exception as e:
        logger.error(f"Job subscription error: {e}")
        await websocket_manager.send_personal_message(
            WebSocketMessage(
                type=WebSocketMessageType.ERROR,
                data={
                    "error_type": "subscription_error",
                    "message": "Failed to subscribe to job"
                },
                timestamp=datetime.now()
            ).dict(),
            connection_id
        )

async def _handle_job_unsubscription(connection_id: str, job_id: str):
    """Handle job unsubscription request"""
    await websocket_manager.send_personal_message(
        WebSocketMessage(
            type=WebSocketMessageType.SYSTEM_NOTIFICATION,
            data={
                "type": "subscription_removed",
                "job_id": job_id,
                "message": f"Unsubscribed from job {job_id}"
            },
            timestamp=datetime.now()
        ).dict(),
        connection_id
    )

async def _handle_metrics_request(connection_id: str, user_id: str):
    """Handle metrics request"""
    try:
        metrics = await live_monitor.get_realtime_metrics(user_id)
        await websocket_manager.send_personal_message(
            WebSocketMessage(
                type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                data={
                    "type": "metrics_update",
                    "metrics": metrics
                },
                timestamp=datetime.now()
            ).dict(),
            connection_id
        )
    except Exception as e:
        logger.error(f"Metrics request error: {e}")

async def _handle_list_subscriptions(connection_id: str, user_id: str):
    """Handle list subscriptions request"""
    try:
        user_connections = websocket_manager.get_user_connections(user_id)
        subscriptions = []
        
        for conn in user_connections:
            subscriptions.extend(conn.get("subscriptions", []))
        
        await websocket_manager.send_personal_message(
            WebSocketMessage(
                type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                data={
                    "type": "subscriptions_list",
                    "subscriptions": list(set(subscriptions))
                },
                timestamp=datetime.now()
            ).dict(),
            connection_id
        )
    except Exception as e:
        logger.error(f"List subscriptions error: {e}")

@router.get("/metrics", response_model=SuccessResponse)
async def get_realtime_metrics(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get real-time monitoring metrics for current user"""
    try:
        user_id = current_user["id"]
        metrics = await live_monitor.get_realtime_metrics(user_id)
        
        return SuccessResponse(
            message="Metrics retrieved successfully",
            data=metrics
        )
        
    except Exception as e:
        logger.error(f"Error fetching metrics for user {current_user['id']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching monitoring metrics"
        )

@router.get("/metrics/system", response_model=SuccessResponse)
async def get_system_metrics(current_user: Dict[str, Any] = Depends(get_current_admin_user)):
    """Get system-wide metrics (admin only)"""
    try:
        system_metrics = await live_monitor.get_system_wide_metrics()
        
        return SuccessResponse(
            message="System metrics retrieved successfully",
            data=system_metrics
        )
        
    except Exception as e:
        logger.error(f"Error fetching system metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching system metrics"
        )

@router.get("/jobs/{job_id}/status", response_model=SuccessResponse)
async def get_job_status(
    job_id: str, 
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get specific job status with detailed information"""
    try:
        user_id = current_user["id"]
        user_role = current_user.get("role")
        
        # Get job details
        job_details = await live_monitor.get_job_details(job_id)
        
        if "error" in job_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=job_details["error"]
            )
        
        # Check if user owns this job or is admin
        if job_details.get("created_by") != user_id and user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this job"
            )
        
        return SuccessResponse(
            message="Job status retrieved successfully",
            data={
                "job": job_details,
                "websocket_support": True,
                "subscription_endpoint": f"/api/monitoring/ws?token=YOUR_TOKEN"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job status {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching job status"
        )

@router.get("/jobs/{job_id}/progress", response_model=SuccessResponse)
async def get_job_progress(
    job_id: str, 
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get real-time progress for a specific job"""
    try:
        user_id = current_user["id"]
        
        # Verify job access
        job = await supabase.get_job_by_id(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        if job["created_by"] != user_id and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this job"
            )
        
        # Get progress from live monitor
        job_details = await live_monitor.get_job_details(job_id)
        
        progress_data = {
            "job_id": job_id,
            "status": job_details.get("status"),
            "progress_percentage": job_details.get("progress", {}).get("percentage", 0),
            "processed_records": job_details.get("processed_records", 0),
            "total_records": job_details.get("total_records", 0),
            "failed_records": job_details.get("failed_records", 0),
            "is_active": job_details.get("is_active", False),
            "start_time": job_details.get("start_time"),
            "last_update": job_details.get("last_update"),
            "estimated_completion": job_details.get("estimated_completion")
        }
        
        return SuccessResponse(
            message="Job progress retrieved successfully",
            data=progress_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job progress {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching job progress"
        )

@router.get("/errors", response_model=SuccessResponse)
async def get_recent_errors(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get recent errors for the current user"""
    try:
        user_id = current_user["id"]
        user_role = current_user.get("role")
        
        # Get user's jobs with errors
        limit = 100 if user_role == "admin" else 50
        jobs = await supabase.get_user_jobs(user_id, limit=limit)
        
        errors = []
        for job in jobs:
            if job.get("error_log") and len(job["error_log"]) > 0:
                for error in job["error_log"][:5]:  # Last 5 errors per job
                    errors.append({
                        "job_id": job["job_id"],
                        "filename": job["filename"],
                        "mapping_name": job.get("column_mappings", {}).get("mapping_name", "Unknown"),
                        "error": error,
                        "timestamp": job["created_at"],
                        "status": job["status"],
                        "severity": error.get("severity", "error")
                    })
        
        # Sort by timestamp (newest first) and limit
        errors.sort(key=lambda x: x["timestamp"], reverse=True)
        recent_errors = errors[:50]  # Last 50 errors
        
        # Calculate error statistics
        error_stats = {
            "total_errors": len(recent_errors),
            "last_24_hours": len([e for e in recent_errors if 
                                 datetime.now() - datetime.fromisoformat(e["timestamp"].replace('Z', '+00:00')) < timedelta(hours=24)]),
            "by_severity": {
                "error": len([e for e in recent_errors if e.get("severity") == "error"]),
                "warning": len([e for e in recent_errors if e.get("severity") == "warning"]),
                "info": len([e for e in recent_errors if e.get("severity") == "info"])
            }
        }
        
        return SuccessResponse(
            message="Recent errors retrieved successfully",
            data={
                "errors": recent_errors,
                "statistics": error_stats
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching recent errors for user {current_user['id']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching recent errors"
        )

@router.get("/system/health", response_model=SuccessResponse)
async def get_system_health(current_user: Dict[str, Any] = Depends(optional_auth)):
    """Get comprehensive system health status"""
    try:
        health_data = {
            "timestamp": datetime.now().isoformat(),
            "services": {},
            "overall_status": "healthy"
        }
        
        # Test database connection
        try:
            start_time = datetime.now()
            test_result = supabase.client.from_('profiles').select('count', count='exact').limit(1).execute()
            response_time = (datetime.now() - start_time).total_seconds()
            
            health_data["services"]["database"] = {
                "status": "healthy",
                "response_time": round(response_time, 3),
                "details": "Connection successful"
            }
        except Exception as e:
            health_data["services"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
                "details": "Database connection failed"
            }
            health_data["overall_status"] = "degraded"
        
        # Test ERP connection
        try:
            erp_connection = await supabase.get_active_erp_connection()
            if erp_connection:
                erp_test = await erp_integration.test_connection()
                health_data["services"]["erp_integration"] = {
                    "status": "healthy" if erp_test["success"] else "unhealthy",
                    "response_time": erp_test.get("response_time"),
                    "details": erp_test.get("message", "ERP connection test"),
                    "error": None if erp_test["success"] else erp_test.get("error")
                }
                
                if not erp_test["success"]:
                    health_data["overall_status"] = "degraded"
            else:
                health_data["services"]["erp_integration"] = {
                    "status": "not_configured",
                    "details": "No active ERP connection configured"
                }
        except Exception as e:
            health_data["services"]["erp_integration"] = {
                "status": "unhealthy",
                "error": str(e),
                "details": "ERP connection test failed"
            }
            health_data["overall_status"] = "degraded"
        
        # WebSocket status
        try:
            ws_stats = websocket_manager.get_connection_stats()
            health_data["services"]["websocket"] = {
                "status": "healthy",
                "active_connections": ws_stats["total_connections"],
                "connected_users": ws_stats["connected_users"],
                "details": "WebSocket service operational"
            }
        except Exception as e:
            health_data["services"]["websocket"] = {
                "status": "unhealthy",
                "error": str(e),
                "details": "WebSocket service issues"
            }
            health_data["overall_status"] = "degraded"
        
        # Monitoring system status
        try:
            system_metrics = await live_monitor.get_system_wide_metrics()
            health_data["services"]["monitoring"] = {
                "status": "healthy",
                "active_jobs": system_metrics.get("active_jobs_count", 0),
                "performance": system_metrics.get("performance_metrics", {}),
                "details": "Monitoring system operational"
            }
        except Exception as e:
            health_data["services"]["monitoring"] = {
                "status": "unhealthy",
                "error": str(e),
                "details": "Monitoring system issues"
            }
            health_data["overall_status"] = "degraded"
        
        # System resources
        try:
            import psutil
            health_data["system_resources"] = {
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "details": "System resources normal"
            }
            
            # Check if resources are critical
            if (health_data["system_resources"]["memory_usage"] > 90 or 
                health_data["system_resources"]["disk_usage"] > 90):
                health_data["overall_status"] = "degraded"
                
        except Exception as e:
            health_data["system_resources"] = {
                "error": str(e),
                "details": "Unable to read system resources"
            }
        
        return SuccessResponse(
            message="System health status retrieved successfully",
            data=health_data
        )
        
    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking system health"
        )

@router.get("/connections", response_model=SuccessResponse)
async def get_connection_stats(current_user: Dict[str, Any] = Depends(get_current_admin_user)):
    """Get WebSocket connection statistics (admin only)"""
    try:
        stats = websocket_manager.get_connection_stats()
        
        return SuccessResponse(
            message="Connection statistics retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Error fetching connection stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching connection statistics"
        )

@router.post("/alerts/test", response_model=SuccessResponse)
async def test_alert_system(current_user: Dict[str, Any] = Depends(get_current_admin_user)):
    """Test alert system (admin only)"""
    try:
        # Create a test alert
        test_alert = {
            "alert_id": f"test_{uuid.uuid4().hex[:8]}",
            "type": "test_alert",
            "level": "info",
            "message": "Test alert generated by admin user",
            "timestamp": datetime.now().isoformat(),
            "user_id": current_user["id"]
        }
        
        # Broadcast to admins
        await websocket_manager.broadcast_to_admins(
            WebSocketMessage(
                type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                data={
                    "type": "alert",
                    "alert": test_alert
                },
                timestamp=datetime.now()
            ).dict()
        )
        
        return SuccessResponse(
            message="Test alert sent successfully",
            data=test_alert
        )
        
    except Exception as e:
        logger.error(f"Error sending test alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error sending test alert"
            )
