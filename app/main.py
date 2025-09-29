from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pandas as pd
import io
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any
import base64

# Import internal modules
from .database import get_db, ColumnMapping, ImportJob, ERPConnection
from .models import ColumnMappingCreate, ImportRequest, ERPConnectionCreate
from .erp_integration import ERPIntegration
from .utils.file_processor import process_excel_file, process_csv_file
from .utils.validators import validate_business_rules
from .utils.mapping_engine import MappingEngine

app = FastAPI(
    title="POS-ERP Middleware with Custom Mapping",
    description="Advanced Excel import with customizable column mapping",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
erp_integration = ERPIntegration()
mapping_engine = MappingEngine()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard"""
    mappings = db.query(ColumnMapping).filter(ColumnMapping.is_active == True).all()
    recent_jobs = db.query(ImportJob).order_by(ImportJob.created_at.desc()).limit(10).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "mappings": mappings,
        "recent_jobs": recent_jobs
    })

@app.get("/mapping/create", response_class=HTMLResponse)
async def create_mapping_page(request: Request):
    """Column mapping configuration page"""
    return templates.TemplateResponse("mapping_config.html", {"request": request})

@app.post("/api/mappings")
async def create_mapping(mapping: ColumnMappingCreate, db: Session = Depends(get_db)):
    """Create new column mapping configuration"""
    
    # Validate mapping configuration
    validation = mapping_engine.validate_mapping_config(mapping.dict())
    if not validation["is_valid"]:
        raise HTTPException(400, detail={"errors": validation["errors"]})
    
    # Check if mapping name already exists
    existing = db.query(ColumnMapping).filter(ColumnMapping.mapping_name == mapping.mapping_name).first()
    if existing:
        raise HTTPException(400, detail="Mapping name already exists")
    
    # Create new mapping
    db_mapping = ColumnMapping(
        mapping_name=mapping.mapping_name,
        source_columns=mapping.source_columns,
        target_columns=mapping.target_columns,
        mapping_rules=mapping.mapping_rules or {}
    )
    
    db.add(db_mapping)
    db.commit()
    db.refresh(db_mapping)
    
    return {"status": "success", "mapping_id": db_mapping.id}

@app.get("/api/mappings")
async def get_mappings(db: Session = Depends(get_db)):
    """Get all column mappings"""
    mappings = db.query(ColumnMapping).filter(ColumnMapping.is_active == True).all()
    return {"mappings": [
        {
            "id": m.id,
            "mapping_name": m.mapping_name,
            "source_columns": m.source_columns,
            "target_columns": m.target_columns,
            "created_at": m.created_at.isoformat()
        } for m in mappings
    ]}

@app.post("/api/import")
async def import_excel_file(
    mapping_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import Excel file using specified mapping"""
    
    # Validate file
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(400, detail="Only Excel and CSV files are supported")
    
    # Get mapping configuration
    mapping = db.query(ColumnMapping).filter(ColumnMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(404, detail="Mapping configuration not found")
    
    # Create import job
    job_id = str(uuid.uuid4())
    job = ImportJob(
        job_id=job_id,
        mapping_id=mapping_id,
        filename=file.filename,
        status="pending"
    )
    db.add(job)
    db.commit()
    
    # Process file asynchronously
    await process_import_job(job_id, file, mapping, db)
    
    return {
        "status": "processing",
        "job_id": job_id,
        "message": "File import started"
    }

async def process_import_job(job_id: str, file: UploadFile, mapping: ColumnMapping, db: Session):
    """Background job to process import"""
    try:
        # Update job status
        job = db.query(ImportJob).filter(ImportJob.job_id == job_id).first()
        job.status = "processing"
        db.commit()
        
        # Read and process file
        contents = await file.read()
        
        if file.filename.endswith('.csv'):
            df = process_csv_file(contents)
        else:
            df = process_excel_file(contents)
        
        job.total_records = len(df)
        db.commit()
        
        # Apply mapping
        mapped_data = mapping_engine.apply_mapping(df, {
            "target_columns": mapping.target_columns,
            "mapping_rules": mapping.mapping_rules
        })
        
        # Validate data
        valid_data = []
        errors = []
        
        for i, row in enumerate(mapped_data):
            validation = validate_business_rules(row, mapping.mapping_rules)
            if validation["is_valid"]:
                valid_data.append(row)
            else:
                errors.append({
                    "row": i + 2,
                    "data": row,
                    "errors": validation["errors"]
                })
        
        # Send to ERP
        if valid_data:
            erp_endpoint = mapping.mapping_rules.get("erp_endpoint", "customers")
            erp_result = await erp_integration.send_to_erp(valid_data, erp_endpoint, mapping.id)
            
            job.erp_response = erp_result
            job.processed_records = len(valid_data)
        
        job.failed_records = len(errors)
        job.error_log = errors
        job.status = "completed" if len(errors) < len(mapped_data) else "failed"
        job.completed_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        # Update job with error
        job = db.query(ImportJob).filter(ImportJob.job_id == job_id).first()
        job.status = "failed"
        job.error_log = [{"error": str(e)}]
        job.completed_at = datetime.utcnow()
        db.commit()

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get import job status"""
    job = db.query(ImportJob).filter(ImportJob.job_id == job_id).first()
    if not job:
        raise HTTPException(404, detail="Job not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "filename": job.filename,
        "total_records": job.total_records,
        "processed_records": job.processed_records,
        "failed_records": job.failed_records,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_log": job.error_log
    }

@app.post("/api/erp/connection")
async def configure_erp_connection(connection: ERPConnectionCreate, db: Session = Depends(get_db)):
    """Configure ERP connection"""
    
    # Test connection first
    test_result = await erp_integration.test_connection()
    if not test_result["success"]:
        raise HTTPException(400, detail=f"ERP connection test failed: {test_result['error']}")
    
    # Deactivate other connections
    db.query(ERPConnection).update({"is_active": False})
    
    # Create new connection
    erp_conn = ERPConnection(
        name=connection.name,
        base_url=connection.base_url,
        api_key=connection.api_key,
        endpoints=connection.endpoints,
        is_active=True
    )
    
    db.add(erp_conn)
    db.commit()
    
    return {"status": "success", "message": "ERP connection configured successfully"}

@app.get("/api/erp/test")
async def test_erp_connection():
    """Test ERP connection"""
    result = await erp_integration.test_connection()
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
