from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
import uuid
from datetime import datetime
from typing import Dict, Any
from ..auth import get_current_active_user
from ..database.supabase_client import supabase
from ..monitoring import live_monitor
from ..utils.file_processor import process_excel_file, process_csv_file
from ..utils.mapping_engine import MappingEngine
from ..utils.validators import validate_business_rules

router = APIRouter()
mapping_engine = MappingEngine()

@router.post("/excel")
async def import_excel_file(
    mapping_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Import Excel file with column mapping"""
    
    # Validate file
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(400, "Only Excel and CSV files are supported")
    
    try:
        user_id = current_user["id"]
        
        # Get mapping configuration
        mappings = await supabase.get_user_mappings(user_id)
        mapping = next((m for m in mappings if m["id"] == mapping_id), None)
        
        if not mapping:
            raise HTTPException(404, "Mapping configuration not found")
        
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
            "created_at": datetime.now().isoformat()
        }
        
        job = await supabase.create_import_job(job_data)
        
        # Start real-time monitoring
        await live_monitor.start_job_monitoring(job_id, user_id)
        
        # Process file asynchronously
        asyncio.create_task(
            process_import_file(job_id, file, mapping, user_id)
        )
        
        return {
            "status": "processing",
            "job_id": job_id,
            "message": "File import started",
            "websocket_url": f"/monitoring/ws/{user_id}"
        }
        
    except Exception as e:
        raise HTTPException(500, f"Import failed: {str(e)}")

async def process_import_file(job_id: str, file: UploadFile, mapping: Dict[str, Any], user_id: str):
    """Background file processing"""
    try:
        # Read file
        contents = await file.read()
        
        if file.filename.endswith('.csv'):
            df = process_csv_file(contents)
        else:
            df = process_excel_file(contents)
        
        # Update job with record count
        await supabase.update_job_status(job_id, {
            "total_records": len(df),
            "updated_at": datetime.now().isoformat()
        })
        
        # Apply mapping
        mapped_data = mapping_engine.apply_mapping(df, {
            "target_columns": mapping["target_columns"],
            "mapping_rules": mapping["mapping_rules"]
        })
        
        # Validate data
        valid_data = []
        errors = []
        
        for i, row in enumerate(mapped_data):
            validation = validate_business_rules(row, mapping["mapping_rules"])
            if validation["is_valid"]:
                valid_data.append(row)
            else:
                errors.append({
                    "row": i + 2,
                    "data": row,
                    "errors": validation["errors"]
                })
            
            # Update progress every 10 records
            if i % 10 == 0:
                await supabase.update_job_status(job_id, {
                    "processed_records": len(valid_data),
                    "failed_records": len(errors),
                    "updated_at": datetime.now().isoformat()
                })
        
        # Send to ERP
        erp_result = {"success": True, "message": "Mock ERP integration"}
        # In real implementation: await erp_integration.send_to_erp(valid_data, mapping)
        
        # Final job update
        final_status = "completed" if len(errors) < len(mapped_data) else "failed"
        
        await supabase.update_job_status(job_id, {
            "status": final_status,
            "processed_records": len(valid_data),
            "failed_records": len(errors),
            "error_log": errors,
            "erp_response": erp_result,
            "completed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        # Update job with error
        await supabase.update_job_status(job_id, {
            "status": "failed",
            "error_log": [{"error": str(e)}],
            "completed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
