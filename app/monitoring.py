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
from .models import ProgressUpdate, WebSocketMessage, WebSocketMessageType, ERPIntegrationProgress, ERPNextEndpoint
from .erp_integration import erp_integration

# Configure logging
logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ERPNextMetrics:
    """ERPNext specific performance metrics tracking"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.api_response_times = defaultdict(lambda: deque(maxlen=window_size))
        self.api_success_rates = defaultdict(lambda: deque(maxlen=window_size))
        self.circuit_breaker_state_changes = deque(maxlen=50)
        self.batch_processing_times = deque(maxlen=window_size)
        self.erp_connection_status = deque(maxlen=window_size)
    
    def record_api_response_time(self, endpoint: str, response_time: float):
        """Record API response time for specific endpoint"""
        self.api_response_times[endpoint].append(response_time)
    
    def record_api_success(self, endpoint: str, success: bool):
        """Record API success/failure for specific endpoint"""
        self.api_success_rates[endpoint].append(1 if success else 0)
    
    def record_circuit_breaker_change(self, old_state: str, new_state: str, endpoint: str):
        """Record circuit breaker state changes"""
        self.circuit_breaker_state_changes.append({
            "timestamp": datetime.now().isoformat(),
            "old_state": old_state,
            "new_state": new_state,
            "endpoint": endpoint
        })
    
    def record_batch_processing_time(self, processing_time: float):
        """Record batch processing time"""
        self.batch_processing_times.append(processing_time)
    
    def record_connection_status(self, is_connected: bool):
        """Record ERP connection status"""
        self.erp_connection_status.append(1 if is_connected else 0)
    
    def get_erpnext_metrics_summary(self) -> Dict[str, Any]:
        """Get ERPNext specific metrics summary"""
        endpoint_metrics = {}
        
        for endpoint in self.api_response_times:
            response_times = list(self.api_response_times[endpoint])
            success_rates = list(self.api_success_rates[endpoint])
            
            if response_times:
                endpoint_metrics[endpoint] = {
                    "avg_response_time": sum(response_times) / len(response_times),
                    "max_response_time": max(response_times) if response_times else 0,
                    "min_response_time": min(response_times) if response_times else 0,
                    "success_rate": (sum(success_rates) / len(success_rates) * 100) if success_rates else 0,
                    "total_calls": len(response_times)
                }
        
        return {
            "endpoint_metrics": endpoint_metrics,
            "avg_batch_processing_time": sum(self.batch_processing_times) / len(self.batch_processing_times) if self.batch_processing_times else 0,
            "connection_success_rate": (sum(self.erp_connection_status) / len(self.erp_connection_status) * 100) if self.erp_connection_status else 0,
            "recent_circuit_breaker_changes": list(self.circuit_breaker_state_changes)[-10:],  # Last 10 changes
            "total_endpoints_monitored": len(endpoint_metrics)
        }

class PerformanceMetrics:
    """Enhanced performance metrics tracking with ERPNext support"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.processing_times = deque(maxlen=window_size)
        self.error_rates = deque(maxlen=window_size)
        self.memory_usage = deque(maxlen=window_size)
        self.request_rates = deque(maxlen=window_size)
        self.erpnext_metrics = ERPNextMetrics(window_size)
    
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
        """Get comprehensive performance summary including ERPNext metrics"""
        base_metrics = {
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
        
        # Add ERPNext metrics
        erpnext_summary = self.erpnext_metrics.get_erpnext_metrics_summary()
        base_metrics["erpnext_metrics"] = erpnext_summary
        
        return base_metrics

class AlertManager:
    """Enhanced alert management system with ERPNext specific alerts"""
    
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
            },
            "erpnext_connection": {
                "level": AlertLevel.CRITICAL,
                "message": "ERPNext connection lost"
            },
            "circuit_breaker_open": {
                "level": AlertLevel.ERROR,
                "message": "Circuit breaker opened for ERPNext endpoint"
            },
            "high_erpnext_latency": {
                "threshold": 10.0,  # 10 seconds
                "level": AlertLevel.WARNING,
                "message": "High ERPNext API latency detected"
            },
            "erpnext_api_failure": {
                "threshold": 5,  # 5 consecutive failures
                "level": AlertLevel.ERROR,
                "message": "Multiple consecutive ERPNext API failures"
            }
        }
        self.active_alerts = {}
        self.erpnext_failure_count = defaultdict(int)
    
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
        
        # Check ERPNext specific alerts
        erpnext_alerts = await self._check_erpnext_alerts(metrics)
        triggered_alerts.extend(erpnext_alerts)
        
        return triggered_alerts
    
    async def _check_erpnext_alerts(self, metrics: Dict[str, Any]) -> List[str]:
        """Check ERPNext specific alert conditions"""
        triggered_alerts = []
        
        # Check ERPNext connection
        erpnext_metrics = metrics.get("erpnext_metrics", {})
        connection_rate = erpnext_metrics.get("connection_success_rate", 100)
        
        if connection_rate < 50:  # Less than 50% success rate
            alert_id = await self.trigger_alert(
                "erpnext_connection",
                f"ERPNext connection success rate is {connection_rate:.1f}%",
                self.alert_rules["erpnext_connection"]["level"]
            )
            triggered_alerts.append(alert_id)
        
        # Check circuit breaker status
        circuit_changes = erpnext_metrics.get("recent_circuit_breaker_changes", [])
        for change in circuit_changes[-3:]:  # Check last 3 changes
            if change["new_state"] == "OPEN":
                alert_id = await self.trigger_alert(
                    "circuit_breaker_open",
                    f"Circuit breaker opened for {change['endpoint']}",
                    self.alert_rules["circuit_breaker_open"]["level"]
                )
                triggered_alerts.append(alert_id)
        
        # Check API latency
        endpoint_metrics = erpnext_metrics.get("endpoint_metrics", {})
        for endpoint, metrics_data in endpoint_metrics.items():
            avg_response_time = metrics_data.get("avg_response_time", 0)
            if avg_response_time > self.alert_rules["high_erpnext_latency"]["threshold"]:
                alert_id = await self.trigger_alert(
                    "high_erpnext_latency",
                    f"High latency for {endpoint}: {avg_response_time:.2f}s",
                    self.alert_rules["high_erpnext_latency"]["level"]
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
            self.active_alert s[alert_id]["resolution_message"] = resolution_message
            
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
    """Enhanced live monitoring system with ERPNext integration tracking"""
    
    def __init__(self):
        self.active_jobs = {}
        self.metrics_cache = {}
        self.cache_ttl = 30  # seconds
        self.max_cache_size = 1000
        self.performance_metrics = PerformanceMetrics()
        self.alert_manager = AlertManager()
        self.job_history = defaultdict(list)
        self.erpnext_integration_history = deque(maxlen=100)
        self.system_metrics = {
            "start_time": datetime.now(),
            "total_processed_jobs": 0,
            "total_processed_records": 0,
            "total_errors": 0,
            "total_erpnext_calls": 0,
            "successful_erpnext_calls": 0
        }
    
    async def start_erpnext_integration_monitoring(self, job_id: str, endpoint: ERPNextEndpoint, total_records: int):
        """Start monitoring ERPNext integration process"""
        try:
            integration_data = {
                "job_id": job_id,
                "endpoint": endpoint.value,
                "start_time": datetime.now(),
                "total_records": total_records,
                "processed_records": 0,
                "successful_records": 0,
                "failed_records": 0,
                "circuit_breaker_state": "CLOSED",
                "batches_processed": 0
            }
            
            self.erpnext_integration_history.append(integration_data)
            
            # Broadcast ERP integration start
            await websocket_manager.broadcast_message(
                WebSocketMessage(
                    type=WebSocketMessageType.ERP_INTEGRATION_PROGRESS,
                    data={
                        "type": "integration_started",
                        "job_id": job_id,
                        "endpoint": endpoint.value,
                        "total_records": total_records,
                        "timestamp": datetime.now().isoformat()
                    },
                    timestamp=datetime.now()
                )
            )
            
            logger.info(f"Started ERPNext integration monitoring for job {job_id}, endpoint: {endpoint.value}")
            
        except Exception as e:
            logger.error(f"Failed to start ERPNext integration monitoring: {e}")
    
    async def update_erpnext_integration_progress(self, job_id: str, progress_data: Dict[str, Any]):
        """Update ERPNext integration progress"""
        try:
            # Find the integration record
            integration_record = None
            for record in self.erpnext_integration_history:
                if record["job_id"] == job_id:
                    integration_record = record
                    break
            
            if not integration_record:
                return
            
            # Update progress
            integration_record.update({
                "processed_records": progress_data.get("processed", 0),
                "successful_records": progress_data.get("successful", 0),
                "failed_records": progress_data.get("failed", 0),
                "batches_processed": progress_data.get("batches_processed", 0),
                "last_update": datetime.now()
            })
            
            # Update system metrics
            self.system_metrics["total_erpnext_calls"] += progress_data.get("api_calls", 0)
            self.system_metrics["successful_erpnext_calls"] += progress_data.get("successful_api_calls", 0)
            
            # Record performance metrics
            if "processing_time" in progress_data:
                self.performance_metrics.record_processing_time(progress_data["processing_time"])
                self.performance_metrics.erpnext_metrics.record_batch_processing_time(progress_data["processing_time"])
            
            if "api_response_time" in progress_data:
                self.performance_metrics.erpnext_metrics.record_api_response_time(
                    progress_data.get("endpoint", "unknown"),
                    progress_data["api_response_time"]
                )
            
            # Broadcast progress update
            progress_update = ERPIntegrationProgress(
                job_id=job_id,
                endpoint=ERPNextEndpoint(progress_data.get("endpoint", "unknown")),
                processed=progress_data.get("processed", 0),
                successful=progress_data.get("successful", 0),
                failed=progress_data.get("failed", 0),
                timestamp=datetime.now(),
                circuit_breaker_state=progress_data.get("circuit_breaker_state", "CLOSED")
            )
            
            await websocket_manager.broadcast_message(progress_update.dict())
            
            logger.debug(f"ERPNext integration progress for {job_id}: {progress_data.get('processed', 0)} records")
            
        except Exception as e:
            logger.error(f"Failed to update ERPNext integration progress: {e}")
    
    async def record_erpnext_api_call(self, endpoint: str, success: bool, response_time: float):
        """Record ERPNext API call for monitoring"""
        try:
            # Record in performance metrics
            self.performance_metrics.erpnext_metrics.record_api_response_time(endpoint, response_time)
            self.performance_metrics.erpnext_metrics.record_api_success(endpoint, success)
            
            # Update system metrics
            self.system_metrics["total_erpnext_calls"] += 1
            if success: self.system_metrics["successful_erpnext_calls"] += 1
            
            # Check for alert conditions
            if not success:
                # Track consecutive failures for alerting
                self.alert_manager.erpnext_failure_count[endpoint] += 1
                
                failure_count = self.alert_manager.erpnext_failure_count[endpoint]
                if failure_count >= self.alert_manager.alert_rules["erpnext_api_failure"]["threshold"]:
                    await self.alert_manager.trigger_alert(
                        "erpnext_api_failure",
                        f"Consecutive {failure_count} failures for {endpoint}",
                        AlertLevel.ERROR
                    )
            else:
                # Reset failure count on success
                self.alert_manager.erpnext_failure_count[endpoint] = 0
            
        except Exception as e:
            logger.error(f"Failed to record ERPNext API call: {e}")
    
    async def record_circuit_breaker_change(self, endpoint: str, old_state: str, new_state: str):
        """Record circuit breaker state change"""
        try:
            self.performance_metrics.erpnext_metrics.record_circuit_breaker_change(
                old_state, new_state, endpoint
            )
            
            # Broadcast state change
            await websocket_manager.broadcast_message(
                WebSocketMessage(
                    type=WebSocketMessageType.SYSTEM_NOTIFICATION,
                    data={
                        "type": "circuit_breaker_change",
                        "endpoint": endpoint,
                        "old_state": old_state,
                        "new_state": new_state,
                        "timestamp": datetime.now().isoformat()
                    },
                    timestamp=datetime.now()
                )
            )
            
            logger.info(f"Circuit breaker state changed for {endpoint}: {old_state} -> {new_state}")
            
        except Exception as e:
            logger.error(f"Failed to record circuit breaker change: {e}")
    
    async def record_erpnext_connection_status(self, is_connected: bool):
        """Record ERPNext connection status"""
        try:
            self.performance_metrics.erpnext_metrics.record_connection_status(is_connected)
            
            if not is_connected:
                await self.alert_manager.trigger_alert(
                    "erpnext_connection",
                    "ERPNext connection lost",
                    AlertLevel.CRITICAL
                )
            else:
                # Resolve any existing connection alerts
                for alert_id, alert in self.alert_manager.active_alerts.items():
                    if alert["type"] == "erpnext_connection" and not alert.get("is_resolved", False):
                        await self.alert_manager.resolve_alert(alert_id, "ERPNext connection restored")
            
        except Exception as e:
            logger.error(f"Failed to record ERPNext connection status: {e}")
    
    # Existing methods remain the same but enhanced with ERPNext integration
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
                "metadata": initial_data,
                "erpnext_integration": {
                    "enabled": initial_data.get("erp_integration", False),
                    "endpoint": initial_data.get("erp_endpoint"),
                    "status": "pending"
                }
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
            
            # Update ERPNext integration status if present
            if "erp_integration_status" in progress:
                job_info["erpnext_integration"]["status"] = progress["erp_integration_status"]
            
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
    
    async def get_system_wide_metrics(self) -> Dict[str, Any]:
        """Get enhanced system-wide metrics including ERPNext integration"""
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
            
            # Get ERPNext integration status
            erpnext_status = await erp_integration.get_system_status()
            
            return {
                **self.system_metrics,
                **system_info,
                "performance_metrics": perf_metrics,
                "active_jobs_count": len(self.active_jobs),
                "active_alerts": active_alerts,
                "cache_size": len(self.metrics_cache),
                "erpnext_integration_status": erpnext_status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system-wide metrics: {e}")
            return {}
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self.metrics_cache:
            return False
        
        cache_entry = self.metrics_cache[cache_key]
        cache_age = (datetime.now() - cache_entry["timestamp"]).total_seconds()
        
        return cache_age < self.cache_ttl
    
    def _update_cache(self, cache_key: str, data: Any, timestamp: datetime):
        """Update cache with size limit"""
        # Remove oldest entries if cache is full
        if len(self.metrics_cache) >= self.max_cache_size:
            oldest_key = min(self.metrics_cache.keys(), 
                           key=lambda k: self.metrics_cache[k]["timestamp"])
            del self.metrics_cache[oldest_key]
        
        self.metrics_cache[cache_key] = {
            "data": data,
            "timestamp": timestamp
        }
    
    def _calculate_success_rate(self, jobs: List[Dict]) -> float:
        """Calculate success rate from job list"""
        if not jobs:
            return 100.0
        
        successful = sum(1 for job in jobs if job.get("status") == "completed")
        return (successful / len(jobs)) * 100
    
    def _get_recent_errors(self, jobs: List[Dict], hours: int = 24) -> List[Dict]:
        """Get recent errors from job list"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_errors = []
        for job in jobs:
            job_time = datetime.fromisoformat(job["created_at"])
            if job_time >= cutoff_time and job.get("status") == "failed":
                recent_errors.append({
                    "job_id": job["job_id"],
                    "error": job.get("error_message", "Unknown error"),
                    "timestamp": job["created_at"]
                })
        
        return recent_errors[-10:]  # Return last 10 errors
    
    def _get_fallback_metrics(self, timestamp: datetime) -> Dict[str, Any]:
        """Get fallback metrics when database query fails"""
        return {
            "today_jobs": 0,
            "week_jobs": 0,
            "today_success_rate": 0,
            "week_success_rate": 0,
            "active_monitoring": 0,
            "recent_errors": [],
            "performance_metrics": self.performance_metrics.get_performance_summary(),
            "system_health": {"status": "unknown"},
            "last_updated": timestamp.isoformat()
        }
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        try:
            # Test database connection
            supabase.client.from_('profiles').select('id').limit(1).execute()
            db_health = "healthy"
        except:
            db_health = "unhealthy"
        
        # Test ERPNext connection if available
        if erp_integration.erpnext_client:
            erp_status = await erp_integration.test_connection()
            erp_health = "healthy" if erp_status["success"] else "unhealthy"
        else:
            erp_health = "not_configured"
        
        return {
            "database": db_health,
            "erpnext": erp_health,
            "websocket": "healthy" if websocket_manager else "unhealthy",
            "overall": "healthy" if db_health == "healthy" else "degraded"
        }

# Global monitor instance
live_monitor = LiveMonitor()
       
