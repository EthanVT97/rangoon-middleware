from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List

from app.auth import get_current_active_user
from app.database.supabase_client import supabase
from app.monitoring import live_monitor

router = APIRouter()

@router.get("/overview", response_model=Dict[str, Any])
async def get_dashboard_overview(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get dashboard overview with metrics"""
    try:
        user_id = current_user["id"]
        
        # Get real-time metrics
        metrics = await live_monitor.get_realtime_metrics(user_id)
        
        # Get recent jobs
        recent_jobs = await supabase.get_user_jobs(user_id, limit=10)
        
        # Get user's mappings
        mappings = await supabase.get_user_mappings(user_id)
        
        # Get ERP connection status
        erp_connection = await supabase.get_active_erp_connection()
        
        return {
            "status": "success",
            "metrics": metrics,
            "recent_jobs": recent_jobs,
            "mappings_count": len(mappings),
            "erp_connection": {
                "connected": erp_connection is not None,
                "name": erp_connection["name"] if erp_connection else None
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching dashboard data: {str(e)}"
        )

@router.get("/jobs", response_model=Dict[str, Any])
async def get_user_jobs(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    limit: int = 50,
    offset: int = 0
):
    """Get user's import jobs with pagination"""
    try:
        user_id = current_user["id"]
        jobs = await supabase.get_user_jobs(user_id, limit=limit)
        
        # Apply offset manually since Supabase doesn't support offset in our method
        paginated_jobs = jobs[offset:offset + limit]
        
        return {
            "status": "success",
            "jobs": paginated_jobs,
            "pagination": {
                "total": len(jobs),
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < len(jobs)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching jobs: {str(e)}"
        )

@router.get("/mappings", response_model=Dict[str, Any])
async def get_user_mappings(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get user's column mappings"""
    try:
        user_id = current_user["id"]
        mappings = await supabase.get_user_mappings(user_id)
        
        return {
            "status": "success",
            "mappings": mappings
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching mappings: {str(e)}"
        )

@router.get("/stats", response_model=Dict[str, Any])
async def get_dashboard_stats(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get detailed dashboard statistics"""
    try:
        user_id = current_user["id"]
        
        # Get metrics
        metrics = await live_monitor.get_realtime_metrics(user_id)
        
        # Get recent activity
        recent_jobs = await supabase.get_user_jobs(user_id, limit=100)
        
        # Calculate additional stats
        today = "today"  # Placeholder - would calculate actual today's date
        weekly_trend = "up"  # Placeholder - would calculate actual trend
        
        # Most used mappings (placeholder)
        top_mappings = ["Customer Import", "Product Sync"]  # Would calculate from actual data
        
        return {
            "status": "success",
            "stats": {
                "today_imports": metrics.get("today_jobs", 0),
                "success_rate": metrics.get("success_rate", 0),
                "active_monitoring": metrics.get("active_monitoring", 0),
                "weekly_trend": weekly_trend,
                "top_mappings": top_mappings
            },
            "metrics": metrics
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching stats: {str(e)}"
        )
