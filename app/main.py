from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import time
import logging
from contextlib import asynccontextmanager
from decouple import config
import asyncio
from datetime import datetime

from .routes import api_router
from .database.supabase_client import supabase
from .websocket_manager import websocket_manager
from .erp_integration import erp_integration
from .auth import auth_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_ORIGINS = config("ALLOWED_ORIGINS", default="http://localhost:3000,http://localhost:8000").split(",")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")
API_PREFIX = config("API_PREFIX", default="/api")

# ERPNext Test Configuration
ERPNEXT_TEST_URL = config("ERPNEXT_TEST_URL", default="https://rangoontesting.s.erpnext.com")
ERPNEXT_TEST_USERNAME = config("ERPNEXT_TEST_USERNAME", default="rangoon")
ERPNEXT_TEST_PASSWORD = config("ERPNEXT_TEST_PASSWORD", default="rangoon@123")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced lifespan context manager for startup/shutdown events"""
    # Startup
    startup_time = time.time()
    logger.info("🚀 Rangoon Middleware starting up...")
    
    try:
        # Test database connection with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Test Supabase connection with actual query
                result = supabase.client.from_('profiles').select('id', count='exact').limit(1).execute()
                logger.info("✅ Supabase connection established")
                break
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ Database connection failed after {max_retries} attempts: {e}")
                    raise
                else:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"⚠️ Database connection attempt {attempt + 1} failed, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
        
        # Initialize ERPNext integration with test credentials
        await initialize_erpnext_integration()
        
        # Initialize background tasks
        asyncio.create_task(background_health_check())
        
        startup_duration = time.time() - startup_time
        logger.info(f"✅ Startup completed in {startup_duration:.2f}s")
        
    except Exception as e:
        logger.critical(f"💥 Startup failed: {e}")
        raise
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("🛑 Rangoon Middleware shutting down...")
    try:
        # Close WebSocket connections
        await websocket_manager.disconnect_all()
        logger.info("✅ WebSocket connections closed")
        
        # Close background tasks
        logger.info("✅ Background tasks stopped")
        
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

async def initialize_erpnext_integration():
    """Initialize ERPNext integration with test credentials"""
    try:
        # Check if ERPNext configuration exists in environment
        erpnext_api_key = config("ERPNEXT_API_KEY", default=None)
        erpnext_base_url = config("ERPNEXT_BASE_URL", default=ERPNEXT_TEST_URL)
        erpnext_username = config("ERPNEXT_USERNAME", default=ERPNEXT_TEST_USERNAME)
        erpnext_password = config("ERPNEXT_PASSWORD", default=ERPNEXT_TEST_PASSWORD)
        
        if erpnext_api_key and erpnext_base_url:
            # Initialize with environment variables
            await erp_integration.initialize_erpnext(
                base_url=erpnext_base_url,
                api_key=erpnext_api_key,
                username=erpnext_username,
                password=erpnext_password
            )
            
            # Test connection
            erp_status = await erp_integration.test_connection()
            if erp_status["success"]:
                logger.info("✅ ERPNext connection established with environment config")
            else:
                logger.warning(f"⚠️ ERPNext connection failed: {erp_status.get('error', 'Unknown error')}")
        else:
            logger.info("ℹ️ ERPNext configuration not found in environment. Will use manual setup.")
            
    except Exception as e:
        logger.error(f"❌ ERPNext initialization failed: {e}")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Rangoon Middleware",
    description="Advanced Excel Import with Custom Mapping & ERPNext Integration",
    version="2.0.0",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan
)

# Security middleware
if not DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=ALLOWED_HOSTS
    )

# CORS middleware with enhanced configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization", 
        "Content-Type", 
        "X-Requested-With",
        "X-Request-ID",
        "Accept"
    ],
    expose_headers=["X-Request-ID", "Content-Disposition"],
    max_age=600,  # 10 minutes
)

# Compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include API routes
app.include_router(api_router, prefix=API_PREFIX)

# Global exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Global HTTP exception handler"""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Global validation error handler"""
    logger.warning(f"Validation error: {exc.errors()} - Path: {request.url.path}")
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": "Validation failed",
            "details": exc.errors(),
            "status_code": 422,
            "path": request.url.path
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {str(exc)} - Path: {request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500,
            "path": request.url.path
        }
    )

# Middleware for request logging and processing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware for logging requests and adding request ID"""
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    # Log request
    logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log response
        logger.info(f"Response {request_id}: {response.status_code} - {process_time:.3f}s")
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Error {request_id}: {str(e)} - {process_time:.3f}s")
        raise

# Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "version": "2.0.0",
        "debug": DEBUG
    })

@app.get("/mapping/create", response_class=HTMLResponse)
async def create_mapping_page(request: Request):
    """Column mapping configuration page"""
    return templates.TemplateResponse("mapping_config.html", {
        "request": request,
        "api_prefix": API_PREFIX
    })

@app.get("/upload/status", response_class=HTMLResponse)
async def upload_status_page(request: Request):
    """Upload status monitoring page"""
    return templates.TemplateResponse("upload_status.html", {
        "request": request,
        "api_prefix": API_PREFIX
    })

@app.get("/erpnext/setup", response_class=HTMLResponse)
async def erpnext_setup_page(request: Request):
    """ERPNext connection setup page"""
    return templates.TemplateResponse("erpnext_setup.html", {
        "request": request,
        "api_prefix": API_PREFIX,
        "test_url": ERPNEXT_TEST_URL,
        "test_username": ERPNEXT_TEST_USERNAME
    })

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Comprehensive health check endpoint"""
    health_status = {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }
    
    # Database health check
    try:
        db_result = supabase.client.from_('profiles').select('count', count='exact').limit(1).execute()
        health_status["services"]["database"] = {
            "status": "healthy",
            "response_time": "ok"
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # ERPNext health check
    try:
        erp_status = await erp_integration.test_connection()
        health_status["services"]["erpnext"] = erp_status
        if not erp_status["success"]:
            health_status["status"] = "degraded"
            health_status["services"]["erpnext"]["status"] = "unhealthy"
        else:
            health_status["services"]["erpnext"]["status"] = "healthy"
    except Exception as e:
        health_status["services"]["erpnext"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # System info
    health_status["system"] = {
        "debug": DEBUG,
        "python_version": os.environ.get("PYTHON_VERSION", "unknown"),
        "environment": "development" if DEBUG else "production"
    }
    
    return health_status

@app.get(f"{API_PREFIX}/status", tags=["Monitoring"])
async def system_status():
    """Detailed system status endpoint"""
    status = {
        "application": {
            "name": "Rangoon Middleware",
            "version": "2.0.0",
            "environment": "development" if DEBUG else "production",
            "debug": DEBUG
        },
        "database": {
            "connected": supabase.client is not None,
            "provider": "Supabase"
        },
        "erpnext_integration": await erp_integration.get_system_status(),
        "websockets": {
            "active_connections": len(websocket_manager.active_connections),
            "manager_status": "running"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return status

@app.post(f"{API_PREFIX}/erpnext/test-connection", tags=["ERPNext"])
async def test_erpnext_connection(request: Request):
    """Test ERPNext connection with provided credentials"""
    try:
        data = await request.json()
        
        # Validate required fields
        if not data.get("base_url") or not data.get("api_key"):
            raise HTTPException(
                status_code=400,
                detail="base_url and api_key are required"
            )
        
        # Test connection using auth handler
        connection_test = await auth_handler.test_erpnext_connection({
            "base_url": data["base_url"],
            "api_key": data["api_key"],
            "username": data.get("username"),
            "password": data.get("password")
        })
        
        return {
            "success": connection_test["success"],
            "message": "Connection test completed",
            "details": connection_test
        }
        
    except Exception as e:
        logger.error(f"ERPNext connection test failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Connection test failed: {str(e)}"
        )

@app.post(f"{API_PREFIX}/erpnext/initialize", tags=["ERPNext"])
async def initialize_erpnext(request: Request):
    """Initialize ERPNext integration with provided credentials"""
    try:
        data = await request.json()
        
        # Validate required fields
        if not data.get("base_url") or not data.get("api_key"):
            raise HTTPException(
                status_code=400,
                detail="base_url and api_key are required"
            )
        
        # Initialize ERPNext integration
        success = await erp_integration.initialize_erpnext(
            base_url=data["base_url"],
            api_key=data["api_key"],
            username=data.get("username"),
            password=data.get("password")
        )
        
        if success:
            # Test the connection
            connection_status = await erp_integration.test_connection()
            
            return {
                "success": True,
                "message": "ERPNext integration initialized successfully",
                "connection_status": connection_status
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize ERPNext integration"
            )
        
    except Exception as e:
        logger.error(f"ERPNext initialization failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Initialization failed: {str(e)}"
        )

@app.get(f"{API_PREFIX}/erpnext/endpoints", tags=["ERPNext"])
async def get_erpnext_endpoints():
    """Get available ERPNext endpoints and their configurations"""
    from .models import ERPNextEndpoint
    
    endpoints_info = {}
    
    for endpoint in ERPNextEndpoint:
        endpoints_info[endpoint.value] = {
            "description": f"ERPNext {endpoint.value} endpoint",
            "supported_operations": ["CREATE", "GET"],
            "required_fields": get_required_fields_for_endpoint(endpoint)
        }
    
    return {
        "success": True,
        "endpoints": endpoints_info,
        "total_endpoints": len(endpoints_info)
    }

def get_required_fields_for_endpoint(endpoint):
    """Get required fields for each ERPNext endpoint"""
    required_fields = {
        "Item": ["item_code", "item_name"],
        "Customer": ["customer_name", "customer_group"],
        "Sales Order": ["customer", "items"],
        "Sales Invoice": ["customer", "items"],
        "Payment Entry": ["payment_type", "party", "paid_amount"],
        "Bin": []  # Stock information - usually read-only
    }
    
    return required_fields.get(endpoint.value, [])

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Favicon endpoint"""
    from fastapi.responses import FileResponse
    return FileResponse("static/favicon.ico")

# Background tasks
async def background_health_check():
    """Background health monitoring task"""
    while True:
        try:
            # Perform periodic health checks
            await asyncio.sleep(300)  # Every 5 minutes
            
            # Test database connection
            try:
                supabase.client.from_('profiles').select('id').limit(1).execute()
            except Exception as e:
                logger.error(f"Background health check - Database error: {e}")
            
            # Test ERP connection if initialized
            try:
                if erp_integration.erpnext_client:
                    erp_status = await erp_integration.test_connection()
                    if not erp_status["success"]:
                        logger.warning(f"Background health check - ERPNext connection issue: {erp_status.get('error')}")
            except Exception as e:
                logger.error(f"Background health check - ERPNext error: {e}")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Background health check error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error

# Development server
if __name__ == "__main__":
    import uvicorn
    
    uvicorn_config = {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": DEBUG,
        "log_level": "debug" if DEBUG else "info",
        "access_log": True,
        "workers": 1 if DEBUG else 2
    }
    
    if not DEBUG:
        uvicorn_config.update({
            "proxy_headers": True,
            "forwarded_allow_ips": "*"
        })
    
    uvicorn.run(**uvicorn_config)
