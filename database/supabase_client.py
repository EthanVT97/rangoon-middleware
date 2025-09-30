from supabase import create_client, Client
from config import settings
from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime, timedelta
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        try:
            self.client: Client = create_client(
                settings.supabase_url, 
                settings.supabase_key
            )
            self._connected = False
            self._test_connection()
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Supabase client initialization failed: {str(e)}")
            raise
    
    def _test_connection(self):
        """Test database connection"""
        try:
            # Simple query to test connection
            result = self.client.from_("profiles").select("count", count="exact").limit(1).execute()
            self._connected = True
            logger.info("Supabase connection test passed")
        except Exception as e:
            self._connected = False
            logger.error(f"Supabase connection test failed: {str(e)}")
            raise
    
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self._connected
    
    # Enhanced User Management with RBAC
    async def create_user(self, email: str, password: str, user_data: Dict[str, Any]):
        """Create new user with enhanced error handling"""
        try:
            result = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        **user_data,
                        "created_at": datetime.utcnow().isoformat(),
                        "is_active": True,
                        "role": user_data.get('role', 'user')
                    }
                }
            })
            
            if result.user:
                # Create user profile
                profile_data = {
                    "id": result.user.id,
                    "email": email,
                    "username": user_data.get('username'),
                    "full_name": user_data.get('full_name'),
                    "role": user_data.get('role', 'user'),
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat(),
                    "last_login": None
                }
                
                await self._create_user_profile(profile_data)
                logger.info(f"User created successfully: {email}")
            
            return result
        except Exception as e:
            logger.error(f"User creation failed for {email}: {str(e)}")
            raise Exception(f"User creation failed: {str(e)}")
    
    async def _create_user_profile(self, profile_data: Dict[str, Any]):
        """Create user profile with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = self.client.from_("profiles").insert(profile_data).execute()
                return result.data[0] if result.data else None
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Profile creation failed after {max_retries} attempts: {str(e)}")
                    raise
                await asyncio.sleep(1)  # Wait before retry
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID with enhanced data"""
        try:
            result = self.client.from_("profiles")\
                .select("*, user_preferences(*)")\
                .eq("id", user_id)\
                .eq("is_active", True)\
                .execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"User fetch failed for {user_id}: {str(e)}")
            return None
    
    async def update_user_last_login(self, user_id: str):
        """Update user's last login timestamp"""
        try:
            updates = {
                "last_login": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            result = self.client.from_("profiles")\
                .update(updates)\
                .eq("id", user_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Last login update failed for {user_id}: {str(e)}")
    
    # Enhanced Column Mappings with Versioning
    async def create_column_mapping(self, mapping_data: Dict[str, Any], user_id: str):
        """Create new column mapping with version control"""
        try:
            mapping_data.update({
                "created_by": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "is_active": True,
                "version": mapping_data.get('version', '1.0.0'),
                "mapping_id": self._generate_mapping_id()
            })
            
            result = self.client.from_("column_mappings").insert(mapping_data).execute()
            
            if result.data:
                logger.info(f"Column mapping created: {mapping_data.get('mapping_name')}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Mapping creation failed: {str(e)}")
            raise Exception(f"Mapping creation failed: {str(e)}")
    
    async def get_user_mappings(self, user_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get all mappings for a user with filtering options"""
        try:
            query = self.client.from_("column_mappings")\
                .select("*")\
                .eq("created_by", user_id)\
                .order("created_at", desc=True)
            
            if not include_inactive:
                query = query.eq("is_active", True)
            
            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Mapping fetch failed for user {user_id}: {str(e)}")
            return []
    
    async def get_mapping_by_id(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Get specific mapping by ID"""
        try:
            result = self.client.from_("column_mappings")\
                .select("*, profiles(email, username)")\
                .eq("mapping_id", mapping_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Mapping fetch failed for {mapping_id}: {str(e)}")
            return None
    
    async def deactivate_mapping(self, mapping_id: str, user_id: str):
        """Soft delete mapping"""
        try:
            updates = {
                "is_active": False,
                "deactivated_at": datetime.utcnow().isoformat(),
                "deactivated_by": user_id
            }
            result = self.client.from_("column_mappings")\
                .update(updates)\
                .eq("mapping_id", mapping_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Mapping deactivation failed for {mapping_id}: {str(e)}")
            raise Exception(f"Mapping deactivation failed: {str(e)}")
    
    # Enhanced Import Jobs with ERP Integration Tracking
    async def create_import_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create new import job with enhanced tracking"""
        try:
            job_data.update({
                "job_id": self._generate_job_id(),
                "created_at": datetime.utcnow().isoformat(),
                "status": "pending",
                "is_active": True,
                "retry_count": 0,
                "processing_stage": "initialized"
            })
            
            result = self.client.from_("import_jobs").insert(job_data).execute()
            
            if result.data:
                logger.info(f"Import job created: {job_data['job_id']}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Job creation failed: {str(e)}")
            raise Exception(f"Job creation failed: {str(e)}")
    
    async def update_job_status(self, job_id: str, updates: Dict[str, Any]):
        """Update job status with comprehensive tracking"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            
            # Track status changes
            if 'status' in updates:
                updates['status_updated_at'] = datetime.utcnow().isoformat()
            
            result = self.client.from_("import_jobs")\
                .update(updates)\
                .eq("job_id", job_id)\
                .execute()
            
            if result.data:
                logger.info(f"Job {job_id} updated: {updates.get('status', 'unknown')}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Job update failed for {job_id}: {str(e)}")
            raise Exception(f"Job update failed: {str(e)}")
    
    async def increment_retry_count(self, job_id: str):
        """Increment job retry count"""
        try:
            result = self.client.from_("import_jobs")\
                .select("retry_count")\
                .eq("job_id", job_id)\
                .execute()
            
            if result.data:
                current_count = result.data[0].get('retry_count', 0)
                await self.update_job_status(job_id, {"retry_count": current_count + 1})
        except Exception as e:
            logger.error(f"Retry count increment failed for {job_id}: {str(e)}")
    
    async def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID with related data"""
        try:
            result = self.client.from_("import_jobs")\
                .select("*, column_mappings(*), profiles(email, username)")\
                .eq("job_id", job_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Job fetch failed for {job_id}: {str(e)}")
            return None
    
    async def get_user_jobs(self, user_id: str, limit: int = 50, 
                          status_filter: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """Get user's import jobs with advanced filtering"""
        try:
            since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            query = self.client.from_("import_jobs")\
                .select("*, column_mappings(mapping_name, version), profiles(email, username)")\
                .eq("created_by", user_id)\
                .gte("created_at", since_date)\
                .order("created_at", desc=True)\
                .limit(limit)
            
            if status_filter and status_filter != 'all':
                query = query.eq("status", status_filter)
            
            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Jobs fetch failed for user {user_id}: {str(e)}")
            return []
    
    # Enhanced Job Statistics and Analytics
    async def get_job_statistics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive job statistics"""
        try:
            since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Get basic counts
            result = self.client.from_("import_jobs")\
                .select("status", count="exact")\
                .eq("created_by", user_id)\
                .gte("created_at", since_date)\
                .execute()
            
            status_counts = {}
            if hasattr(result, 'count'):
                # Process status counts
                pass
            
            # Get success rate
            success_rate = await self._calculate_success_rate(user_id, since_date)
            
            # Get average processing time
            avg_time = await self._calculate_avg_processing_time(user_id, since_date)
            
            return {
                "total_jobs": sum(status_counts.values()) if status_counts else 0,
                "status_counts": status_counts,
                "success_rate": success_rate,
                "avg_processing_time": avg_time,
                "time_period_days": days
            }
        except Exception as e:
            logger.error(f"Job statistics failed for user {user_id}: {str(e)}")
            return {}
    
    async def _calculate_success_rate(self, user_id: str, since_date: str) -> float:
        """Calculate job success rate"""
        try:
            result = self.client.from_("import_jobs")\
                .select("status", count="exact")\
                .eq("created_by", user_id)\
                .gte("created_at", since_date)\
                .execute()
            
            # Implementation for success rate calculation
            return 0.0
        except Exception as e:
            logger.error(f"Success rate calculation failed: {str(e)}")
            return 0.0
    
    async def _calculate_avg_processing_time(self, user_id: str, since_date: str) -> float:
        """Calculate average job processing time"""
        try:
            # Implementation for average processing time
            return 0.0
        except Exception as e:
            logger.error(f"Avg processing time calculation failed: {str(e)}")
            return 0.0
    
    # Enhanced Real-time Subscriptions with Error Handling
    def subscribe_to_job_updates(self, user_id: str, callback):
        """Subscribe to job updates for real-time monitoring"""
        try:
            subscription = self.client.from_("import_jobs")\
                .on("UPDATE", callback)\
                .eq("created_by", user_id)\
                .subscribe()
            
            logger.info(f"Real-time subscription started for user {user_id}")
            return subscription
        except Exception as e:
            logger.error(f"Subscription failed for user {user_id}: {str(e)}")
            raise Exception(f"Subscription failed: {str(e)}")
    
    def subscribe_to_system_events(self, callback):
        """Subscribe to system-wide events"""
        try:
            subscription = self.client.from_("system_events")\
                .on("INSERT", callback)\
                .subscribe()
            return subscription
        except Exception as e:
            logger.error(f"System events subscription failed: {str(e)}")
            raise Exception(f"System events subscription failed: {str(e)}")
    
    # ERP Integration Tracking
    async def log_erp_integration(self, job_id: str, erp_data: Dict[str, Any]):
        """Log ERP integration details"""
        try:
            log_entry = {
                "job_id": job_id,
                "erp_system": erp_data.get('erp_system'),
                "endpoint": erp_data.get('endpoint'),
                "request_data": erp_data.get('request_data'),
                "response_data": erp_data.get('response_data'),
                "status_code": erp_data.get('status_code'),
                "success": erp_data.get('success', False),
                "timestamp": datetime.utcnow().isoformat(),
                "processing_time": erp_data.get('processing_time')
            }
            
            result = self.client.from_("erp_integration_logs").insert(log_entry).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"ERP integration logging failed for job {job_id}: {str(e)}")
    
    # Circuit Breaker State Management
    async def update_circuit_breaker_state(self, erp_system: str, state: str, failures: int = 0):
        """Update circuit breaker state"""
        try:
            state_data = {
                "erp_system": erp_system,
                "state": state,
                "failures": failures,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            result = self.client.from_("circuit_breaker_states")\
                .upsert(state_data, on_conflict="erp_system")\
                .execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Circuit breaker state update failed for {erp_system}: {str(e)}")
    
    # Utility Methods
    def _generate_job_id(self) -> str:
        """Generate unique job ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = __import__('random').choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6)
        return f"JOB_{timestamp}_{''.join(random_suffix)}"
    
    def _generate_mapping_id(self) -> str:
        """Generate unique mapping ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = __import__('random').choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4)
        return f"MAP_{timestamp}_{''.join(random_suffix)}"
    
    # Context Manager for Database Operations
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions"""
        # Note: Supabase JavaScript client has transactions, but Python client may need manual handling
        try:
            yield self
        except Exception as e:
            logger.error(f"Transaction failed: {str(e)}")
            raise
    
    # Cleanup and Maintenance
    async def cleanup_old_jobs(self, days: int = 90):
        """Clean up old job records"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            result = self.client.from_("import_jobs")\
                .delete()\
                .lt("created_at", cutoff_date)\
                .execute()
            
            logger.info(f"Cleaned up jobs older than {days} days")
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            return []

# Global Supabase client instance with error handling
try:
    supabase = SupabaseClient()
except Exception as e:
    logger.error(f"Failed to initialize global Supabase client: {str(e)}")
    supabase = None
