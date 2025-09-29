from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Dict, Any

from app.auth import auth_handler, get_current_active_user
from app.database.supabase_client import supabase
from app.models import UserRegister, UserLogin, UserResponse

router = APIRouter()

@router.post("/register", response_model=Dict[str, Any])
async def register(user_data: UserRegister):
    """Register new user"""
    try:
        # Check if user already exists
        existing_user = await supabase.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Create user
        user_dict = user_data.dict()
        user = await supabase.create_user(user_dict)
        
        if user:
            # Create access token
            access_token = auth_handler.create_access_token(
                data={"sub": user["id"]}
            )
            
            return {
                "status": "success",
                "message": "User registered successfully",
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user["full_name"],
                    "company": user.get("company", ""),
                    "role": user.get("role", "user")
                },
                "access_token": access_token,
                "token_type": "bearer"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User registration failed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login", response_model=Dict[str, Any])
async def login(login_data: UserLogin):
    """User login"""
    try:
        # Authenticate user
        user = await auth_handler.authenticate_user(login_data.email, login_data.password)
        
        if user:
            # Create access token
            access_token = auth_handler.create_access_token(
                data={"sub": user["id"]}
            )
            
            return {
                "status": "success",
                "message": "Login successful",
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user["full_name"],
                    "company": user.get("company", ""),
                    "role": user.get("role", "user")
                },
                "access_token": access_token,
                "token_type": "bearer"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@router.get("/me", response_model=Dict[str, Any])
async def get_current_user(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get current user info"""
    return {
        "status": "success",
        "user": current_user
    }

@router.post("/refresh")
async def refresh_token(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Refresh access token"""
    access_token = auth_handler.create_access_token(
        data={"sub": current_user["id"]}
    )
    
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """User logout"""
    # In a stateless JWT system, we can't invalidate the token
    # But we can record the logout action for auditing
    try:
        # Record logout in monitoring logs
        await supabase.create_monitoring_log({
            "user_id": current_user["id"],
            "event_type": "user_logout",
            "metadata": {
                "timestamp": "now",
                "user_agent": "web"  # In real implementation, get from request
            }
        })
        
        return {
            "status": "success",
            "message": "Logout successful"
        }
    except Exception as e:
        # Logout should not fail even if monitoring fails
        return {
            "status": "success", 
            "message": "Logout completed"
        }
