from supabase import create_client, Client
from typing import Dict, Any, List, Optional
import os
from decouple import config

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(
            config("SUPABASE_URL"),
            config("SUPABASE_KEY")
        )
    
    # User Management Methods
    async def create_user(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create new user in Supabase Auth and profiles table"""
        try:
            # Create auth user
            auth_response = self.client.auth.sign_up({
                "email": user_data["email"],
                "password": user_data["password"],
                "options": {
                    "data": {
                        "full_name": user_data["full_name"],
                        "company": user_data.get("company", "")
                    }
                }
            })
            
            if auth_response.user:
                # Create profile in profiles table
                profile_data = {
                    "id": auth_response.user.id,
                    "email": user_data["email"],
                    "full_name": user_data["full_name"],
                    "company": user_data.get("company", ""),
                    "role": user_data.get("role", "user")
                }
                
                profile_response = self.client.from_("profiles").insert(profile_data).execute()
                return profile_response.data[0] if profile_response.data else None
            
            return None
            
        except Exception as e:
            raise Exception(f"User creation failed: {str(e)}")
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID from profiles table"""
        try:
            response = self.client.from_("profiles").select("*").eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"User fetch failed: {str(e)}")
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email from profiles table"""
        try:
            response = self.client.from_("profiles").select("*").eq("email", email).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"User fetch failed: {str(e)}")
    
    # Column Mappings Methods
    async def create_column_mapping(self, mapping_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create new column mapping"""
        try:
            response = self.client.from_("column_mappings").insert(mapping_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"Mapping creation failed: {str(e)}")
    
    async def get_user_mappings(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all column mappings for a user"""
        try:
            response = self.client.from_("column_mappings")\
                .select("*")\
                .eq("created_by", user_id)\
                .eq("is_active", True)\
                .order("created_at", desc=True)\
                .execute()
            return response.data
        except Exception as e:
            raise Exception(f"Mappings fetch failed: {str(e)}")
    
    async def get_mapping_by_id(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Get specific mapping by ID"""
        try:
            response = self.client.from_("column_mappings")\
                .select("*")\
                .eq("id", mapping_id)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"Mapping fetch failed: {str(e)}")
    
    # Import Jobs Methods
    async def create_import_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create new import job"""
        try:
            response = self.client.from_("import_jobs").insert(job_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"Job creation failed: {str(e)}")
    
    async def update_job_status(self, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update job status and progress"""
        try:
            response = self.client.from_("import_jobs")\
                .update(updates)\
                .eq("job_id", job_id)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"Job update failed: {str(e)}")
    
    async def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by job_id"""
        try:
            response = self.client.from_("import_jobs")\
                .select("*, column_mappings(mapping_name, description)")\
                .eq("job_id", job_id)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"Job fetch failed: {str(e)}")
    
    async def get_user_jobs(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's import jobs"""
        try:
            response = self.client.from_("import_jobs")\
                .select("*, column_mappings(mapping_name, description)")\
                .eq("created_by", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return response.data
        except Exception as e:
            raise Exception(f"Jobs fetch failed: {str(e)}")
    
    # ERP Connections Methods
    async def create_erp_connection(self, connection_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create ERP connection"""
        try:
            # Deactivate other connections
            self.client.from_("erp_connections").update({"is_active": False}).execute()
            
            response = self.client.from_("erp_connections").insert(connection_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"ERP connection creation failed: {str(e)}")
    
    async def get_active_erp_connection(self) -> Optional[Dict[str, Any]]:
        """Get active ERP connection"""
        try:
            response = self.client.from_("erp_connections")\
                .select("*")\
                .eq("is_active", True)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"ERP connection fetch failed: {str(e)}")
    
    # Monitoring Methods
    async def create_monitoring_log(self, log_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create monitoring log entry"""
        try:
            response = self.client.from_("monitoring_logs").insert(log_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"Monitoring log creation failed: {str(e)}")
    
    async def get_user_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get user metrics for dashboard"""
        try:
            # Get user's jobs for metrics
            jobs = await self.get_user_jobs(user_id, limit=1000)
            
            total_jobs = len(jobs)
            completed_jobs = len([j for j in jobs if j.get("status") == "completed"])
            failed_jobs = len([j for j in jobs if j.get("status") == "failed"])
            processing_jobs = len([j for j in jobs if j.get("status") in ["pending", "processing"]])
            
            success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            
            return {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "processing_jobs": processing_jobs,
                "success_rate": round(success_rate, 2)
            }
        except Exception as e:
            return {
                "total_jobs": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "processing_jobs": 0,
                "success_rate": 0
            }

# Global Supabase client instance
supabase = SupabaseClient()
