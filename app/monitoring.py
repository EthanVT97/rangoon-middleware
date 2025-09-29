from typing import Dict, Any, List
import asyncio
from datetime import datetime, timedelta
from .database.supabase_client import supabase
from .websocket_manager import websocket_manager

class LiveMonitor:
    def __init__(self):
        self.active_jobs = {}
    
    async def start_job_monitoring(self, job_id: str, user_id: str):
        """Start monitoring a job"""
        self.active_jobs[job_id] = {
            "user_id": user_id,
            "start_time": datetime.now(),
            "last_update": datetime.now()
        }
        
        # Subscribe to Supabase real-time updates
        def handle_update(payload):
            asyncio.create_task(
                self._handle_job_update(payload, user_id)
            )
        
        supabase.subscribe_to_job_updates(user_id, handle_update)
    
    async def _handle_job_update(self, payload: Dict[str, Any], user_id: str):
        """Handle real-time job updates"""
        try:
            if payload.get("eventType") == "UPDATE":
                record = payload.get("record", {})
                
                # Send update via WebSocket
                await websocket_manager.broadcast_job_update(record, user_id)
                
                # Log the update
                await self._log_monitoring_event(record, user_id)
                
        except Exception as e:
            error_data = {
                "timestamp": datetime.now().isoformat(),
                "type": "monitoring_error",
                "job_id": payload.get("record", {}).get("job_id"),
                "error": str(e)
            }
            await websocket_manager.broadcast_error(error_data, user_id)
    
    async def _log_monitoring_event(self, job_data: Dict[str, Any], user_id: str):
        """Log monitoring events for analytics"""
        log_entry = {
            "user_id": user_id,
            "job_id": job_data.get("job_id"),
            "event_type": "status_update",
            "old_status": job_data.get("old_status"),
            "new_status": job_data.get("status"),
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "processed_records": job_data.get("processed_records"),
                "failed_records": job_data.get("failed_records")
            }
        }
        
        try:
            await supabase.client.from_("monitoring_logs").insert(log_entry).execute()
        except Exception as e:
            print(f"Monitoring log error: {e}")
    
    async def get_realtime_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get real-time metrics for dashboard"""
        try:
            # Get recent jobs
            jobs = await supabase.get_user_jobs(user_id, limit=100)
            
            # Calculate metrics
            total_jobs = len(jobs)
            completed_jobs = len([j for j in jobs if j.get("status") == "completed"])
            failed_jobs = len([j for j in jobs if j.get("status") == "failed"])
            processing_jobs = len([j for j in jobs if j.get("status") == "processing"])
            
            # Calculate success rate
            success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            
            # Recent errors
            recent_errors = []
            for job in jobs:
                if job.get("error_log"):
                    for error in job.get("error_log", [])[:5]:  # Last 5 errors
                        recent_errors.append({
                            "job_id": job.get("job_id"),
                            "filename": job.get("filename"),
                            "error": error,
                            "timestamp": job.get("created_at")
                        })
            
            return {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "processing_jobs": processing_jobs,
                "success_rate": round(success_rate, 2),
                "recent_errors": recent_errors[-10:],  # Last 10 errors
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "total_jobs": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "processing_jobs": 0,
                "success_rate": 0,
                "recent_errors": [],
                "last_updated": datetime.now().isoformat()
            }

# Global monitor instance
live_monitor = LiveMonitor()
