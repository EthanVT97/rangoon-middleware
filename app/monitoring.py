import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
import time
from enum import Enum
import psutil
import json

from .database.supabase_client import supabase
from .websocket_manager import websocket_manager
from .models import ProgressUpdate, WebSocketMessage, WebSocketMessageType

# Configure logging
logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class PerformanceMetrics:
    """Performance metrics tracking"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.processing_times = deque(maxlen=window_size)
        self.error_rates = deque(maxlen=window_size)
        self.memory_usage = deque(maxlen=window_size)
        self.request_rates = deque(maxlen=window_size)
    
    def record_processing_time(self, processing_time: float):
        """Record processing time for performance analysis"""
        self.processing_times.append(processing_time)
    
    def record_error_rate(self, error_count: int, total_operations: int):
        """Record error rate"""
        if total_operations > 0:
            error_rate = (error_count / total_operations) * 100
            self.error_rates.append(error_rate)
    
    def record_memory_usage(self):
        """Record current memory usage"""
        memory_percent = psutil.virtual_memory().percent
        self.memory_usage.append(memory_percent)
    
    def record_request_rate(self, requests: int, time_window: float = 60.0):
        """Record request rate"""
        if time_window > 0:
            rate = requests / time_window
            self.request_rates.append(rate)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        return {
            "avg_processing_time": sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0,
            "max_processing_time": max(self.processing_times) if self.processing_times else 0,
            "min_processing_time": min(self.processing_times) if self.processing_times else 0,
            "current_error_rate": self.error_rates[-1] if self.error_rates else 0,
            "avg_error_rate": sum(self.error_rates) / len(self.error_rates) if self.error_rates else 0,
            "current_memory_usage": self.memory_usage[-1] if self.memory_usage else 0,
            "avg_memory_usage": sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0,
            "current_request_rate": self.request_rates[-1] if self.request_rates else 0,
            "metrics_window_size": len(self.processing_times)
        }

class AlertManager:
    """Alert management system"""
    
    def __init__(self):
        self.alert_rules = {
            "high_error_rate": {
                "threshold": 10.0,  # 10% error rate
                "level": AlertLevel.WARNING,
                "message": "High error rate detected"
            },
            "high_memory_usage": {
                "threshold": 85.0,  # 85% memory usage
                "level": AlertLevel.WARNING,
                "message": "High memory usage detected"
            },
            "job_timeout": {
                "threshold": 3600,  # 1 hour
                "level": AlertLevel.ERROR,
                "message": "Job processing timeout"
            },
            "database_connection": {
                "level": AlertLevel.CRITICAL,
                "message": "Database connection issues"
            }
        }
        self.active_alerts = {}
    
    async def check_and_trigger_alerts(self, metrics: Dict[str, Any], job_data: Optional[Dict] = None):
        """Check metrics against alert rules and trigger alerts if needed"""
        triggered_alerts = []
        
        # Check error rate
        error_rate = metrics.get("current_error_rate", 0)
        if error_rate > self.alert_rules["high_error_rate"]["threshold"]:
            alert_id = await self.trigger_alert(
                "high_error_rate",
                f"Error rate is {error_rate:.1f}%",
                self.alert_rules["high_error_rate"]["level"]
            )
            triggered_alerts.append(alert_id)
        
        # Check memory usage
        memory_usage = metrics.get("current_memory_usage", 0)
        if memory_usage > self.alert_rules["high_memory_usage"]["threshold"]:
            alert_id = await self.trigger_alert(
                "high_memory_usage",
                f"Memory usage is {memory_usage:.1f}%",
                self.alert_rules["high_memory_usage"]["level"]
            )
            triggered_alerts.append(alert_id)
        
        # Check job timeouts
        if job_data and self._check_job_timeout(job_data):
            alert_id = await self.trigger_alert(
                "job_timeout",
                f"Job {job_data.get('job_id')} has been running for too long",
                self.alert_rules["job_timeout"]["level"]
            )
            triggered_alerts.append(alert_id)
        
        return triggered_alerts
    
    def _check_job_timeout(self, job_data: Dict) -> bool:
        """Check if job has timed out"""
        start_time = job_data.get("start_time")
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        
        if start_time and isinstance(start_time, datetime):
            elapsed = datetime.now() - start_time
            return elapsed.total_seconds() > self.alert_rules["job_timeout"]["threshold"]
        return False
    
    async def trigger_alert(self, alert_type: str, message: str, level: AlertLevel) -> str:
        """Trigger a new alert"""
        alert_id = f"alert_{int(time.time())}_{alert_type}"
        
        alert_data = {
            "alert_id": alert_id,
            "type": alert_type,
            "level": level.value,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "is_resolved": False
        }
        
        self.active_alerts[alert_id] = alert_data
        
        # Broadcast alert via WebSocket
        await websocket_manager.broadcast_to_admins(
            WebSocketMessage(
                type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                data={
                    "type": "alert",
                    "alert": alert_data
                },
                timestamp=datetime.now()
            )
        )
        
        # Log alert
        logger.warning(f"Alert triggered: {alert_type} - {message}")
        
        # Store alert in database
        try:
            await supabase.create_monitoring_log({
                "log_type": "alert",
                "log_data": alert_data,
                "created_at": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to save alert to database: {e}")
        
        return alert_id
    
    async def resolve_alert(self, alert_id: str, resolution_message: str = "Resolved"):
        """Resolve an active alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id]["is_resolved"] = True
            self.active_alerts[alert_id]["resolved_at"] = datetime.now().isoformat()
            self.active_alerts[alert_id]["resolution_message"] = resolution_message
            
            # Broadcast resolution
            await websocket_manager.broadcast_to_admins(
                WebSocketMessage(
                    type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                    data={
                        "type": "alert_resolution",
                        "alert": self.active_alerts[alert_id]
                    },
                    timestamp=datetime.now()
                )
            )
            
            logger.info(f"Alert resolved: {alert_id} - {resolution_message}")

class LiveMonitor:
    """Enhanced live monitoring system with performance tracking and alerting"""
    
    def __init__(self):
        self.active_jobs = {}
        self.metrics_cache = {}
        self.cache_ttl = 30  # seconds
        self.max_cache_size = 1000
        self.performance_metrics = PerformanceMetrics()
        self.alert_manager = AlertManager()
        self.job_history = defaultdict(list)
        self.system_metrics = {
            "start_time": datetime.now(),
            "total_processed_jobs": 0,
            "total_processed_records": 0,
            "total_errors": 0
        }
    
    async def start_job_monitoring(self, job_id: str, user_id: str, initial_data: Dict[str, Any]):
        """Start monitoring a job with enhanced tracking"""
        try:
            self.active_jobs[job_id] = {
                "user_id": user_id,
                "start_time": datetime.now(),
                "last_update": datetime.now(),
                "progress": {
                    "total": initial_data.get("total_records", 0),
                    "processed": 0,
                    "failed": 0,
                    "current_stage": "initializing"
                },
                "metadata": initial_data
            }
            
            # Record system metrics
            self.system_metrics["total_processed_jobs"] += 1
            
            # Send initial monitoring start message
            await websocket_manager.broadcast_to_user(
                user_id,
                WebSocketMessage(
                    type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                    data={
                        "type": "job_started",
                        "job_id": job_id,
                        "message": f"Started monitoring job: {job_id}",
                        "initial_data": initial_data
                    },
                    timestamp=datetime.now()
                )
            )
            
            logger.info(f"Started monitoring job: {job_id} for user: {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to start job monitoring for {job_id}: {e}")
            raise
    
    async def update_job_progress(self, job_id: str, progress: Dict[str, Any]):
        """Update job progress with enhanced tracking and broadcasting"""
        try:
            if job_id not in self.active_jobs:
                logger.warning(f"Job {job_id} not found in active monitoring")
                return
            
            job_info = self.active_jobs[job_id]
            user_id = job_info["user_id"]
            
            # Update progress information
            job_info["progress"].update(progress)
            job_info["last_update"] = datetime.now()
            
            # Calculate percentage and estimated time
            total = progress.get("total", job_info["progress"]["total"])
            processed = progress.get("processed", 0)
            failed = progress.get("failed", 0)
            
            percentage = (processed / total * 100) if total > 0 else 0
            
            # Calculate estimated time remaining
            elapsed_time = (datetime.now() - job_info["start_time"]).total_seconds()
            if processed > 0 and elapsed_time > 0:
                records_per_second = processed / elapsed_time
                remaining_records = total - processed
                estimated_remaining = remaining_records / records_per_second if records_per_second > 0 else 0
            else:
                estimated_remaining = None
            
            # Prepare progress data
            progress_data = ProgressUpdate(
                job_id=job_id,
                status=progress.get("status", "processing"),
                progress=round(percentage, 2),
                processed_records=processed,
                total_records=total,
                message=progress.get("message", "Processing..."),
                estimated_time_remaining=estimated_remaining
            )
            
            # Broadcast progress update
            await websocket_manager.broadcast_progress_update(job_id, progress_data.dict(), user_id)
            
            # Record performance metrics
            if "processing_time" in progress:
                self.performance_metrics.record_processing_time(progress["processing_time"])
            
            # Update system metrics
            self.system_metrics["total_processed_records"] += (processed - job_info["progress"]["processed"])
            self.system_metrics["total_errors"] += (failed - job_info["progress"]["failed"])
            
            logger.debug(f"Job {job_id} progress: {percentage:.1f}% ({processed}/{total})")
            
        except Exception as e:
            logger.error(f"Failed to update job progress for {job_id}: {e}")
    
    async def complete_job_monitoring(self, job_id: str, final_status: str, summary: Dict[str, Any] = None):
        """Complete job monitoring with comprehensive reporting"""
        try:
            if job_id not in self.active_jobs:
                return
            
            job_info = self.active_jobs[job_id]
            user_id = job_info["user_id"]
            start_time = job_info["start_time"]
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Store job history
            self.job_history[user_id].append({
                "job_id": job_id,
                "start_time": start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "processing_time": processing_time,
                "status": final_status,
                "summary": summary or {}
            })
            
            # Limit job history size
            if len(self.job_history[user_id]) > 100:
                self.job_history[user_id] = self.job_history[user_id][-100:]
            
            # Send completion message
            await websocket_manager.broadcast_to_user(
                user_id,
                WebSocketMessage(
                    type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                    data={
                        "type": "job_completed",
                        "job_id": job_id,
                        "status": final_status,
                        "processing_time": processing_time,
                        "summary": summary,
                        "message": f"Job completed: {job_id} - Status: {final_status}"
                    },
                    timestamp=datetime.now()
                )
            )
            
            # Remove from active monitoring
            del self.active_jobs[job_id]
            
            logger.info(f"Completed monitoring job: {job_id} with status: {final_status}")
            
        except Exception as e:
            logger.error(f"Failed to complete job monitoring for {job_id}: {e}")
    
    async def get_realtime_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive real-time metrics for dashboard"""
        cache_key = f"metrics_{user_id}"
        current_time = datetime.now()
        
        # Check cache with TTL
        if self._is_cache_valid(cache_key):
            return self.metrics_cache[cache_key]["data"]
        
        try:
            # Get user metrics from database
            db_metrics = await supabase.get_user_metrics(user_id)
            
            # Get recent jobs for additional metrics
            recent_jobs = await supabase.get_user_jobs(user_id, limit=50)
            
            # Calculate time-based metrics
            today = datetime.now().date()
            last_week = today - timedelta(days=7)
            
            today_jobs = []
            week_jobs = []
            
            for job in recent_jobs:
                job_time = datetime.fromisoformat(j["created_at"]).date()
                if job_time == today:
                    today_jobs.append(job)
                if job_time >= last_week:
                    week_jobs.append(job)
            
            # Calculate success rates
            today_success_rate = self._calculate_success_rate(today_jobs)
            week_success_rate = self._calculate_success_rate(week_jobs)
            
            # Get recent errors
            recent_errors = self._get_recent_errors(recent_jobs, hours=24)
            
            # Get active monitoring jobs for user
            user_active_jobs = [
                job_id for job_id, info in self.active_jobs.items() 
                if info["user_id"] == user_id
            ]
            
            # Prepare comprehensive metrics
            metrics_data = {
                **db_metrics,
                "today_jobs": len(today_jobs),
                "week_jobs": len(week_jobs),
                "today_success_rate": today_success_rate,
                "week_success_rate": week_success_rate,
                "active_monitoring": len(user_active_jobs),
                "recent_errors": recent_errors,
                "performance_metrics": self.performance_metrics.get_performance_summary(),
                "system_health": await self._get_system_health(),
                "last_updated": current_time.isoformat()
            }
            
            # Update cache with size limit
            self._update_cache(cache_key, metrics_data, current_time)
            
            return metrics_data
            
        except Exception as e:
            logger.error(f"Failed to get realtime metrics for user {user_id}: {e}")
            return self._get_fallback_metrics(current_time)
    
    async def get_system_wide_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics for admin dashboard"""
        try:
            # Get performance metrics
            perf_metrics = self.performance_metrics.get_performance_summary()
            
            # Get system info
            system_info = {
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "active_connections": len(websocket_manager.active_connections),
                "uptime": (datetime.now() - self.system_metrics["start_time"]).total_seconds()
            }
            
            # Get active alerts
            active_alerts = [
                alert for alert in self.alert_manager.active_alerts.values() 
                if not alert.get("is_resolved", False)
            ]
            
            return {
                **self.system_metrics,
                **system_info,
                "performance_metrics": perf_metrics,
                "active_jobs_count": len(self.active_jobs),
                "active_alerts": active_alerts,
                "cache_size": len(self.metrics_cache),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system-wide metrics: {e}")
            return {}
    
    async def get_job_details(self, job_id: str) -> Dict[str, Any]:
        """Get detailed job information with enhanced data"""
        try:
            job = await supabase.get_job_by_id(job_id)
            if not job:
                return {"error": "Job not found"}
            
            # Add enhanced monitoring information
            monitoring_info = {}
            if job_id in self.active_jobs:
                job_info = self.active_jobs[job_id]
                elapsed_time = (datetime.now() - job_info["start_time"]).total_seconds()
                
                monitoring_info = {
                    "is_active": True,
                    "progress": job_info["progress"],
                    "start_time": job_info["start_time"].isoformat(),
                    "last_update": job_info["last_update"].isoformat(),
                    "elapsed_time": elapsed_time,
                    "user_id": job_info["user_id"]
                }
           else:
                monitoring_info = {"is_active": False}
            
            # Add performance data if available
            performance_data = {
                "processing_time": None,
                "records_per_second": None
            }
            
            if job.get("created_at") and job.get("completed_at"):
                start_time = datetime.fromisoformat(job["created_at"])
                end_time = datetime.fromisoformat(job["completed_at"])
                processing_time = (end_time - start_time).total_seconds()
                
                performance_data["processing_time"] = processing_time
                if processing_time > 0 and job.get("total_records"):
                    performance_data["records_per_second"] = job["total_records"] / processing_time
            
            return {
                **job,
                **monitoring_info,
                "performance": performance_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get job details for {job_id}: {e}")
            return {"error": str(e)}
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            # Test database connection
            db_test = await supabase.client.from_('profiles').select('count', count='exact').limit(1).execute()
            db_health = "healthy" if db_test else "unhealthy"
            
            # Check memory usage
            memory_usage = psutil.virtual_memory().percent
            memory_health = "healthy" if memory_usage < 80 else "warning"
            
            # Check active connections
            connections_health = "healthy" if len(self.active_jobs) < 100 else "warning"
            
            return {
                "database": db_health,
                "memory": memory_health,
                "connections": connections_health,
                "overall": "healthy" if all([
                    db_health == "healthy",
                    memory_health == "healthy",
                    connections_health == "healthy"
                ]) else "degraded"
            }
        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {"overall": "unhealthy", "error": str(e)}
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self.metrics_cache:
            return False
        
        cache_entry = self.metrics_cache[cache_key]
        cache_age = (datetime.now() - cache_entry["timestamp"]).total_seconds()
        
        return cache_age < self.cache_ttl
    
    def _update_cache(self, cache_key: str, data: Dict[str, Any], timestamp: datetime):
        """Update cache with size management"""
        # Remove oldest entries if cache is too large
        if len(self.metrics_cache) >= self.max_cache_size:
            oldest_key = min(
                self.metrics_cache.keys(),
                key=lambda k: self.metrics_cache[k]["timestamp"]
            )
            del self.metrics_cache[oldest_key]
        
        self.metrics_cache[cache_key] = {
            "data": data,
            "timestamp": timestamp
        }
    
    def _calculate_success_rate(self, jobs: List[Dict]) -> float:
        """Calculate success rate from job list"""
        if not jobs:
            return 0.0
        
        completed_jobs = [j for j in jobs if j.get("status") == "completed"]
        return (len(completed_jobs) / len(jobs)) * 100
    
    def _get_recent_errors(self, jobs: List[Dict], hours: int = 24) -> List[Dict]:
        """Get recent errors from job list"""
        recent_errors = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for job in jobs:
            job_time = datetime.fromisoformat(job["created_at"])
            if job_time >= cutoff_time and job.get("error_log"):
                for error in job["error_log"][:5]:  # Last 5 errors per job
                    recent_errors.append({
                        "job_id": job["job_id"],
                        "filename": job["filename"],
                        "error": error,
                        "timestamp": job["created_at"],
                        "mapping_name": job.get("column_mappings", {}).get("mapping_name", "Unknown")
                    })
        
        return sorted(recent_errors, key=lambda x: x["timestamp"], reverse=True)[:20]
    
    def _get_fallback_metrics(self, timestamp: datetime) -> Dict[str, Any]:
        """Get fallback metrics when database is unavailable"""
        return {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "processing_jobs": 0,
            "success_rate": 0,
            "today_jobs": 0,
            "week_jobs": 0,
            "today_success_rate": 0,
            "week_success_rate": 0,
            "active_monitoring": 0,
            "recent_errors": [],
            "performance_metrics": {},
            "system_health": {"overall": "unhealthy"},
            "last_updated": timestamp.isoformat(),
            "error": "Failed to fetch metrics from database"
        }
    
    async def cleanup_old_monitoring(self):
        """Clean up old monitoring sessions with enhanced logic"""
        current_time = datetime.now()
        expired_jobs = []
        
        for job_id, job_info in self.active_jobs.items():
            time_since_update = current_time - job_info["last_update"]
            
            # Different timeouts based on job stage
            timeout = timedelta(hours=2)  # Default 2 hours
            
            if job_info["progress"]["current_stage"] in ["initializing", "validating"]:
                timeout = timedelta(minutes=30)  # 30 minutes for early stages
            elif job_info["progress"]["current_stage"] == "sending_to_erp":
                timeout = timedelta(hours=1)  # 1 hour for ERP operations
            
            if time_since_update > timeout:
                expired_jobs.append(job_id)
        
        for job_id in expired_jobs:
            logger.warning(f"Job {job_id} exceeded timeout, marking as failed")
            await self.complete_job_monitoring(
                job_id, 
                "timeout",
                {"reason": "Job exceeded maximum allowed processing time"}
            )
        
        # Clean up old cache entries
        old_cache_keys = []
        for cache_key, cache_entry in self.metrics_cache.items():
            cache_age = (current_time - cache_entry["timestamp"]).total_seconds()
            if cache_age > self.cache_ttl * 2:  # Double TTL for cleanup
                old_cache_keys.append(cache_key)
        
        for cache_key in old_cache_keys:
            del self.metrics_cache[cache_key]

# Global monitor instance
live_monitor = LiveMonitor()

# Background tasks
async def monitoring_cleanup_task():
    """Background task to clean up old monitoring sessions"""
    while True:
        try:
            await live_monitor.cleanup_old_monitoring()
            await asyncio.sleep(300)  # Run every 5 minutes
        except Exception as e:
            logger.error(f"Monitoring cleanup error: {e}")
            await asyncio.sleep(60)

async def performance_metrics_task():
    """Background task to collect performance metrics"""
    while True:
        try:
            # Record system metrics
            live_monitor.performance_metrics.record_memory_usage()
            
            # Check for alerts
            system_metrics = await live_monitor.get_system_wide_metrics()
            await live_monitor.alert_manager.check_and_trigger_alerts(
                system_metrics.get("performance_metrics", {})
            )
            
            await asyncio.sleep(60)  # Run every minute
            
        except Exception as e:
            logger.error(f"Performance metrics task error: {e}")
            await asyncio.sleep(30)
