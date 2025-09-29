from fastapi import APIRouter

# Import route modules
from . import auth_routes, dashboard_routes, mapping_routes, import_routes, monitoring_routes

# Main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(auth_routes.router, prefix="/auth", tags=["authentication"])
api_router.include_router(dashboard_routes.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(mapping_routes.router, prefix="/mappings", tags=["column-mappings"])
api_router.include_router(import_routes.router, prefix="/import", tags=["file-import"])
api_router.include_router(monitoring_routes.router, prefix="/monitoring", tags=["monitoring"])
