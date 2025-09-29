from decouple import config
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Supabase
    supabase_url: str = config("SUPABASE_URL")
    supabase_key: str = config("SUPABASE_KEY")
    supabase_service_key: str = config("SUPABASE_SERVICE_KEY")
    
    # App
    secret_key: str = config("SECRET_KEY")
    debug: bool = config("DEBUG", cast=bool, default=False)
    allowed_origins: list = config("ALLOWED_ORIGINS", default="http://localhost:3000").split(",")
    
    # ERP
    erp_base_url: str = config("ERP_BASE_URL")
    erp_api_key: str = config("ERP_API_KEY")

settings = Settings()
