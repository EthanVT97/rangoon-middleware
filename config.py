from decouple import config
from pydantic import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # App Configuration
    app_name: str = "Rangoon Middleware"
    app_version: str = "2.0.0"
    secret_key: str = config("SECRET_KEY")
    debug: bool = config("DEBUG", cast=bool, default=False)
    environment: str = config("ENVIRONMENT", default="development")
    
    # API Configuration
    api_prefix: str = config("API_PREFIX", default="/api")
    allowed_origins: List[str] = config("ALLOWED_ORIGINS", default="http://localhost:3000,http://localhost:8000").split(",")
    allowed_hosts: List[str] = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")
    
    # Supabase Configuration
    supabase_url: str = config("SUPABASE_URL")
    supabase_key: str = config("SUPABASE_KEY")
    supabase_service_key: str = config("SUPABASE_SERVICE_KEY")
    
    # ERPNext Configuration
    erpnext_base_url: str = config("ERPNEXT_BASE_URL", default="")
    erpnext_api_key: str = config("ERPNEXT_API_KEY", default="")
    erpnext_username: str = config("ERPNEXT_USERNAME", default="")
    erpnext_password: str = config("ERPNEXT_PASSWORD", default="")
    erpnext_company: str = config("ERPNEXT_COMPANY", default="Myanmar ShweTech")
    
    # ERPNext Integration Settings
    erpnext_timeout: int = config("ERPNEXT_TIMEOUT", cast=int, default=30)
    erpnext_max_retries: int = config("ERPNEXT_MAX_RETRIES", cast=int, default=3)
    erpnext_retry_delay: float = config("ERPNEXT_RETRY_DELAY", cast=float, default=1.0)
    erpnext_batch_size: int = config("ERPNEXT_BATCH_SIZE", cast=int, default=50)
    erpnext_max_concurrent: int = config("ERPNEXT_MAX_CONCURRENT", cast=int, default=5)
    erpnext_rate_limit_delay: float = config("ERPNEXT_RATE_LIMIT_DELAY", cast=float, default=0.1)
    
    # Circuit Breaker Configuration
    erpnext_circuit_failure_threshold: int = config("ERPNEXT_CIRCUIT_FAILURE_THRESHOLD", cast=int, default=5)
    erpnext_circuit_reset_timeout: int = config("ERPNEXT_CIRCUIT_RESET_TIMEOUT", cast=int, default=60)
    
    # File Processing Configuration
    max_file_size: int = config("MAX_FILE_SIZE", cast=int, default=50)  # MB
    supported_formats: List[str] = config("SUPPORTED_FORMATS", default=".xlsx,.xls,.csv").split(",")
    
    # Security & Authentication
    access_token_expire_minutes: int = config("ACCESS_TOKEN_EXPIRE_MINUTES", cast=int, default=60)
    refresh_token_expire_days: int = config("REFRESH_TOKEN_EXPIRE_DAYS", cast=int, default=7)
    password_reset_expire_minutes: int = config("PASSWORD_RESET_EXPIRE_MINUTES", cast=int, default=30)
    
    # Redis Configuration (for rate limiting and caching)
    redis_host: str = config("REDIS_HOST", default="localhost")
    redis_port: int = config("REDIS_PORT", cast=int, default=6379)
    redis_password: str = config("REDIS_PASSWORD", default="")
    redis_db: int = config("REDIS_DB", cast=int, default=0)
    
    # Monitoring & Logging
    log_level: str = config("LOG_LEVEL", default="INFO")
    enable_metrics: bool = config("ENABLE_METRICS", cast=bool, default=True)
    metrics_interval: int = config("METRICS_INTERVAL", cast=int, default=300)  # 5 minutes
    
    # Test Environment Configuration
    erpnext_test_url: str = config("ERPNEXT_TEST_URL", default="https://rangoontesting.s.erpnext.com")
    erpnext_test_username: str = config("ERPNEXT_TEST_USERNAME", default="rangoon")
    erpnext_test_password: str = config("ERPNEXT_TEST_PASSWORD", default="rangoon@123")
    
    # WebSocket Configuration
    websocket_ping_interval: int = config("WEBSOCKET_PING_INTERVAL", cast=int, default=20)
    websocket_ping_timeout: int = config("WEBSOCKET_PING_TIMEOUT", cast=int, default=10)
    websocket_max_connections: int = config("WEBSOCKET_MAX_CONNECTIONS", cast=int, default=100)
    
    # Background Tasks
    background_task_interval: int = config("BACKGROUND_TASK_INTERVAL", cast=int, default=300)  # 5 minutes
    health_check_interval: int = config("HEALTH_CHECK_INTERVAL", cast=int, default=60)  # 1 minute
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_erpnext_connection_config(self) -> dict:
        """Get ERPNext connection configuration"""
        return {
            "base_url": self.erpnext_base_url or self.erpnext_test_url,
            "api_key": self.erpnext_api_key,
            "username": self.erpnext_username or self.erpnext_test_username,
            "password": self.erpnext_password or self.erpnext_test_password,
            "company": self.erpnext_company,
            "timeout": self.erpnext_timeout,
            "max_retries": self.erpnext_max_retries
        }
    
    def get_erpnext_test_config(self) -> dict:
        """Get ERPNext test configuration"""
        return {
            "base_url": self.erpnext_test_url,
            "username": self.erpnext_test_username,
            "password": self.erpnext_test_password,
            "company": self.erpnext_company
        }
    
    def is_erpnext_configured(self) -> bool:
        """Check if ERPNext is properly configured"""
        return bool(self.erpnext_base_url and self.erpnext_api_key)
    
    def is_test_environment(self) -> bool:
        """Check if running in test environment"""
        return self.environment.lower() in ["test", "testing", "development"]

# Global settings instance
settings = Settings()
