from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class ColumnMappingCreate(BaseModel):
    mapping_name: str
    source_columns: List[Dict[str, Any]]
    target_columns: List[Dict[str, Any]]
    mapping_rules: Optional[Dict[str, Any]] = {}

class ColumnMappingResponse(BaseModel):
    id: int
    mapping_name: str
    source_columns: List[Dict[str, Any]]
    target_columns: List[Dict[str, Any]]
    mapping_rules: Dict[str, Any]
    is_active: bool
    created_at: datetime

class ImportRequest(BaseModel):
    mapping_id: int
    file_content: str  # Base64 encoded file
    filename: str

class ERPConnectionCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    endpoints: Dict[str, str]

class ImportJobResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    mapping_name: str
    total_records: int
    processed_records: int
    failed_records: int
    created_at: datetime
    completed_at: Optional[datetime]

class DataValidationResult(BaseModel):
    is_valid: bool
    errors: List[str]
    validated_data: Dict[str, Any]
