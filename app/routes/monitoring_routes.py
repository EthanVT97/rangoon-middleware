from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict, Any
import json
import asyncio

from app.auth import get_current_active_user
from app.websocket_manager import websocket_manager
from app.monitoring import live_monitor
from app.database.supabase_client import supabase

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket for real-time monitoring"""
    await websocket_manager.connect(websocket, user_id)
    
    try:
        while True:
            # Wait for messages from client (ping/pong)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await websocket_manager.send_personal_message({
                    "type": "pong",
                    "timestamp": "now"
                }, user_id)
                
            elif message.get("type") == "subscribe_job":
                job_id = message.get("job_id")
                # Subscribe to job updates (implementation would track subscriptions)
                
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, user_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(websocket, user_id)

@router.get("/metrics", response_model=Dict[str, Any])
async def get_realtime_metrics(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get real-time monitoring metrics"""
    try:
        user_id = current_user["id"]
        metrics = await live_monitor.get_realtime_metrics(user_id)
        
        return {
            "status": "success",
            "metrics": metrics
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching metrics: {str(e)}"
        )

@router.get("/jobs/{job_id}/status", response_model=Dict[str, Any])
async def get_job_status(
    job_id: str, 
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get specific job status with real-time updates"""
    try:
        user_id = current_user["id"]
        
        # Get job details
        job_details = await live_monitor.get_job_details(job_id)
        
        if "error" in job_details:
            raise HTTPException(status_code=404, detail=job_details["error"])
        
        # Check if user owns this job
        if job_details["created_by"] != user_id and current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied to this job")
        
        return {
            "status": "success",
            "job": job_details,
            "websocket_url": f"/api/monitoring/ws/{user_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching job status: {str(e)}"
        )

@router.get("/errors", response_model=Dict[str, Any])
async def get_recent_errors(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get recent errors for the user"""
    try:
        user_id = current_user["id"]
        jobs = await supabase.get_user_jobs(user_id, limit=50)
        
        errors = []
        for job in jobs:
            if job.get("error_log") and len(job["error_log"]) > 0:
                for error in job["error_log"]:
                    errors.append({
                        "job_id": job["job_id"],
                        "filename": job["filename"],
                        "mapping_name": job.get("column_mappings", {}).get("mapping_name", "Unknown"),
                        "error": error,
                        "timestamp": job["created_at"],
                        "status": job["status"]
                    })
        
        # Sort by timestamp (newest first)
        errors.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "status": "success",
            "total_errors": len(errors),
            "errors": errors[:20]  # Last 20 errors
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching errors: {str(e)}"
        )

@router.get("/system/health", response_model=Dict[str, Any])
async def get_system_health():
    """Get system health status"""
    try:
        # Test database connection
        db_status = "healthy"
        try:
            test_result = supabase.client.from_('profiles').select('count', count='exact').limit(1).execute()
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        
        # Test ERP connection (if configured)
        erp_status = "not configured"
        erp_connection = await supabase.get_active_erp_connection()
        if erp_connection:
            try:
                erp_test = await erp_integration.test_connection()
                erp_status = "healthy" if erp_test["success"] else f"unhealthy: {erp_test.get('error')}"
            except Exception as e:
                erp_status = f"unhealthy: {str(e)}"
        
        return {
            "status": "success",
            "health": {
                "database": db_status,
                "erp_connection": erp_status,
                "websocket_connections": len(websocket_manager.active_connections),
                "active_monitoring_jobs": len(live_monitor.active_jobs),
                "timestamp": "now"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking system health: {str(e)}"
        )
