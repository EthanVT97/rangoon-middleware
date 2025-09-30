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
    ITEMS = "Item"
    CUSTOMERS = "Customer"
    SALES_ORDERS = "Sales Order"
    SALES_INVOICES = "Sales Invoice" 
    PAYMENTS = "Payment Entry"
    BINS = "Bin"  # Stock information

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

class ERPNextDataMapper:
    """Map internal data to ERPNext format"""
    
    @staticmethod
    def map_customer(customer_data: Dict) -> Dict:
        return {
            "customer_name": customer_data.get('name'),
            "customer_group": customer_data.get('customer_group', 'Individual'),
            "territory": customer_data.get('territory', 'Myanmar'),
            "mobile_no": customer_data.get('phone', ''),
            "email_id": customer_data.get('email', '')
        }
    
    @staticmethod
    def map_item(item_data: Dict) -> Dict:
        return {
            "item_code": item_data.get('item_code'),
            "item_name": item_data.get('item_name'),
            "item_group": item_data.get('item_group', 'Products'),
            "stock_uom": item_data.get('uom', 'Nos')
        }
    
    @staticmethod
    def map_sales_order(order_data: Dict) -> Dict:
        return {
            "customer": order_data.get('customer_code'),
            "delivery_date": order_data.get('delivery_date'),
            "due_date": order_data.get('due_date'),
            "company": order_data.get('company', 'Myanmar ShweTech'),
            "items": [
                {
                    "item_code": item.get('item_code'),
                    "qty": item.get('quantity', 1),
                    "rate": item.get('rate', 0),
                    "item_name": item.get('item_name', '')
                }
                for item in order_data.get('items', [])
            ]
        }
    
    @staticmethod
    def map_sales_invoice(invoice_data: Dict) -> Dict:
        return {
            "customer": invoice_data.get('customer_code'),
            "posting_date": invoice_data.get('posting_date'),
            "due_date": invoice_data.get('due_date'),
            "update_stock": invoice_data.get('update_stock', 0),
            "items": [
                {
                    "item_code": item.get('item_code'),
                    "qty": item.get('quantity', 1),
                    "rate": item.get('rate', 0),
                    "item_name": item.get('item_name', ''),
                    "warehouse": item.get('warehouse', 'Stores - MST')
                }
                for item in invoice_data.get('items', [])
            ]
        }

class ERPNextClient:
    """ERPNext specific API client"""
    
    def __init__(self, base_url: str, api_key: str, username: str = None, password: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.username = username
        self.password = password
        self.session = httpx.AsyncClient(timeout=30.0)
        self.token = None
        self.is_authenticated = False
    
    async def authenticate(self) -> bool:
        """Authenticate with ERPNext using username/password"""
        if not self.username or not self.password:
            logger.error("Username and password required for ERPNext authentication")
            return False
            
        login_url = f"{self.base_url}/api/method/login"
        payload = {
            "usr": self.username,
            "pwd": self.password
        }
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            response = await self.session.post(login_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('message') == 'Logged In':
                    self.is_authenticated = True
                    logger.info("ERPNext authentication successful")
                    return True
            
            logger.error(f"ERPNext authentication failed: {response.text}")
            return False
            
        except Exception as e:
            logger.error(f"ERPNext authentication error: {e}")
            return False
    
    async def create_document(self, doctype: str, data: Dict) -> Dict:
        """Create a document in ERPNext"""
        url = f"{self.base_url}/api/resource/{doctype}"
        
        headers = {
            "Authorization": f"token {self.api_key}:{self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            response = await self.session.post(url, json=data, headers=headers)
            return {
                "success": response.status_code in [200, 201],
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else {},
                "error": response.text if response.status_code != 200 else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": 500
            }
    
    async def get_documents(self, doctype: str, fields: List[str] = None, filters: Dict = None, limit: int = 100) -> Dict:
        """Get documents from ERPNext"""
        url = f"{self.base_url}/api/resource/{doctype}"
        
        params = {}
        if fields:
            params['fields'] = json.dumps(fields)
        if filters:
            params['filters'] = json.dumps(filters)
        if limit:
            params['limit_page_length'] = limit
            
        headers = {
            "Authorization": f"token {self.api_key}:{self.api_key}",
            "Accept": "application/json"
        }
        
        try:
            response = await self.session.get(url, params=params, headers=headers)
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "data": response.json().get('data', []) if response.status_code == 200 else [],
                "error": response.text if response.status_code != 200 else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": 500
            }

class ERPIntegration:
    """Enhanced ERPNext Integration with circuit breaker and advanced features"""
    
    def __init__(self):
        # Configuration from environment with defaults
        self.timeout = config("ERP_TIMEOUT", default=30.0, cast=float)
        self.max_retries = config("ERP_MAX_RETRIES", default=3, cast=int)
        self.retry_delay = config("ERP_RETRY_DELAY", default=1.0, cast=float)
        self.batch_size = config("ERP_BATCH_SIZE", default=50, cast=int)
        self.max_concurrent_requests = config("ERP_MAX_CONCURRENT", default=5, cast=int)
        
        # Circuit breaker instance
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config("ERP_CIRCUIT_FAILURE_THRESHOLD", default=5, cast=int),
            reset_timeout=config("ERP_CIRCUIT_RESET_TIMEOUT", default=60, cast=int)
        )
        
        # Semaphore for limiting concurrent requests
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # ERPNext client
        self.erpnext_client = None
        
        # Data mapper
        self.mapper = ERPNextDataMapper()
        
        # Endpoint configuration for ERPNext
        self.endpoint_config = {
            ERPEndpoint.CUSTOMERS: {
                "doctype": "Customer",
                "required_fields": ["customer_name", "customer_group"],
                "mapper": self.mapper.map_customer
            },
            ERPEndpoint.ITEMS: {
                "doctype": "Item", 
                "required_fields": ["item_code", "item_name"],
                "mapper": self.mapper.map_item
            },
            ERPEndpoint.SALES_ORDERS: {
                "doctype": "Sales Order",
                "required_fields": ["customer", "items"],
                "mapper": self.mapper.map_sales_order
            },
            ERPEndpoint.SALES_INVOICES: {
                "doctype": "Sales Invoice",
                "required_fields": ["customer", "items"],
                "mapper": self.mapper.map_sales_invoice
            },
            ERPEndpoint.PAYMENTS: {
                "doctype": "Payment Entry",
                "required_fields": ["payment_type", "party", "paid_amount"],
                "mapper": None  # Will be implemented as needed
            }
        }
    
    async def initialize_erpnext(self, base_url: str, api_key: str, username: str = None, password: str = None):
        """Initialize ERPNext client with credentials"""
        self.erpnext_client = ERPNextClient(base_url, api_key, username, password)
        
        # Authenticate if username/password provided
        if username and password:
            auth_success = await self.erpnext_client.authenticate()
            if not auth_success:
                logger.error("Failed to authenticate with ERPNext")
                return False
        return True
    
    async def send_to_erpnext(self, data: List[Dict[str, Any]], endpoint: str) -> Dict[str, Any]:
        """Send data to ERPNext system with enhanced error handling"""
        
        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            return {
                "success": False,
                "error": "ERPNext service temporarily unavailable (Circuit Breaker OPEN)",
                "circuit_state": self.circuit_breaker.get_status(),
                "sent_data": data
            }
        
        start_time = datetime.now()
        
        try:
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
            
            # Check if ERPNext client is initialized
            if not self.erpnext_client:
                return {
                    "success": False,
                    "error": "ERPNext client not initialized. Call initialize_erpnext() first.",
                    "sent_data": data
                }
            
            # Validate and map data
            validated_data, validation_errors = await self._validate_and_map_data(data, endpoint_enum)
            if validation_errors and len(validated_data) == 0:
                return {
                    "success": False,
                    "error": "Data validation failed",
                    "validation_errors": validation_errors,
                    "sent_data": data
                }
            
            # Process data in batches
            batch_results = await self._process_erpnext_batches(validated_data, endpoint_config["doctype"])
            
            # Calculate overall results
            successful_records = sum(r["records_sent"] for r in batch_results if r["status"] == "success")
            overall_success = successful_records > 0
            
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
                success_rate=(successful_records / len(validated_data)) * 100 if validated_data else 0,
                circuit_state=self.circuit_breaker.get_status()
            )
            
            return {
                "success": overall_success,
                "total_records_processed": len(validated_data),
                "successful_records": successful_records,
                "failed_records": len(validated_data) - successful_records,
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
                "error": f"ERPNext integration error: {str(e)}",
                "processing_time_seconds": round(processing_time, 2),
                "circuit_breaker_status": self.circuit_breaker.get_status(),
                "sent_data": data
            }
    
    async def _process_erpnext_batches(self, data: List[Dict], doctype: str) -> List[Dict]:
        """Process data in batches for ERPNext"""
        batch_results = []
        
        tasks = []
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i + self.batch_size]
            task = self._send_erpnext_batch_with_retry(batch, doctype, i // self.batch_size + 1)
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
    
    async def _send_erpnext_batch_with_retry(self, batch: List[Dict], doctype: str, batch_number: int) -> Dict:
        """Send a single batch to ERPNext with retry logic"""
        async with self.semaphore:
            batch_result = {
                "batch": batch_number,
                "status": "partial",
                "records_sent": 0,
                "failed_records": [],
                "attempts": 0
            }
            
            for record in batch:
                for attempt in range(self.max_retries):
                    try:
                        result = await self.erpnext_client.create_document(doctype, record)
                        batch_result["attempts"] += 1
                        
                        if result["success"]:
                            batch_result["records_sent"] += 1
                            break
                        else:
                            if attempt == self.max_retries - 1:
                                batch_result["failed_records"].append({
                                    "record": record,
                                    "error": result["error"]
                                })
                            else:
                                await asyncio.sleep(self.retry_delay * (attempt + 1))
                    
                    except Exception as e:
                        if attempt == self.max_retries - 1:
                            batch_result["failed_records"].append({
                                "record": record,
                                "error": str(e)
                            })
                        else:
                            await asyncio.sleep(self.retry_delay * (attempt + 1))
            
            # Determine batch status
            if batch_result["records_sent"] == len(batch):
                batch_result["status"] = "success"
            elif batch_result["records_sent"] == 0:
                batch_result["status"] = "failed"
            else:
                batch_result["status"] = "partial"
            
            return batch_result
    
    async def _validate_and_map_data(self, data: List[Dict], endpoint: ERPEndpoint) -> tuple:
        """Validate data structure and map to ERPNext format"""
        endpoint_config = self.endpoint_config.get(endpoint, {})
        required_fields = endpoint_config.get("required_fields", [])
        mapper_func = endpoint_config.get("mapper")
        
        validated_data = []
        validation_errors = []
        
        for index, record in enumerate(data):
            # Validate required fields
            missing_fields = [field for field in required_fields if field not in record or record[field] is None]
            
            if missing_fields:
                validation_errors.append({
                    "record_index": index,
                    "missing_fields": missing_fields,
                    "record_data": {k: v for k, v in record.items() if k in required_fields}
                })
                continue
            
            # Map data if mapper function exists
            if mapper_func:
                try:
                    mapped_record = mapper_func(record)
                    validated_data.append(mapped_record)
                except Exception as e:
                    validation_errors.append({
                        "record_index": index,
                        "error": f"Mapping failed: {str(e)}",
                        "record_data": record
                    })
            else:
                validated_data.append(record)
        
        return validated_data, validation_errors
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test ERPNext connection with comprehensive diagnostics"""
        start_time = datetime.now()
        
        try:
            if not self.erpnext_client:
                return {
                    "success": False, 
                    "error": "ERPNext client not initialized",
                    "tested_at": datetime.now().isoformat()
                }
            
            # Test by getting items list (lightweight operation)
            result = await self.erpnext_client.get_documents("Item", fields=["name"], limit=1)
            response_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": result["success"],
                "status_code": result["status_code"],
                "response_time": round(response_time, 3),
                "test_endpoint": "/api/resource/Item",
                "message": "Connection successful" if result["success"] else result["error"],
                "circuit_breaker_status": self.circuit_breaker.get_status(),
                "tested_at": datetime.now().isoformat()
            }
                
        except httpx.TimeoutException:
            return {
                "success": False, 
                "error": "Connection timeout - ERPNext system may be down",
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
    
    async def get_items(self, fields: List[str] = None, limit: int = 100) -> Dict:
        """Get items from ERPNext"""
        if not fields:
            fields = ["name", "item_code", "item_name", "item_group"]
        
        return await self.erpnext_client.get_documents("Item", fields=fields, limit=limit)
    
    async def get_customers(self, fields: List[str] = None, limit: int = 100) -> Dict:
        """Get customers from ERPNext"""
        if not fields:
            fields = ["name", "customer_name", "customer_type", "customer_group", "territory"]
        
        return await self.erpnext_client.get_documents("Customer", fields=fields, limit=limit)
    
    async def get_stock_info(self, fields: List[str] = None, limit: int = 100) -> Dict:
        """Get stock information from ERPNext"""
        if not fields:
            fields = ["name", "item_code", "warehouse", "actual_qty"]
        
        return await self.erpnext_client.get_documents("Bin", fields=fields, limit=limit)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive ERPNext integration status"""
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
                "data_sample": data[:3] if data else [],
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
    
    def reset_circuit_breaker(self):
        """Manually reset circuit breaker (for admin use)"""
        self.circuit_breaker = CircuitBreaker()
        logger.info("Circuit breaker manually reset")

# Global ERPNext integration instance
erp_integration = ERPIntegration()
