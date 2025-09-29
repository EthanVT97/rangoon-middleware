import httpx
import asyncio
from typing import Dict, Any, List
import json
from datetime import datetime

from .database.supabase_client import supabase

class ERPIntegration:
    def __init__(self):
        self.timeout = 30.0
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def send_to_erp(self, data: List[Dict[str, Any]], endpoint: str) -> Dict[str, Any]:
        """Send data to ERP system"""
        try:
            # Get ERP connection details
            erp_conn = await supabase.get_active_erp_connection()
            if not erp_conn:
                return {
                    "success": False, 
                    "error": "No active ERP connection configured",
                    "sent_data": data
                }
            
            # Prepare request
            base_url = erp_conn["base_url"].rstrip('/')
            endpoint_path = erp_conn["endpoints"].get(endpoint, f"/api/{endpoint}")
            url = f"{base_url}{endpoint_path}"
            
            headers = {
                "Authorization": f"Bearer {erp_conn['api_key']}",
                "Content-Type": "application/json",
                "User-Agent": "Rangoon-Middleware/2.0.0"
            }
            
            # Send data in batches to avoid timeout
            batch_size = 50
            results = []
            
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                
                for attempt in range(self.max_retries):
                    try:
                        async with httpx.AsyncClient(timeout=self.timeout) as client:
                            response = await client.post(url, json=batch, headers=headers)
                            
                            if response.status_code in [200, 201]:
                                batch_result = response.json()
                                results.append({
                                    "batch": i // batch_size + 1,
                                    "status": "success",
                                    "records_sent": len(batch),
                                    "response": batch_result
                                })
                                break
                            else:
                                if attempt == self.max_retries - 1:  # Last attempt
                                    results.append({
                                        "batch": i // batch_size + 1,
                                        "status": "failed",
                                        "records_sent": len(batch),
                                        "error": f"HTTP {response.status_code}: {response.text}"
                                    })
                                else:
                                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                                    
                    except httpx.TimeoutException:
                        if attempt == self.max_retries - 1:
                            results.append({
                                "batch": i // batch_size + 1,
                                "status": "failed",
                                "records_sent": len(batch),
                                "error": "Request timeout"
                            })
                        else:
                            await asyncio.sleep(self.retry_delay * (attempt + 1))
                    
                    except Exception as e:
                        if attempt == self.max_retries - 1:
                            results.append({
                                "batch": i // batch_size + 1,
                                "status": "failed", 
                                "records_sent": len(batch),
                                "error": str(e)
                            })
                        else:
                            await asyncio.sleep(self.retry_delay * (attempt + 1))
            
            # Calculate overall success
            successful_batches = [r for r in results if r["status"] == "success"]
            total_sent = sum(r["records_sent"] for r in successful_batches)
            
            return {
                "success": len(successful_batches) > 0,
                "total_batches": len(results),
                "successful_batches": len(successful_batches),
                "total_records_sent": total_sent,
                "results": results,
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False, 
                "error": str(e),
                "sent_data": data
            }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test ERP connection"""
        try:
            erp_conn = await supabase.get_active_erp_connection()
            if not erp_conn:
                return {
                    "success": False, 
                    "error": "No ERP connection configured"
                }
            
            url = f"{erp_conn['base_url'].rstrip('/')}/health"
            headers = {
                "Authorization": f"Bearer {erp_conn['api_key']}",
                "User-Agent": "Rangoon-Middleware/2.0.0"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                
                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds(),
                    "message": "Connection successful" if response.status_code == 200 else f"HTTP {response.status_code}: {response.text}"
                }
                
        except httpx.TimeoutException:
            return {
                "success": False, 
                "error": "Connection timeout - ERP system may be down"
            }
        except Exception as e:
            return {
                "success": False, 
                "error": str(e)
            }

# ERP endpoint configurations
ERP_ENDPOINTS = {
    "customers": "customers",
    "products": "products", 
    "sales": "sales",
    "inventory": "inventory",
    "orders": "orders"
}

# Global ERP integration instance
erp_integration = ERPIntegration()
