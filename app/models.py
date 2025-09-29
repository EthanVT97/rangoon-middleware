from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company: str = ""
    role: UserRole = UserRole.USER

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    company: str
    role: UserRole
    created_at: datetime

class ColumnMappingCreate(BaseModel):
    mapping_name: str
    description: str = ""
    source_columns: List[Dict[str, Any]]
    target_columns: Dict[str, Any]
    mapping_rules: Dict[str, Any] = {}
    erp_endpoint: str = "customers"

class ColumnMappingResponse(BaseModel):
    id: str
    mapping_name: str
    description: str
    source_columns: List[Dict[str, Any]]
    target_columns: Dict[str, Any]
    mapping_rules: Dict[str, Any]
    erp_endpoint: str
    created_by: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class ImportJobCreate(BaseModel):
    mapping_id: str
    filename: str
    file_content: str  # Base64 encoded

class ImportJobResponse(BaseModel):
    job_id: str
    mapping_id: str
    filename: str
    status: str
    total_records: int
    processed_records: int
    failed_records: int
    error_log: List[Dict[str, Any]]
    erp_response: Dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

class ERPConnectionCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    endpoints: Dict[str, str]

class ERPConnectionResponse(BaseModel):
    id: str
    name: str
    base_url: str
    endpoints: Dict[str, str]
    is_active: bool
    created_at: datetime

class SystemMetrics(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    processing_jobs: int
    success_rate: float
    avg_processing_time: float
    recent_errors: List[Dict[str, Any]]
    last_updated: datetime

class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    timestamp: datetime
