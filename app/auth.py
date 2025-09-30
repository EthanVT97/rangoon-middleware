import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from enum import Enum

from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from decouple import config
import redis.asyncio as redis

from .database.supabase_client import supabase
from .models import UserRole, Token, TokenData

# Configure logging
logger = logging.getLogger(__name__)

# Security configuration
security = HTTPBearer(auto_error=False)

class TokenType(Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"

class AuthError(Enum):
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    RATE_LIMITED = "rate_limited"

class RateLimiter:
    """Rate limiting for authentication attempts"""
    
    def __init__(self):
        self.redis_client = None
        self.max_attempts = 5
        self.window_minutes = 15
        self.lockout_minutes = 30
    
    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=config("REDIS_HOST", default="localhost"),
                port=config("REDIS_PORT", default=6379),
                password=config("REDIS_PASSWORD", default=""),
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connection established for rate limiting")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory rate limiting")
            self.redis_client = None
            self.memory_store = {}
    
    async def is_rate_limited(self, identifier: str, action: str) -> bool:
        """Check if request is rate limited"""
        key = f"rate_limit:{action}:{identifier}"
        current_time = int(time.time())
        window_seconds = self.window_minutes * 60
        
        try:
            if self.redis_client:
                # Redis implementation
                pipeline = self.redis_client.pipeline()
                pipeline.zremrangebyscore(key, 0, current_time - window_seconds)
                pipeline.zadd(key, {str(current_time): current_time})
                pipeline.zcard(key)
                pipeline.expire(key, window_seconds)
                results = await pipeline.execute()
                attempts = results[2]
            else:
                # In-memory implementation
                if key not in self.memory_store:
                    self.memory_store[key] = []
                
                # Remove old attempts
                self.memory_store[key] = [
                    ts for ts in self.memory_store[key] 
                    if ts > current_time - window_seconds
                ]
                
                # Add current attempt
                self.memory_store[key].append(current_time)
                attempts = len(self.memory_store[key])
            
            return attempts >= self.max_attempts
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False
    
    async def get_remaining_attempts(self, identifier: str, action: str) -> int:
        """Get remaining attempts before lockout"""
        key = f"rate_limit:{action}:{identifier}"
        current_time = int(time.time())
        window_seconds = self.window_minutes * 60
        
        try:
            if self.redis_client:
                await self.redis_client.zremrangebyscore(key, 0, current_time - window_seconds)
                attempts = await self.redis_client.zcard(key)
            else:
                if key not in self.memory_store:
                    attempts = 0
                else:
                    self.memory_store[key] = [
                        ts for ts in self.memory_store[key] 
                        if ts > current_time - window_seconds
                    ]
                    attempts = len(self.memory_store[key])
            
            return max(0, self.max_attempts - attempts)
            
        except Exception as e:
            logger.error(f"Failed to get remaining attempts: {e}")
            return self.max_attempts
    
    async def lock_account(self, identifier: str, minutes: int = 30):
        """Lock account for specified minutes"""
        key = f"account_lock:{identifier}"
        lock_time = int(time.time()) + (minutes * 60)
        
        try:
            if self.redis_client:
                await self.redis_client.setex(key, minutes * 60, "locked")
            else:
                self.memory_store[key] = lock_time
        except Exception as e:
            logger.error(f"Failed to lock account: {e}")
    
    async def is_account_locked(self, identifier: str) -> bool:
        """Check if account is locked"""
        key = f"account_lock:{identifier}"
        
        try:
            if self.redis_client:
                return await self.redis_client.exists(key) > 0
            else:
                lock_time = self.memory_store.get(key, 0)
                return lock_time > time.time()
        except Exception as e:
            logger.error(f"Failed to check account lock: {e}")
            return False

class TokenBlacklist:
    """Token blacklist management"""
    
    def __init__(self):
        self.redis_client = None
    
    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=config("REDIS_HOST", default="localhost"),
                port=config("REDIS_PORT", default=6379),
                password=config("REDIS_PASSWORD", default=""),
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connection established for token blacklist")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory blacklist")
            self.redis_client = None
            self.memory_blacklist = set()
    
    async def blacklist_token(self, token: str, expires_in: int):
        """Add token to blacklist"""
        try:
            if self.redis_client:
                await self.redis_client.setex(f"blacklist:{token}", expires_in, "1")
            else:
                self.memory_blacklist.add(token)
                # Note: In-memory blacklist doesn't expire automatically
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
    
    async def is_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        try:
            if self.redis_client:
                return await self.redis_client.exists(f"blacklist:{token}") > 0
            else:
                return token in self.memory_blacklist
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            return False

class AuthHandler:
    """Enhanced authentication handler with security features"""
    
    def __init__(self):
        self.secret_key = config("SECRET_KEY")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = config("ACCESS_TOKEN_EXPIRE_MINUTES", default=60, cast=int)
        self.refresh_token_expire_days = config("REFRESH_TOKEN_EXPIRE_DAYS", default=7, cast=int)
        self.password_reset_expire_minutes = config("PASSWORD_RESET_EXPIRE_MINUTES", default=30, cast=int)
        
        # Password hashing
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Rate limiting and blacklist
        self.rate_limiter = RateLimiter()
        self.token_blacklist = TokenBlacklist()
        
        # Initialize components
        asyncio.create_task(self._initialize_components())
    
    async def _initialize_components(self):
        """Initialize rate limiter and blacklist"""
        await self.rate_limiter.init_redis()
        await self.token_blacklist.init_redis()
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "type": TokenType.ACCESS.value,
            "iat": datetime.now(timezone.utc),
            "jti": self._generate_token_id()
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "type": TokenType.REFRESH.value,
            "iat": datetime.now(timezone.utc),
            "jti": self._generate_token_id()
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_password_reset_token(self, data: dict) -> str:
        """Create password reset token"""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.password_reset_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "type": TokenType.RESET.value,
            "iat": datetime.now(timezone.utc),
            "jti": self._generate_token_id()
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def _generate_token_id(self) -> str:
        """Generate unique token ID"""
        import uuid
        return str(uuid.uuid4())
    
    def verify_token(self, token: str, expected_type: TokenType = None) -> Optional[Dict[str, Any]]:
        """Verify JWT token with enhanced security"""
        try:
            # Check if token is blacklisted
            if asyncio.run(self.token_blacklist.is_blacklisted(token)):
                logger.warning("Attempt to use blacklisted token")
                return None
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Verify token type if expected
            if expected_type and payload.get("type") != expected_type.value:
                logger.warning(f"Token type mismatch. Expected: {expected_type.value}, Got: {payload.get('type')}")
                return None
            
            # Verify token has required fields
            if not all(key in payload for key in ["sub", "exp", "type", "jti"]):
                logger.warning("Token missing required fields")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}")
            return None
    
    async def authenticate_user(self, email: str, password: str, request: Request = None) -> Dict[str, Any]:
        """Authenticate user with enhanced security features"""
        client_ip = request.client.host if request else "unknown"
        
        # Check rate limiting
        if await self.rate_limiter.is_rate_limited(client_ip, "login"):
            logger.warning(f"Rate limited login attempt from IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later."
            )
        
        # Check if account is locked
        if await self.rate_limiter.is_account_locked(email):
            logger.warning(f"Login attempt for locked account: {email}")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked due to too many failed attempts."
            )
        
        try:
            # Use Supabase auth for authentication
            auth_response = supabase.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                # Reset rate limiting on successful login
                logger.info(f"Successful login for user: {email}")
                
                # Get user profile
                user = await supabase.get_user_by_id(auth_response.user.id)
                if user:
                    return user
            
            # Increment failed attempt counter
            remaining_attempts = await self.rate_limiter.get_remaining_attempts(client_ip, "login")
            
            if remaining_attempts <= 1:
                # Lock account on last attempt
                await self.rate_limiter.lock_account(email)
                logger.warning(f"Account locked due to failed login attempts: {email}")
                
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account locked due to too many failed attempts. Please try again later."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid credentials. {remaining_attempts - 1} attempts remaining."
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error for {email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """Get current user from token with enhanced validation"""
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = credentials.credentials
        payload = self.verify_token(token, TokenType.ACCESS)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user from database
        user = await supabase.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated"
            )
        
        logger.debug(f"Authenticated user: {user_id}")
        return user
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[Token]:
        """Refresh access token using refresh token"""
        payload = self.verify_token(refresh_token, TokenType.REFRESH)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Verify user still exists and is active
        user = await supabase.get_user_by_id(user_id)
        if not user or not user.get("is_active", True):
            return None
        
        # Create new access token
        access_token = self.create_access_token({"sub": user_id})
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60,
            user=user
        )
    
    async def logout(self, token: str, expires_in: int):
        """Logout user by blacklisting token"""
        await self.token_blacklist.blacklist_token(token, expires_in)
        logger.info("User logged out successfully")
    
    async def initiate_password_reset(self, email: str) -> bool:
        """Initiate password reset process"""
        try:
            user = await supabase.get_user_by_email(email)
            if not user:
                # Don't reveal whether email exists
                logger.info(f"Password reset requested for non-existent email: {email}")
                return True
            
            # Create reset token
            reset_token = self.create_password_reset_token({"sub": user["id"]})
            
            # TODO: Send email with reset token
            # This would integrate with your email service
            logger.info(f"Password reset token created for user: {email}")
            
            return True
            
        except Exception as e:
            logger.error(f"Password reset initiation failed for {email}: {e}")
            return False
    
    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using reset token"""
        payload = self.verify_token(token, TokenType.RESET)
        if not payload:
            return False
        
        user_id = payload.get("sub")
        if not user_id:
            return False
        
        try:
            # Update password in Supabase
            # Note: This requires the Supabase service role key
            auth_response = supabase.client.auth.admin.update_user_by_id(
                user_id,
                {"password": new_password}
            )
            
            if auth_response.user:
                # Blacklist the used reset token
                expires_in = payload.get("exp", 0) - int(datetime.now(timezone.utc).timestamp())
                if expires_in > 0:
                    await self.token_blacklist.blacklist_token(token, expires_in)
                
                logger.info(f"Password reset successful for user: {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Password reset failed for user {user_id}: {e}")
            return False
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return self.pwd_context.hash(password)
    
    async def get_token_data(self, token: str) -> Optional[TokenData]:
        """Extract token data without full validation"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            return TokenData(
                user_id=payload.get("sub"),
                email=payload.get("email"),
                role=UserRole(payload.get("role")) if payload.get("role") else None
            )
        except Exception:
            return None

# Global auth handler
auth_handler = AuthHandler()

# Dependency for protected routes
async def get_current_active_user(current_user: Dict[str, Any] = Depends(auth_handler.get_current_user)):
    """Dependency for active users"""
    return current_user

async def get_current_admin_user(current_user: Dict[str, Any] = Depends(auth_handler.get_current_user)):
    """Dependency for admin-only routes"""
    if current_user.get("role") != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def get_current_manager_user(current_user: Dict[str, Any] = Depends(auth_handler.get_current_user)):
    """Dependency for manager and admin routes"""
    if current_user.get("role") not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access required"
        )
    return current_user

async def optional_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict[str, Any]]:
    """Optional authentication dependency"""
    if not credentials:
        return None
    
    try:
        return await auth_handler.get_current_user(credentials)
    except HTTPException:
        return None

# Security middleware
async def security_middleware(request: Request, call_next):
    """Security middleware for additional protection"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Log slow requests
        process_time = time.time() - start_time
        if process_time > 5.0:  # Log requests slower than 5 seconds
            logger.warning(f"Slow request: {request.method} {request.url.path} - {process_time:.3f}s")
        
        return response
        
    except Exception as e:
        logger.error(f"Request processing error: {e}")
        raise
