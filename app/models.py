from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import re
import uuid
from decimal import Decimal

# Custom validators
def validate_password_strength(password: str) -> str:
    """Validate password strength"""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    return password

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    MANAGER = "manager"

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VALIDATING = "validating"
    MAPPING = "mapping"
    SENDING_TO_ERP = "sending_to_erp"

class FileType(str, Enum):
    EXCEL = "excel"
    CSV = "csv"
    UNSUPPORTED = "unsupported"

class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

# User Management Models
class UserRegister(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name")
    company: str = Field("", max_length=100, description="Company name")
    role: UserRole = Field(UserRole.USER, description="User role")
    
    @validator('password')
    def validate_password(cls, v):
        return validate_password_strength(v)
    
    @validator('full_name')
    def validate_full_name(cls, v):
        if not re.match(r'^[a-zA-Z\s\-\.]+$', v):
            raise ValueError("Full name can only contain letters, spaces, hyphens, and periods")
        return v.strip()

class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: str = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    full_name: str = Field(..., description="Full name")
    company: str = Field(..., description="Company name")
    role: UserRole = Field(..., description="User role")
    is_active: bool = Field(..., description="Account status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

class UserProfileResponse(BaseModel):
    user: UserResponse
    metrics: Dict[str, Any] = Field(default_factory=dict)

# Column Mapping Models
class ColumnMappingRule(BaseModel):
    source_column: str = Field(..., description="Source column name")
    target_field: str = Field(..., description="Target field name")
    data_type: str = Field(..., description="Expected data type")
    required: bool = Field(False, description="Is this field required")
    transformation: Optional[str] = Field(None, description="Transformation rule")
    validation_rules: List[Dict[str, Any]] = Field(default_factory=list)

class ColumnMappingCreate(BaseModel):
    mapping_name: str = Field(..., min_length=1, max_length=100, description="Mapping name")
    description: str = Field("", max_length=500, description="Mapping description")
    source_columns: List[ColumnMappingRule] = Field(..., description="Source column definitions")
    target_columns: Dict[str, Any] = Field(..., description="Target column mapping")
    mapping_rules: Dict[str, Any] = Field(default_factory=dict, description="Additional mapping rules")
    erp_endpoint: str = Field("customers", description="ERP endpoint for this mapping")
    is_active: bool = Field(True, description="Mapping status")
    
    @validator('mapping_name')
    def validate_mapping_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', v):
            raise ValueError("Mapping name can only contain letters, numbers, spaces, hyphens, and underscores")
        return v.strip()

class ColumnMappingUpdate(BaseModel):
    mapping_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    source_columns: Optional[List[ColumnMappingRule]] = None
    target_columns: Optional[Dict[str, Any]] = None
    mapping_rules: Optional[Dict[str, Any]] = None
    erp_endpoint: Optional[str] = None
    is_active: Optional[bool] = None

class ColumnMappingResponse(BaseModel):
    id: str = Field(..., description="Mapping ID")
    mapping_name: str = Field(..., description="Mapping name")
    description: str = Field(..., description="Mapping description")
    source_columns: List[Dict[str, Any]] = Field(..., description="Source column definitions")
    target_columns: Dict[str, Any] = Field(..., description="Target column mapping")
    mapping_rules: Dict[str, Any] = Field(..., description="Additional mapping rules")
    erp_endpoint: str = Field(..., description="ERP endpoint")
    created_by: str = Field(..., description="Creator user ID")
    is_active: bool = Field(..., description="Mapping status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

# File Processing Models
class FileMetadata(BaseModel):
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    total_records: int = Field(..., description="Total records in file")
    total_columns: int = Field(..., description="Total columns in file")
    column_names: List[str] = Field(..., description="Column names")
    file_type: FileType = Field(..., description="File type")
    processing_time: float = Field(..., description="Processing time in seconds")
    data_quality_metrics: Dict[str, Any] = Field(default_factory=dict)

class ValidationError(BaseModel):
    record_index: int = Field(..., description="Record index")
    field_name: str = Field(..., description="Field name")
    error_type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    severity: ValidationSeverity = Field(..., description="Error severity")
    original_value: Optional[Any] = Field(None, description="Original value")
    suggested_fix: Optional[str] = Field(None, description="Suggested fix")

class DataValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Overall validation status")
    total_records: int = Field(..., description="Total records validated")
    valid_records: int = Field(..., description="Number of valid records")
    invalid_records: int = Field(..., description="Number of invalid records")
    errors: List[ValidationError] = Field(default_factory=list, description="Validation errors")
    warnings: List[ValidationError] = Field(default_factory=list, description="Validation warnings")

# Import Job Models
class ImportJobCreate(BaseModel):
    mapping_id: str = Field(..., description="Column mapping ID")
    filename: str = Field(..., description="Original filename")
    file_content: str = Field(..., description="Base64 encoded file content")
    options: Dict[str, Any] = Field(default_factory=dict, description="Import options")
    
    @validator('file_content')
    def validate_file_content(cls, v):
        if not v or len(v) < 100:  # Basic validation for base64 content
            raise ValueError("File content appears to be invalid")
        return v

class ImportJobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    processed_records: Optional[int] = None
    failed_records: Optional[int] = None
    error_log: Optional[List[Dict[str, Any]]] = None
    erp_response: Optional[Dict[str, Any]] = None
    completed_at: Optional[datetime] = None
    progress_message: Optional[str] = None

class ImportJobResponse(BaseModel):
    job_id: str = Field(..., description="Job ID")
    mapping_id: str = Field(..., description="Mapping ID")
    filename: str = Field(..., description="Filename")
    status: JobStatus = Field(..., description="Job status")
    total_records: int = Field(..., description="Total records")
    processed_records: int = Field(..., description="Processed records")
    failed_records: int = Field(..., description="Failed records")
    error_log: List[Dict[str, Any]] = Field(default_factory=list, description="Error log")
    erp_response: Dict[str, Any] = Field(default_factory=dict, description="ERP response")
    created_by: str = Field(..., description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    processing_time: Optional[float] = Field(None, description="Total processing time in seconds")
    progress_message: Optional[str] = Field(None, description="Current progress message")
    
    class Config:
        from_attributes = True

class ImportJobDetailResponse(ImportJobResponse):
    mapping_details: Optional[ColumnMappingResponse] = Field(None, description="Mapping details")
    file_metadata: Optional[FileMetadata] = Field(None, description="File metadata")
    validation_result: Optional[DataValidationResult] = Field(None, description="Validation results")

# ERP Integration Models
class ERPConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Connection name")
    base_url: str = Field(..., description="ERP base URL")
    api_key: str = Field(..., description="API key")
    endpoints: Dict[str, str] = Field(..., description="ERP endpoints")
    timeout: int = Field(30, ge=5, le=120, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=1, le=10, description="Maximum retry attempts")
    
    @validator('base_url')
    def validate_base_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Base URL must start with http:// or https://")
        return v.rstrip('/')

class ERPConnectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    base_url: Optional[str] = Field(None)
    api_key: Optional[str] = Field(None)
    endpoints: Optional[Dict[str, str]] = None
    timeout: Optional[int] = Field(None, ge=5, le=120)
    max_retries: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None

class ERPConnectionResponse(BaseModel):
    id: str = Field(..., description="Connection ID")
    name: str = Field(..., description="Connection name")
    base_url: str = Field(..., description="ERP base URL")
    endpoints: Dict[str, str] = Field(..., description="ERP endpoints")
    timeout: int = Field(..., description="Request timeout")
    max_retries: int = Field(..., description="Max retries")
    is_active: bool = Field(..., description="Connection status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True

class ERPRequest(BaseModel):
    endpoint: str = Field(..., description="ERP endpoint")
    data: List[Dict[str, Any]] = Field(..., description="Data to send")
    batch_size: int = Field(50, ge=1, le=1000, description="Batch size")

class ERPResponse(BaseModel):
    success: bool = Field(..., description="Request success status")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Error details")
    processing_time: float = Field(..., description="Processing time in seconds")
    timestamp: datetime = Field(..., description="Response timestamp")

# Monitoring and Metrics Models
class SystemMetrics(BaseModel):
    total_jobs: int = Field(..., description="Total jobs")
    completed_jobs: int = Field(..., description="Completed jobs")
    failed_jobs: int = Field(..., description="Failed jobs")
    processing_jobs: int = Field(..., description="Processing jobs")
    success_rate: float = Field(..., ge=0, le=100, description="Success rate percentage")
    avg_processing_time: float = Field(..., description="Average processing time in seconds")
    total_users: int = Field(..., description="Total users")
    active_mappings: int = Field(..., description="Active mappings")
    recent_errors: List[Dict[str, Any]] = Field(default_factory=list, description="Recent errors")
    system_health: Dict[str, Any] = Field(default_factory=dict, description="System health status")
    last_updated: datetime = Field(..., description="Last update timestamp")

class UserMetrics(BaseModel):
    user_id: str = Field(..., description="User ID")
    total_jobs: int = Field(..., description="User's total jobs")
    completed_jobs: int = Field(..., description="User's completed jobs")
    failed_jobs: int = Field(..., description="User's failed jobs")
    success_rate: float = Field(..., ge=0, le=100, description="User's success rate")
    avg_processing_time: float = Field(..., description="User's average processing time")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")

class AuditLog(BaseModel):
    id: str = Field(..., description="Log ID")
    user_id: str = Field(..., description="User ID")
    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Resource type")
    resource_id: Optional[str] = Field(None, description="Resource ID")
    details: Dict[str, Any] = Field(default_factory=dict, description="Action details")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    created_at: datetime = Field(..., description="Creation timestamp")

# WebSocket Models
class WebSocketMessageType(str, Enum):
    JOB_STATUS = "job_status"
    PROGRESS_UPDATE = "progress_update"
    ERROR = "error"
    SYSTEM_NOTIFICATION = "system_notification"
    HEARTBEAT = "heartbeat"

class WebSocketMessage(BaseModel):
    type: WebSocketMessageType = Field(..., description="Message type")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(..., description="Message timestamp")
    job_id: Optional[str] = Field(None, description="Related job ID")
    user_id: Optional[str] = Field(None, description="Target user ID")

class ProgressUpdate(BaseModel):
    job_id: str = Field(..., description="Job ID")
    status: JobStatus = Field(..., description="Current status")
    progress: float = Field(..., ge=0, le=100, description="Progress percentage")
    processed_records: int = Field(..., description="Processed records")
    total_records: int = Field(..., description="Total records")
    message: str = Field(..., description="Progress message")
    estimated_time_remaining: Optional[float] = Field(None, description="Estimated time remaining in seconds")

# Response Wrappers
class PaginatedResponse(BaseModel):
    data: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")

class SuccessResponse(BaseModel):
    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Response message")
    data: Optional[Any] = Field(None, description="Response data")

class ErrorResponse(BaseModel):
    success: bool = Field(False, description="Operation success status")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    code: Optional[str] = Field(None, description="Error code")

# Token Models
class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Expiration time in seconds")
    user: UserResponse = Field(..., description="User details")

class TokenData(BaseModel):
    user_id: Optional[str] = Field(None, description="User ID")
    email: Optional[str] = Field(None, description="User email")
    role: Optional[UserRole] = Field(None, description="User role")

# Health Check Models
class HealthCheck(BaseModel):
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Check timestamp")
    dependencies: Dict[str, Any] = Field(default_factory=dict, description="Dependency statuses")

class ServiceHealth(BaseModel):
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status")
    response_time: Optional[float] = Field(None, description="Response time in seconds")
    error: Optional[str] = Field(None, description="Error message")
    last_checked: datetime = Field(..., description="Last check timestamp")
