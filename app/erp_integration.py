import httpx
import asyncio
from typing import Dict, Any, List, Optional
import json
from datetime import datetime, timedelta
import time
from enum import Enum
import logging
from decouple import config

from .database.supabase_client import supabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"      # Service unavailable
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered

class ERPEndpoint(Enum):
    CUSTOMERS = "customers"
    PRODUCTS = "products"
    SALES = "sales"
    INVENTORY = "inventory"
    ORDERS = "orders"
    SUPPLIERS = "suppliers"

class CircuitBreaker:
    """Circuit breaker pattern for ERP service protection"""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.last_success_time = None
    
    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit state"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        return True  # HALF_OPEN state allows one trial
    
    def on_success(self):
        """Handle successful request"""
        self.failure_count = 0
        self.last_success_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker reset to CLOSED state")
    
    def on_failure(self):
        """Handle failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time
        }

class ERPIntegration:
    """Enhanced ERP Integration with circuit breaker and advanced features"""
    
    def __init__(self):
        # Configuration from environment with defaults
        self.timeout = config("ERP_TIMEOUT", default=30.0, cast=float)
        self.max_retries = config("ERP_MAX_RETRIES", default=3, cast=int)
        self.retry_delay = config("ERP_RETRY_DELAY", default=1.0, cast=float)
        self.batch_size = config("ERP_BATCH_SIZE", default=50, cast=int)
        self.max_concurrent_requests = config("ERP_MAX_CONCURRENT", default=5, cast=int)
        self.rate_limit_delay = config("ERP_RATE_LIMIT_DELAY", default=0.1, cast=float)
        
        # Circuit breaker instance
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config("ERP_CIRCUIT_FAILURE_THRESHOLD", default=5, cast=int),
            reset_timeout=config("ERP_CIRCUIT_RESET_TIMEOUT", default=60, cast=int)
        )
        
        # Semaphore for limiting concurrent requests
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # Endpoint configuration
        self.endpoint_config = {
            ERPEndpoint.CUSTOMERS: {
                "path": "/api/v1/customers",
                "method": "POST",
                "batch_size": 100,
                "required_fields": ["name", "email"]
            },
            ERPEndpoint.PRODUCTS: {
                "path": "/api/v1/products",
                "method": "POST", 
                "batch_size": 50,
                "required_fields": ["sku", "name", "price"]
            },
            ERPEndpoint.SALES: {
                "path": "/api/v1/sales",
                "method": "POST",
                "batch_size": 30,
                "required_fields": ["customer_id", "product_id", "quantity", "date"]
            },
            ERPEndpoint.INVENTORY: {
                "path": "/api/v1/inventory",
                "method": "POST",
                "batch_size": 100,
                "required_fields": ["product_id", "quantity", "location"]
            },
            ERPEndpoint.ORDERS: {
                "path": "/api/v1/orders",
                "method": "POST",
                "batch_size": 25,
                "required_fields": ["customer_id", "items", "order_date"]
            }
        }
    
    async def send_to_erp(self, data: List[Dict[str, Any]], endpoint: str) -> Dict[str, Any]:
        """Send data to ERP system with enhanced error handling and circuit breaker"""
        
        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            return {
                "success": False,
                "error": "ERP service temporarily unavailable (Circuit Breaker OPEN)",
                "circuit_state": self.circuit_breaker.get_status(),
                "sent_data": data
            }
        
        start_time = datetime.now()
        
        try:
            # Get ERP connection details
            erp_conn = await supabase.get_active_erp_connection()
            if not erp_conn:
                self.circuit_breaker.on_failure()
                return {
                    "success": False, 
                    "error": "No active ERP connection configured",
                    "sent_data": data
                }
            
            # Validate endpoint
            try:
                endpoint_enum = ERPEndpoint(endpoint)
                endpoint_config = self.endpoint_config[endpoint_enum]
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid endpoint: {endpoint}. Available: {[e.value for e in ERPEndpoint]}",
                    "sent_data": data
                }
            
            # Validate data structure
            validated_data, validation_errors = await self._validate_erp_data(data, endpoint_enum)
            if validation_errors and len(validated_data) == 0:
                return {
                    "success": False,
                    "error": "Data validation failed",
                    "validation_errors": validation_errors,
                    "sent_data": data
                }
            
            # Prepare request components
            base_url = erp_conn["base_url"].rstrip('/')
            endpoint_path = erp_conn["endpoints"].get(endpoint, endpoint_config["path"])
            url = f"{base_url}{endpoint_path}"
            
            headers = {
                "Authorization": f"Bearer {erp_conn['api_key']}",
                "Content-Type": "application/json",
                "User-Agent": "Rangoon-Middleware/2.0.0",
                "X-Request-ID": f"req_{int(datetime.now().timestamp())}"
            }
            
            # Process data in batches
            batch_results = await self._process_batches(validated_data, url, headers, endpoint_config)
            
            # Calculate overall results
            successful_batches = [r for r in batch_results if r["status"] == "success"]
            total_sent = sum(r["records_sent"] for r in successful_batches)
            overall_success = len(successful_batches) > 0
            
            # Update circuit breaker based on result
            if overall_success:
                self.circuit_breaker.on_success()
            else:
                self.circuit_breaker.on_failure()
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Log performance metrics
            await self._log_performance_metrics(
                endpoint=endpoint,
                record_count=len(validated_data),
                processing_time=processing_time,
                success_rate=(len(successful_batches) / len(batch_results)) * 100 if batch_results else 0,
                circuit_state=self.circuit_breaker.get_status()
            )
            
            return {
                "success": overall_success,
                "total_records_processed": len(validated_data),
                "total_batches": len(batch_results),
                "successful_batches": len(successful_batches),
                "total_records_sent": total_sent,
                "validation_errors": validation_errors,
                "batch_results": batch_results,
                "processing_time_seconds": round(processing_time, 2),
                "circuit_breaker_status": self.circuit_breaker.get_status(),
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.circuit_breaker.on_failure()
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Log error
            await self._log_error(endpoint, str(e), data, processing_time)
            
            return {
                "success": False, 
                "error": f"ERP integration error: {str(e)}",
                "processing_time_seconds": round(processing_time, 2),
                "circuit_breaker_status": self.circuit_breaker.get_status(),
                "sent_data": data
            }
    
    async def _process_batches(self, data: List[Dict], url: str, headers: Dict, endpoint_config: Dict) -> List[Dict]:
        """Process data in batches with rate limiting and concurrency control"""
        batch_size = endpoint_config.get("batch_size", self.batch_size)
        batch_results = []
        
        tasks = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            task = self._send_batch_with_retry(batch, url, headers, i // batch_size + 1)
            tasks.append(task)
        
        # Execute batches with concurrency control
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in batch results
        processed_results = []
        for result in batch_results:
            if isinstance(result, Exception):
                processed_results.append({
                    "batch": "unknown",
                    "status": "failed",
                    "records_sent": 0,
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _send_batch_with_retry(self, batch: List[Dict], url: str, headers: Dict, batch_number: int) -> Dict:
        """Send a single batch with retry logic"""
        async with self.semaphore:
            # Rate limiting delay
            await asyncio.sleep(self.rate_limit_delay)
            
            for attempt in range(self.max_retries):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(url, json=batch, headers=headers)
                        
                        if response.status_code in [200, 201]:
                            return {
                                "batch": batch_number,
                                "status": "success",
                                "records_sent": len(batch),
                                "response_status": response.status_code,
                                "erp_reference": self._extract_reference(response),
                                "attempts": attempt + 1
                            }
                        elif response.status_code == 429:  # Rate limited
                            retry_after = int(response.headers.get('Retry-After', self.retry_delay * (attempt + 1)))
                            logger.warning(f"Rate limited. Retrying after {retry_after} seconds")
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            error_msg = f"HTTP {response.status_code}: {response.text}"
                            if attempt == self.max_retries - 1:
                                return {
                                    "batch": batch_number,
                                    "status": "failed",
                                    "records_sent": len(batch),
                                    "error": error_msg,
                                    "attempts": attempt + 1
                                }
                            else:
                                await asyncio.sleep(self.retry_delay * (attempt + 1))
                                
                except httpx.TimeoutException:
                    if attempt == self.max_retries - 1:
                        return {
                            "batch": batch_number,
                            "status": "failed",
                            "records_sent": len(batch),
                            "error": "Request timeout",
                            "attempts": attempt + 1
                        }
                    else:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        return {
                            "batch": batch_number,
                            "status": "failed", 
                            "records_sent": len(batch),
                            "error": str(e),
                            "attempts": attempt + 1
                        }
                    else:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
            
            return {
                "batch": batch_number,
                "status": "failed",
                "records_sent": len(batch),
                "error": "Max retries exceeded",
                "attempts": self.max_retries
            }
    
    async def _validate_erp_data(self, data: List[Dict], endpoint: ERPEndpoint) -> tuple:
        """Validate data structure before sending to ERP"""
        endpoint_config = self.endpoint_config.get(endpoint, {})
        required_fields = endpoint_config.get("required_fields", [])
        
        validated_data = []
        validation_errors = []
        
        for index, record in enumerate(data):
            missing_fields = [field for field in required_fields if field not in record or record[field] is None]
            
            if not missing_fields:
                validated_data.append(record)
            else:
                validation_errors.append({
                    "record_index": index,
                    "missing_fields": missing_fields,
                    "record_data": {k: v for k, v in record.items() if k in required_fields}
                })
        
        return validated_data, validation_errors
    
    def _extract_reference(self, response: httpx.Response) -> Optional[str]:
        """Extract reference ID from ERP response"""
        try:
            response_data = response.json()
            return (response_data.get("id") or 
                   response_data.get("reference") or 
                   response_data.get("transaction_id"))
        except:
            return None
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test ERP connection with comprehensive diagnostics"""
        start_time = datetime.now()
        
        try:
            erp_conn = await supabase.get_active_erp_connection()
            if not erp_conn:
                return {
                    "success": False, 
                    "error": "No ERP connection configured",
                    "tested_at": datetime.now().isoformat()
                }
            
            # Test multiple endpoints if available
            test_endpoints = ["/health", "/api/health", "/status", "/api/status"]
            base_url = erp_conn['base_url'].rstrip('/')
            headers = {
                "Authorization": f"Bearer {erp_conn['api_key']}",
                "User-Agent": "Rangoon-Middleware/2.0.0"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                for endpoint in test_endpoints:
                    try:
                        url = f"{base_url}{endpoint}"
                        response = await client.get(url, headers=headers)
                        
                        if response.status_code == 200:
                            response_time = (datetime.now() - start_time).total_seconds()
                            
                            return {
                                "success": True,
                                "status_code": response.status_code,
                                "response_time": round(response_time, 3),
                                "test_endpoint": endpoint,
                                "message": "Connection successful",
                                "circuit_breaker_status": self.circuit_breaker.get_status(),
                                "tested_at": datetime.now().isoformat()
                            }
                    except:
                        continue
            
            # If no endpoint worked, try a simple HEAD request to base URL
            try:
                response = await client.head(base_url, headers=headers)
                response_time = (datetime.now() - start_time).total_seconds()
                
                return {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "response_time": round(response_time, 3),
                    "test_endpoint": "HEAD /",
                    "message": f"Service responding with HTTP {response.status_code}",
                    "circuit_breaker_status": self.circuit_breaker.get_status(),
                    "tested_at": datetime.now().isoformat()
                }
            except Exception as e:
                raise e
                
        except httpx.TimeoutException:
            return {
                "success": False, 
                "error": "Connection timeout - ERP system may be down",
                "response_time": round((datetime.now() - start_time).total_seconds(), 3),
                "tested_at": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False, 
                "error": str(e),
                "response_time": round((datetime.now() - start_time).total_seconds(), 3),
                "tested_at": datetime.now().isoformat()
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive ERP integration status"""
        connection_test = await self.test_connection()
        
        return {
            "erp_connection": connection_test,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "configuration": {
                "timeout": self.timeout,
                "max_retries": self.max_retries,
                "batch_size": self.batch_size,
                "max_concurrent_requests": self.max_concurrent_requests
            },
            "supported_endpoints": [e.value for e in ERPEndpoint],
            "timestamp": datetime.now().isoformat()
        }
    
    async def _log_performance_metrics(self, endpoint: str, record_count: int, 
                                     processing_time: float, success_rate: float,
                                     circuit_state: Dict):
   """Log performance metrics to database"""
        try:
            log_data = {
                "endpoint": endpoint,
                "record_count": record_count,
                "processing_time": processing_time,
                "success_rate": success_rate,
                "circuit_state": circuit_state["state"],
                "failure_count": circuit_state["failure_count"],
                "logged_at": datetime.now().isoformat()
            }
            
            await supabase.create_monitoring_log({
                "log_type": "performance_metrics",
                "log_data": log_data,
                "created_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to log performance metrics: {e}")
    
    async def _log_error(self, endpoint: str, error: str, data: List[Dict], processing_time: float):
        """Log error details to database"""
        try:
            error_data = {
                "endpoint": endpoint,
                "error_message": error,
                "data_sample": data[:3] if data else [],  # Log first 3 records as sample
                "processing_time": processing_time,
                "circuit_breaker_status": self.circuit_breaker.get_status(),
                "logged_at": datetime.now().isoformat()
            }
            
            await supabase.create_monitoring_log({
                "log_type": "erp_error",
                "log_data": error_data,
                "created_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
    
    def reset_circuit_breaker(self):
        """Manually reset circuit breaker (for admin use)"""
        self.circuit_breaker = CircuitBreaker()
        logger.info("Circuit breaker manually reset")

# Global ERP integration instance
erp_integration = ERPIntegration()
