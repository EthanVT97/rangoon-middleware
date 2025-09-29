from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List

from app.auth import get_current_active_user
from app.database.supabase_client import supabase
from app.models import ColumnMappingCreate, ColumnMappingResponse
from app.utils.mapping_engine import mapping_engine

router = APIRouter()

@router.post("/create", response_model=Dict[str, Any])
async def create_column_mapping(
    mapping_data: ColumnMappingCreate,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Create new column mapping configuration"""
    try:
        user_id = current_user["id"]
        
        # Validate mapping configuration
        validation = mapping_engine.validate_mapping_config(mapping_data.dict())
        if not validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Mapping configuration validation failed",
                    "errors": validation["errors"],
                    "warnings": validation["warnings"]
                }
            )
        
        # Prepare mapping data for database
        db_mapping_data = {
            **mapping_data.dict(),
            "created_by": user_id,
            "is_active": True
        }
        
        # Create mapping in database
        mapping = await supabase.create_column_mapping(db_mapping_data)
        
        if mapping:
            return {
                "status": "success",
                "message": "Column mapping created successfully",
                "mapping": mapping,
                "warnings": validation["warnings"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create mapping"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating mapping: {str(e)}"
        )

@router.get("/", response_model=Dict[str, Any])
async def get_user_mappings(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get all column mappings for current user"""
    try:
        user_id = current_user["id"]
        mappings = await supabase.get_user_mappings(user_id)
        
        return {
            "status": "success",
            "mappings": mappings
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching mappings: {str(e)}"
        )

@router.get("/{mapping_id}", response_model=Dict[str, Any])
async def get_mapping_by_id(
    mapping_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get specific mapping by ID"""
    try:
        mapping = await supabase.get_mapping_by_id(mapping_id)
        
        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mapping not found"
            )
        
        # Check if user owns this mapping
        if mapping["created_by"] != current_user["id"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this mapping"
            )
        
        return {
            "status": "success",
            "mapping": mapping
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching mapping: {str(e)}"
        )

@router.put("/{mapping_id}", response_model=Dict[str, Any])
async def update_mapping(
    mapping_id: str,
    mapping_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Update column mapping"""
    try:
        # First, get the existing mapping
        existing_mapping = await supabase.get_mapping_by_id(mapping_id)
        
        if not existing_mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mapping not found"
            )
        
        # Check if user owns this mapping
        if existing_mapping["created_by"] != current_user["id"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this mapping"
            )
        
        # Validate updated mapping configuration
        updated_config = {**existing_mapping, **mapping_data}
        validation = mapping_engine.validate_mapping_config(updated_config)
        if not validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Mapping configuration validation failed",
                    "errors": validation["errors"],
                    "warnings": validation["warnings"]
                }
            )
        
        # Update mapping in database
        update_data = {
            **mapping_data,
            "updated_at": "now()"  # Supabase will handle this
        }
        
        # Note: We need to implement update method in supabase_client
        # For now, we'll return a placeholder response
        return {
            "status": "success",
            "message": "Mapping update endpoint - implementation pending",
            "mapping_id": mapping_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating mapping: {str(e)}"
        )

@router.delete("/{mapping_id}", response_model=Dict[str, Any])
async def delete_mapping(
    mapping_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Delete column mapping (soft delete)"""
    try:
        # Get the existing mapping
        existing_mapping = await supabase.get_mapping_by_id(mapping_id)
        
        if not existing_mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mapping not found"
            )
        
        # Check if user owns this mapping
        if existing_mapping["created_by"] != current_user["id"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this mapping"
            )
        
        # Soft delete by setting is_active to False
        # Note: We need to implement update method in supabase_client
        # For now, we'll return a placeholder response
        return {
            "status": "success",
            "message": "Mapping deletion endpoint - implementation pending",
            "mapping_id": mapping_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting mapping: {str(e)}"
        )

@router.get("/templates/{data_type}", response_model=Dict[str, Any])
async def get_mapping_template(data_type: str):
    """Get sample mapping template for different data types"""
    try:
        sample_mapping = mapping_engine.generate_sample_mapping(data_type)
        
        return {
            "status": "success",
            "data_type": data_type,
            "template": sample_mapping
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error generating template: {str(e)}"
        )
