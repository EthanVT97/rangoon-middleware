import httpx
import asyncio
from typing import Dict, Any, List
import json
from .database import ERPConnection, SessionLocal

class ERPIntegration:
    def __init__(self):
        self.db = SessionLocal()
    
    async def send_to_erp(self, data: List[Dict[str, Any]], endpoint: str, mapping_id: int) -> Dict[str, Any]:
        """Send data to ERP system"""
        try:
            # Get ERP connection details
            erp_conn = self.db.query(ERPConnection).filter(ERPConnection.is_active == True).first()
            if not erp_conn:
                return {"success": False, "error": "No active ERP connection configured"}
            
            # Prepare request
            url = f"{erp_conn.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            headers = {
                "Authorization": f"Bearer {erp_conn.api_key}",
                "Content-Type": "application/json"
            }
            
            # Send data in batches (to avoid timeout)
            batch_size = 50
            results = []
            
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=batch, headers=headers)
                    
                    if response.status_code == 200:
                        batch_result = response.json()
                        results.append({
                            "batch": i // batch_size + 1,
                            "status": "success",
                            "processed": len(batch),
                            "response": batch_result
                        })
                    else:
                        results.append({
                            "batch": i // batch_size + 1,
                            "status": "failed",
                            "processed": len(batch),
                            "error": f"HTTP {response.status_code}: {response.text}"
                        })
            
            return {
                "success": True,
                "total_batches": len(results),
                "results": results
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test ERP connection"""
        try:
            erp_conn = self.db.query(ERPConnection).filter(ERPConnection.is_active == True).first()
            if not erp_conn:
                return {"success": False, "error": "No ERP connection configured"}
            
            url = f"{erp_conn.base_url.rstrip('/')}/api/health"
            headers = {"Authorization": f"Bearer {erp_conn.api_key}"}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                
                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "response": response.text if response.status_code != 200 else "Connection successful"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}

# ERP endpoint configurations
ERP_ENDPOINTS = {
    "customers": "/api/v1/customers/batch",
    "products": "/api/v1/products/batch", 
    "sales": "/api/v1/sales/invoices",
    "inventory": "/api/v1/inventory/updates"
}
