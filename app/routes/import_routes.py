from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any
import uuid
import asyncio
from datetime import datetime

from app.auth import get_current_active_user
from app.database.supabase_client import supabase
from app.monitoring import live_monitor
from app.erp_integration import erp_integration
from app.utils.file_processor import process_excel_file, process_csv_file, validate_file_extension
from app.utils.mapping_engine import mapping_engine
from app.utils.validators import validate_business_rules

router = APIRouter()

@router.post("/excel", response_model=Dict[str, Any])
async def import_excel_file(
    background_tasks: BackgroundTasks,
    mapping_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Import Excel file with column mapping"""
    try:
        user_id = current_user["id"]
        
        # Validate file
        if not validate_file_extension(file.filename):
            raise HTTPException(
                status_code=400, 
                detail="Only Excel (.xlsx, .xls) and CSV (.csv) files are supported"
            )
        
        # Get mapping configuration
        mapping = await supabase.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=404, detail="Mapping configuration not found")
        
        # Check if user owns this mapping
        if mapping["created_by"] != user_id and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=403,
                detail="Access denied to this mapping"
            )
        
        # Create import job
        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "mapping_id": mapping_id,
            "filename": file.filename,
            "created_by": user_id,
            "status": "processing",
            "total_records": 0,
            "processed_records": 0,
            "failed_records": 0,
            "error_log": [],
            "erp_response": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        job = await supabase.create_import_job(job_data)
        
        if not job:
            raise HTTPException(
                status_code=500,
                detail="Failed to create import job"
            )
        
        # Start real-time monitoring
        await live_monitor.start_job_monitoring(job_id, user_id)
        
        # Process file in background
        background_tasks.add_task(
            process_import_file, 
            job_id, file, mapping, user_id
        )
        
        return {
            "status": "processing",
            "job_id": job_id,
            "message": "File import started successfully",
            "websocket_url": f"/api/monitoring/ws/{user_id}",
            "monitoring_url": f"/api/monitoring/jobs/{job_id}/status"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Import failed: {str(e)}"
        )

async def process_import_file(job_id: str, file: UploadFile, mapping: Dict[str, Any], user_id: str):
    """Background file processing"""
    try:
        # Read file content
        file_content = await file.read()
        
        # Process file based on type
        if file.filename.endswith('.csv'):
            df = process_csv_file(file_content)
        else:
            df = process_excel_file(file_content)
        
        # Update job with record count
        await supabase.update_job_status(job_id, {
            "total_records": len(df),
            "updated_at": datetime.now().isoformat()
        })
        
        await live_monitor.update_job_progress(job_id, {
            "total": len(df),
            "processed": 0,
            "failed": 0
        })
        
        # Apply mapping
        mapped_data = mapping_engine.apply_mapping(df, {
            "target_columns": mapping["target_columns"],
            "mapping_rules": mapping.get("mapping_rules", {})
        })
        
        # Validate data
        valid_data = []
        errors = []
        
        for i, row in enumerate(mapped_data):
            validation = validate_business_rules(row, mapping.get("mapping_rules", {}))
            if validation["is_valid"]:
                valid_data.append(validation["validated_data"])
            else:
                errors.append({
                    "row": i + 2,  # +2 for header row and 1-based indexing
                    "data": row,
                    "errors": validation["errors"]
                })
            
            # Update progress every 10 records
            if i % 10 == 0:
                await supabase.update_job_status(job_id, {
                    "processed_records": len(valid_data),
                    "failed_records": len(errors),
                    "error_log": errors,
                    "updated_at": datetime.now().isoformat()
                })
                
                await live_monitor.update_job_progress(job_id, {
                    "total": len(mapped_data),
                    "processed": len(valid_data),
                    "failed": len(errors)
                })
        
        # Send valid data to ERP
        erp_result = {"success": False, "message": "ERP integration not configured"}
        
        if valid_data and mapping.get("erp_endpoint"):
            try:
                erp_result = await erp_integration.send_to_erp(
                    valid_data, 
                    mapping["erp_endpoint"]
                )
            except Exception as e:
                erp_result = {
                    "success": False,
                    "error": f"ERP integration error: {str(e)}"
                }
        
        # Final job update
        final_status = "completed" if len(valid_data) > 0 else "failed"
        if len(errors) == len(mapped_data):  # All records failed
            final_status = "failed"
        
        await supabase.update_job_status(job_id, {
            "status": final_status,
            "processed_records": len(valid_data),
            "failed_records": len(errors),
            "error_log": errors,
            "erp_response": erp_result,
            "completed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
        # Complete monitoring
        await live_monitor.complete_job_monitoring(job_id, final_status)
        
    except Exception as e:
        # Update job with error
        error_message = str(e)
        await supabase.update_job_status(job_id, {
            "status": "failed",
            "error_log": [{"error": error_message}],
            "completed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
        await live_monitor.complete_job_monitoring(job_id, "failed")

@router.get("/jobs", response_model=Dict[str, Any])
async def get_import_jobs(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    limit: int = 50
):
    """Get user's import jobs"""
    try:
        user_id = current_user["id"]
        jobs = await supabase.get_user_jobs(user_id, limit=limit)
        
        return {
            "status": "success",
            "jobs": jobs,
            "total": len(jobs)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching jobs: {str(e)}"
        )

@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_import_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get specific import job"""
    try:
        job = await supabase.get_job_by_id(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Check if user owns this job
        if job["created_by"] != current_user["id"] and current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied to this job")
        
        return {
            "status": "success",
            "job": job
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching job: {str(e)}"
        )

@router.post("/jobs/{job_id}/retry", response_model=Dict[str, Any])
async def retry_import_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Retry a failed import job"""
    try:
        # This would re-process the original file with the same mapping
        # Implementation would fetch the original job and restart processing
        return {
            "status": "success",
            "message": "Job retry endpoint - implementation pending",
            "job_id": job_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrying job: {str(e)}"
)
