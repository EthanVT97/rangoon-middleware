from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any
from ..auth import auth_handler, get_current_active_user
from ..database.supabase_client import supabase

router = APIRouter()

class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    company: str = ""

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register(user_data: UserRegister):
    """Register new user"""
    try:
        # Create user in Supabase Auth
        result = await supabase.create_user(
            user_data.email,
            user_data.password,
            {
                "full_name": user_data.full_name,
                "company": user_data.company
            }
        )
        
        if result.user:
            # Create access token
            access_token = auth_handler.create_access_token(
                data={"sub": result.user.id}
            )
            
            return {
                "status": "success",
                "user_id": result.user.id,
                "access_token": access_token,
                "token_type": "bearer"
            }
        else:
            raise HTTPException(400, "User registration failed")
            
    except Exception as e:
        raise HTTPException(400, str(e))

@router.post("/login")
async def login(login_data: UserLogin):
    """User login"""
    try:
        # Authenticate with Supabase
        result = supabase.client.auth.sign_in_with_password({
            "email": login_data.email,
            "password": login_data.password
        })
        
        if result.user:
            # Create access token
            access_token = auth_handler.create_access_token(
                data={"sub": result.user.id}
            )
            
            return {
                "status": "success",
                "user_id": result.user.id,
                "access_token": access_token,
                "token_type": "bearer"
            }
        else:
            raise HTTPException(401, "Invalid credentials")
            
    except Exception as e:
        raise HTTPException(401, str(e))

@router.get("/me")
async def get_current_user(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get current user info"""
    return {
        "status": "success",
        "user": current_user
      }
