from supabase import create_client, Client
from config import settings
from typing import Dict, Any, List
import json

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url, 
            settings.supabase_key
        )
    
    # User Management
    async def create_user(self, email: str, password: str, user_data: Dict[str, Any]):
        """Create new user"""
        try:
            result = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_data
                }
            })
            return result
        except Exception as e:
            raise Exception(f"User creation failed: {str(e)}")
    
    async def get_user(self, user_id: str):
        """Get user by ID"""
        try:
            result = self.client.from_("profiles").select("*").eq("id", user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise Exception(f"User fetch failed: {str(e)}")
    
    # Column Mappings
    async def create_column_mapping(self, mapping_data: Dict[str, Any], user_id: str):
        """Create new column mapping"""
        try:
            mapping_data["created_by"] = user_id
            result = self.client.from_("column_mappings").insert(mapping_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise Exception(f"Mapping creation failed: {str(e)}")
    
    async def get_user_mappings(self, user_id: str):
        """Get all mappings for a user"""
        try:
            result = self.client.from_("column_mappings")\
                .select("*")\
                .eq("created_by", user_id)\
                .eq("is_active", True)\
                .execute()
            return result.data
        except Exception as e:
            raise Exception(f"Mapping fetch failed: {str(e)}")
    
    # Import Jobs
    async def create_import_job(self, job_data: Dict[str, Any]):
        """Create new import job"""
        try:
            result = self.client.from_("import_jobs").insert(job_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise Exception(f"Job creation failed: {str(e)}")
    
    async def update_job_status(self, job_id: str, updates: Dict[str, Any]):
        """Update job status"""
        try:
            result = self.client.from_("import_jobs")\
                .update(updates)\
                .eq("job_id", job_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise Exception(f"Job update failed: {str(e)}")
    
    async def get_job_by_id(self, job_id: str):
        """Get job by ID"""
        try:
            result = self.client.from_("import_jobs")\
                .select("*, column_mappings(mapping_name)")\
                .eq("job_id", job_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise Exception(f"Job fetch failed: {str(e)}")
    
    async def get_user_jobs(self, user_id: str, limit: int = 50):
        """Get user's import jobs"""
        try:
            result = self.client.from_("import_jobs")\
                .select("*, column_mappings(mapping_name)")\
                .eq("created_by", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return result.data
        except Exception as e:
            raise Exception(f"Jobs fetch failed: {str(e)}")
    
    # Real-time Subscriptions
    def subscribe_to_job_updates(self, user_id: str, callback):
        """Subscribe to job updates for real-time monitoring"""
        try:
            subscription = self.client.from_("import_jobs")\
                .on("UPDATE", callback)\
                .eq("created_by", user_id)\
                .subscribe()
            return subscription
        except Exception as e:
            raise Exception(f"Subscription failed: {str(e)}")

# Global Supabase client instance
supabase = SupabaseClient()
