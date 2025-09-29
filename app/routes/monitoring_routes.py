from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import json
import asyncio
from typing import Dict, Any
from ..auth import get_current_active_user
from ..websocket_manager import websocket_manager
from ..monitoring import live_monitor
from ..database.supabase_client import supabase

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket for real-time monitoring"""
    await websocket_manager.connect(websocket, user_id)
    
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(10)
            await websocket.send_json({"type": "ping", "message": "connected"})
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, user_id)

@router.get("/metrics")
async def get_realtime_metrics(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get real-time monitoring metrics"""
    user_id = current_user["id"]
    metrics = await live_monitor.get_realtime_metrics(user_id)
    return {"status": "success", "metrics": metrics}

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get specific job status with real-time updates"""
    job = await supabase.get_job_by_id(job_id)
    
    if not job:
        return {"status": "error", "message": "Job not found"}
    
    # Start monitoring if job is still processing
    if job.get("status") in ["pending", "processing"]:
        await live_monitor.start_job_monitoring(job_id, current_user["id"])
    
    return {"status": "success", "job": job}

@router.get("/errors")
async def get_recent_errors(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get recent errors for the user"""
    try:
        user_id = current_user["id"]
        jobs = await supabase.get_user_jobs(user_id, limit=50)
        
        errors = []
        for job in jobs:
            if job.get("error_log"):
                for error in job.get("error_log", []):
                    errors.append({
                        "job_id": job.get("job_id"),
                        "filename": job.get("filename"),
                        "mapping_name": job.get("column_mappings", {}).get("mapping_name"),
                        "error": error,
                        "timestamp": job.get("created_at"),
                        "status": job.get("status")
                    })
        
        # Sort by timestamp (newest first)
        errors.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "status": "success",
            "total_errors": len(errors),
            "errors": errors[:20]  # Last 20 errors
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
