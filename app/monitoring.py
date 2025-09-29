from typing import Dict, Any, List
import asyncio
from datetime import datetime, timedelta

from .database.supabase_client import supabase
from .websocket_manager import websocket_manager

class LiveMonitor:
    def __init__(self):
        self.active_jobs = {}
        self.metrics_cache = {}
        self.cache_ttl = 30  # seconds
    
    async def start_job_monitoring(self, job_id: str, user_id: str):
        """Start monitoring a job"""
        self.active_jobs[job_id] = {
            "user_id": user_id,
            "start_time": datetime.now(),
            "last_update": datetime.now(),
            "progress": {
                "total": 0,
                "processed": 0,
                "failed": 0
            }
        }
        
        # Send initial monitoring start message
        await websocket_manager.broadcast_system_message(
            f"Started monitoring job: {job_id}", 
            user_id
        )
    
    async def update_job_progress(self, job_id: str, progress: Dict[str, Any]):
        """Update job progress and broadcast to client"""
        if job_id in self.active_jobs:
            user_id = self.active_jobs[job_id]["user_id"]
            self.active_jobs[job_id]["progress"].update(progress)
            self.active_jobs[job_id]["last_update"] = datetime.now()
            
            # Calculate percentage
            total = progress.get("total", 0)
            processed = progress.get("processed", 0)
            percentage = (processed / total * 100) if total > 0 else 0
            
            progress_data = {
                "job_id": job_id,
                "percentage": round(percentage, 2),
                "processed": processed,
                "total": total,
                "failed": progress.get("failed", 0)
            }
            
            await websocket_manager.broadcast_progress_update(job_id, progress_data, user_id)
    
    async def complete_job_monitoring(self, job_id: str, final_status: str):
        """Complete job monitoring"""
        if job_id in self.active_jobs:
            user_id = self.active_jobs[job_id]["user_id"]
            
            await websocket_manager.broadcast_system_message(
                f"Job completed: {job_id} - Status: {final_status}", 
                user_id
            )
            
            # Remove from active monitoring
            del self.active_jobs[job_id]
    
    async def get_realtime_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get real-time metrics for dashboard with caching"""
        cache_key = f"metrics_{user_id}"
        current_time = datetime.now()
        
        # Check cache
        if (cache_key in self.metrics_cache and 
            current_time - self.metrics_cache[cache_key]["timestamp"] < timedelta(seconds=self.cache_ttl)):
            return self.metrics_cache[cache_key]["data"]
        
        try:
            # Get user metrics from database
            metrics = await supabase.get_user_metrics(user_id)
            
            # Get recent jobs for additional metrics
            recent_jobs = await supabase.get_user_jobs(user_id, limit=20)
            
            # Calculate additional metrics
            today = datetime.now().date()
            today_jobs = [j for j in recent_jobs if 
                         datetime.fromisoformat(j["created_at"]).date() == today]
            
            # Recent errors (last 24 hours)
            recent_errors = []
            for job in recent_jobs:
                if job.get("error_log") and len(job["error_log"]) > 0:
                    job_time = datetime.fromisoformat(j["created_at"])
                    if datetime.now() - job_time < timedelta(hours=24):
                        for error in job["error_log"][:3]:  # Last 3 errors per job
                            recent_errors.append({
                                "job_id": job["job_id"],
                                "filename": job["filename"],
                                "error": error,
                                "timestamp": job["created_at"]
                            })
            
            # Prepare metrics data
            metrics_data = {
                **metrics,
                "today_jobs": len(today_jobs),
                "active_monitoring": len([j for j in self.active_jobs.values() if j["user_id"] == user_id]),
                "recent_errors": recent_errors[:10],  # Last 10 errors
                "last_updated": current_time.isoformat()
            }
            
            # Update cache
            self.metrics_cache[cache_key] = {
                "data": metrics_data,
                "timestamp": current_time
            }
            
            return metrics_data
            
        except Exception as e:
            return {
                "total_jobs": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "processing_jobs": 0,
                "success_rate": 0,
                "today_jobs": 0,
                "active_monitoring": 0,
                "recent_errors": [],
                "last_updated": current_time.isoformat(),
                "error": str(e)
            }
    
    async def get_job_details(self, job_id: str) -> Dict[str, Any]:
        """Get detailed job information"""
        try:
            job = await supabase.get_job_by_id(job_id)
            if not job:
                return {"error": "Job not found"}
            
            # Add monitoring information if active
            monitoring_info = {}
            if job_id in self.active_jobs:
                monitoring_info = {
                    "is_active": True,
                    "progress": self.active_jobs[job_id]["progress"],
                    "start_time": self.active_jobs[job_id]["start_time"].isoformat(),
                    "last_update": self.active_jobs[job_id]["last_update"].isoformat()
                }
            else:
                monitoring_info = {"is_active": False}
            
            return {
                **job,
                **monitoring_info
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def cleanup_old_monitoring(self):
        """Clean up old monitoring sessions"""
        current_time = datetime.now()
        expired_jobs = []
        
        for job_id, job_info in self.active_jobs.items():
            if current_time - job_info["last_update"] > timedelta(hours=1):  # 1 hour timeout
                expired_jobs.append(job_id)
        
        for job_id in expired_jobs:
            await self.complete_job_monitoring(job_id, "monitoring_timeout")

# Global monitor instance
live_monitor = LiveMonitor()

# Background task for cleanup
async def monitoring_cleanup_task():
    """Background task to clean up old monitoring sessions"""
    while True:
        try:
            await live_monitor.cleanup_old_monitoring()
            await asyncio.sleep(300)  # Run every 5 minutes
        except Exception as e:
            print(f"Monitoring cleanup error: {e}")
            await asyncio.sleep(60)
