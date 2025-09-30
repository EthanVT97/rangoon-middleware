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
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class ERPEndpoint(Enum):
    ITEM = "Item"
    CUSTOMER = "Customer"
    SALES_ORDER = "Sales Order"
    SALES_INVOICE = "Sales Invoice"
    PAYMENT_ENTRY = "Payment Entry"
    BIN = "Bin"
    BOM = "BOM"

class CircuitBreaker:
    """Circuit breaker pattern for ERPNext service protection"""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.last_success_time = None
    
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        return True
    
    def on_success(self):
        self.failure_count = 0
        self.last_success_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker reset to CLOSED state")
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time
        }

class ERPNextIntegration:
    """ERPNext Integration with Frappe/ERPNext API compatibility"""
    
    def __init__(self):
        # Configuration from environment
        self.timeout = config("ERP_TIMEOUT", default=30.0, cast=float)
        self.max_retries = config("ERP_MAX_RETRIES", default=3, cast=int)
        self.retry_delay = config("ERP_RETRY_DELAY", default=1.0, cast=float)
        self.batch_size = config("ERP_BATCH_SIZE", default=10, cast=int)  # Reduced for ERPNext
        self.max_concurrent_requests = config("ERP_MAX_CONCURRENT", default=3, cast=int)  # Reduced for ERPNext
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config("ERP_CIRCUIT_FAILURE_THRESHOLD", default=5, cast=int),
            reset_timeout=config("ERP_CIRCUIT_RESET_TIMEOUT", default=60, cast=int)
        )
        
        # Semaphore for limiting concurrent requests
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # ERPNext endpoint configuration based on Postman collection
        self.endpoint_config = {
            ERPEndpoint.ITEM: {
                "path": "/api/resource/Item",
                "method": "POST",
                "required_fields": ["item_code", "item_name"],
                "fields_query": ["name", "item_code", "item_name", "item_group"]
            },
            ERPEndpoint.CUSTOMER: {
                "path": "/api/resource/Customer",
                "method": "POST",
                "required_fields": ["customer_name"],
                "fields_query": ["name", "customer_name", "customer_type", "email_id", "customer_group", "territory", "mobile_no"]
            },
            ERPEndpoint.SALES_ORDER: {
                "path": "/api/resource/Sales Order",
                "method": "POST",
                "required_fields": ["customer", "items"],
                "fields_query": ["name", "customer", "status", "grand_total"]
            },
            ERPEndpoint.SALES_INVOICE: {
                "path": "/api/resource/Sales Invoice",
                "method": "POST",
                "required_fields": ["customer", "items"],
                "fields_query": ["name", "customer", "status", "grand_total", "company"]
            },
            ERPEndpoint.PAYMENT_ENTRY: {
                "path": "/api/resource/Payment Entry",
                "method": "POST",
                "required_fields": ["payment_type", "party_type", "party", "paid_amount"],
                "fields_query": ["name", "paid_amount", "posting_date", "status"]
            },
            ERPEndpoint.BIN: {
                "path": "/api/resource/Bin",
                "method": "GET",
                "required_fields": [],
                "fields_query": ["name", "item_code", "warehouse", "actual_qty"]
            },
            ERPEndpoint.BOM: {
                "path": "/api/resource/BOM",
                "method": "POST",
                "required_fields": ["item", "quantity", "items"],
                "fields_query": []
            }
        }
        
        # ERPNext connection details
        self.base_url = config("ERP_BASE_URL", default="https://shwetech.frappe.cloud")
        self.api_key = config("ERP_API_KEY", default="")
        self.api_secret = config("ERP_API_SECRET", default="")
        self.username = config("ERP_USERNAME", default="norabakery.software@gmail.com")
        self.password = config("ERP_PASSWORD", default="rangoon@123")
        
        # Session management
        self.session = None
        self.token = None

    async def initialize_session(self):
        """Initialize ERPNext session with login"""
        if self.session is None:
            self.session = httpx.AsyncClient(timeout=self.timeout)
            
        # Login to ERPNext to get session token
        login_url = f"{self.base_url}/api/method/login"
        login_data = {
            "usr": self.username,
            "pwd": self.password
        }
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            response = await self.session.post(login_url, json=login_data, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result.get("message") == "Logged In":
                    logger.info("ERPNext login successful")
                    # ERPNext uses session cookies, no explicit token in response
                    return True
            logger.error(f"ERPNext login failed: {response.text}")
            return False
        except Exception as e:
            logger.error(f"ERPNext session initialization failed: {e}")
            return False

    async def send_to_erpnext(self, data: List[Dict[str, Any]], endpoint: str, operation: str = "create") -> Dict[str, Any]:
        """Send data to ERPNext with enhanced error handling"""
        
        if not self.circuit_breaker.can_execute():
            return {
                "success": False,
                "error": "ERPNext service temporarily unavailable (Circuit Breaker OPEN)",
                "circuit_state": self.circuit_breaker.get_status(),
                "sent_data": data
            }
        
        start_time = datetime.now()
        
        try:
            # Initialize session if not already done
            if not self.session:
                if not await self.initialize_session():
                    self.circuit_breaker.on_failure()
                    return {
                        "success": False,
                        "error": "ERPNext authentication failed",
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
            validated_data, validation_errors = await self._validate_erpnext_data(data, endpoint_enum, operation)
            if validation_errors and len(validated_data) == 0:
                return {
                    "success": False,
                    "error": "Data validation failed",
                    "validation_errors": validation_errors,
                    "sent_data": data
                }
            
            # Prepare URL and headers
            url = f"{self.base_url}{endpoint_config['path']}"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"token {self.api_key}:{self.api_secret}" if self.api_key and self.api_secret else ""
            }
            
            # Process based on operation type
            if operation == "create":
                results = await self._create_documents(validated_data, url, headers, endpoint_config)
            elif operation == "update":
                results = await self._update_documents(validated_data, url, headers, endpoint_config)
            elif operation == "get":
                results = await self._get_documents(validated_data, url, headers, endpoint_config)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "sent_data": data
                }
            
            # Calculate overall results
            successful_ops = [r for r in results if r["status"] == "success"]
            overall_success = len(successful_ops) > 0
            
            if overall_success:
                self.circuit_breaker.on_success()
            else:
                self.circuit_breaker.on_failure()
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Log performance metrics
            await self._log_performance_metrics(
                endpoint=endpoint,
                operation=operation,
                record_count=len(validated_data),
                processing_time=processing_time,
                success_rate=(len(successful_ops) / len(results)) * 100 if results else 0,
                circuit_state=self.circuit_breaker.get_status()
            )
            
            return {
                "success": overall_success,
                "operation": operation,
                "total_records_processed": len(validated_data),
                "successful_operations": len(successful_ops),
                "failed_operations": len(results) - len(successful_ops),
                "validation_errors": validation_errors,
                "operation_results": results,
                "processing_time_seconds": round(processing_time, 2),
                "circuit_breaker_status": self.circuit_breaker.get_status(),
                "processed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.circuit_breaker.on_failure()
            processing_time = (datetime.now() - start_time).total_seconds()
            
            await self._log_error(endpoint, str(e), data, processing_time)
            
            return {
                "success": False,
                "error": f"ERPNext integration error: {str(e)}",
                "processing_time_seconds": round(processing_time, 2),
                "circuit_breaker_status": self.circuit_breaker.get_status(),
                "sent_data": data
            }

    async def _create_documents(self, data: List[Dict], url: str, headers: Dict, endpoint_config: Dict) -> List[Dict]:
        """Create documents in ERPNext"""
        tasks = []
        for record in data:
            task = self._send_single_request(record, url, headers, "POST", endpoint_config)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._process_results(results)

    async def _update_documents(self, data: List[Dict], url: str, headers: Dict, endpoint_config: Dict) -> List[Dict]:
        """Update documents in ERPNext"""
        tasks = []
        for record in data:
            doc_name = record.get('name')
            if not doc_name:
                continue
            update_url = f"{url}/{doc_name}"
            task = self._send_single_request(record, update_url, headers, "PUT", endpoint_config)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._process_results(results)

    async def _get_documents(self, data: List[Dict], url: str, headers: Dict, endpoint_config: Dict) -> List[Dict]:
        """Get documents from ERPNext"""
        tasks = []
        for record in data:
            doc_name = record.get('name')
            if doc_name:
                get_url = f"{url}/{doc_name}"
            else:
                # List operation with filters
                get_url = url
                if 'filters' in record:
                    get_url += f"?filters={json.dumps(record['filters'])}"
                if 'fields' in record:
                    fields = record.get('fields', endpoint_config.get('fields_query', []))
                    get_url += f"&fields={json.dumps(fields)}"
                get_url += f"&limit_page_length={record.get('limit', 100)}"
            
            task = self._send_single_request({}, get_url, headers, "GET", endpoint_config)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._process_results(results)

    async def _send_single_request(self, data: Dict, url: str, headers: Dict, method: str, endpoint_config: Dict) -> Dict:
        """Send single request to ERPNext with retry logic"""
        async with self.semaphore:
            for attempt in range(self.max_retries):
                try:
                    if method == "GET":
                        response = await self.session.get(url, headers=headers)
                    elif method == "POST":
                        response = await self.session.post(url, json=data, headers=headers)
                    elif method == "PUT":
                        response = await self.session.put(url, json=data, headers=headers)
                    else:
                        return {
                            "status": "failed",
                            "error": f"Unsupported method: {method}",
                            "attempts": attempt + 1
                        }
                    
                    if response.status_code in [200, 201]:
                        response_data = response.json()
                        return {
                            "status": "success",
                            "data": response_data.get("data", response_data),
                            "response_status": response.status_code,
                            "attempts": attempt + 1,
                            "doc_name": response_data.get("data", {}).get("name") if method != "GET" else None
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
                                "status": "failed",
                                "error": error_msg,
                                "attempts": attempt + 1
                            }
                        else:
                            await asyncio.sleep(self.retry_delay * (attempt + 1))
                            
                except httpx.TimeoutException:
                    if attempt == self.max_retries - 1:
                        return {
                            "status": "failed",
                            "error": "Request timeout",
                            "attempts": attempt + 1
                        }
                    else:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        return {
                            "status": "failed",
                            "error": str(e),
                            "attempts": attempt + 1
                        }
                    else:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
            
            return {
                "status": "failed",
                "error": "Max retries exceeded",
                "attempts": self.max_retries
            }

    def _process_results(self, results: List) -> List[Dict]:
        """Process and normalize results from async operations"""
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    "status": "failed",
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        return processed_results

    async def _validate_erpnext_data(self, data: List[Dict], endpoint: ERPEndpoint, operation: str) -> tuple:
        """Validate data structure for ERPNext"""
        endpoint_config = self.endpoint_config.get(endpoint, {})
        
        validated_data = []
        validation_errors = []
        
        for index, record in enumerate(data):
            # Skip validation for GET operations
            if operation == "get":
                validated_data.append(record)
                continue
                
            required_fields = endpoint_config.get("required_fields", [])
            missing_fields = [field for field in required_fields if field not in record or record[field] is None]
            
            if not missing_fields:
                validated_data.append(record)
            else:
                validation_errors.append({
                    "record_index": index,
                    "missing_fields": missing_fields,
                    "operation": operation
                })
        
        return validated_data, validation_errors

    async def test_connection(self) -> Dict[str, Any]:
        """Test ERPNext connection with login"""
        start_time = datetime.now()
        
        try:
            if not await self.initialize_session():
                return {
                    "success": False,
                    "error": "ERPNext authentication failed",
                    "tested_at": datetime.now().isoformat()
                }
            
            # Test a simple API call
            test_url = f"{self.base_url}/api/resource/Item?fields=[\"name\"]&limit_page_length=1"
            headers = {
                "Authorization": f"token {self.api_key}:{self.api_secret}" if self.api_key and self.api_secret else "",
                "Content-Type": "application/json"
            }
            
            response = await self.session.get(test_url, headers=headers)
            response_time = (datetime.now() - start_time).total_seconds()
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response_time": round(response_time, 3),
                    "message": "ERPNext connection successful",
                    "circuit_breaker_status": self.circuit_breaker.get_status(),
                    "tested_at": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"ERPNext API test failed: {response.text}",
                    "response_time": round(response_time, 3),
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
        """Get comprehensive ERPNext integration status"""
        connection_test = await self.test_connection()
        
        return {
            "erp_connection": connection_test,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "configuration": {
                "base_url": self.base_url,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
                "batch_size": self.batch_size,
                "max_concurrent_requests": self.max_concurrent_requests
            },
            "supported_endpoints": [e.value for e in ERPEndpoint],
            "timestamp": datetime.now().isoformat()
        }

    async def _log_performance_metrics(self, endpoint: str, operation: str, record_count: int, 
                                     processing_time: float, success_rate: float,
                                     circuit_state: Dict):
        """Log performance metrics to database"""
        try:
            log_data = {
                "endpoint": endpoint,
                "operation": operation,
                "record_count": record_count,
                "processing_time": processing_time,
                "success_rate": success_rate,
                "circuit_state": circuit_state["state"],
                "failure_count": circuit_state["failure_count"],
                "logged_at": datetime.now().isoformat()
            }
            
            await supabase.create_monitoring_log({
                "log_type": "erpnext_performance",
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
                "data_sample": data[:2] if data else [],
                "processing_time": processing_time,
                "circuit_breaker_status": self.circuit_breaker.get_status(),
                "logged_at": datetime.now().isoformat()
            }
            
            await supabase.create_monitoring_log({
                "log_type": "erpnext_error",
                "log_data": error_data,
                "created_at": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.aclose()
            self.session = None

    def reset_circuit_breaker(self):
        """Manually reset circuit breaker"""
        self.circuit_breaker = CircuitBreaker()
        logger.info("Circuit breaker manually reset")

# Global ERPNext integration instance
erpnext_integration = ERPNextIntegration()
