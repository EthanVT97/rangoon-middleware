from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os
from decouple import config

from .routes import api_router
from .database.supabase_client import supabase
from .websocket_manager import websocket_manager

# Configuration
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_ORIGINS = config("ALLOWED_ORIGINS", default="http://localhost:3000").split(",")

app = FastAPI(
    title="Rangoon Middleware",
    description="Advanced Excel Import with Custom Mapping & ERP Integration",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include API routes
app.include_router(api_router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/mapping/create", response_class=HTMLResponse)
async def create_mapping_page(request: Request):
    """Column mapping configuration page"""
    return templates.TemplateResponse("mapping_config.html", {"request": request})

@app.get("/upload/status", response_class=HTMLResponse)
async def upload_status_page(request: Request):
    """Upload status monitoring page"""
    return templates.TemplateResponse("upload_status.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "database": "connected" if supabase.client else "disconnected"
    }

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    print("🚀 Rangoon Middleware starting up...")
    # Test database connection
    try:
        # Test Supabase connection
        result = supabase.client.from_('profiles').select('count', count='exact').execute()
        print("✅ Supabase connection established")
    except Exception as e:
        print(f"❌ Database connection error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Rangoon Middleware shutting down...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
