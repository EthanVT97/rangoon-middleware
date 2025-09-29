import pandas as pd
from typing import Dict, Any, List
import re

class MappingEngine:
    def __init__(self):
        self.transformations = {
            "uppercase": lambda x: str(x).upper() if x else "",
            "lowercase": lambda x: str(x).lower() if x else "",
            "title_case": lambda x: str(x).title() if x else "",
            "trim": lambda x: str(x).strip() if x else "",
            "phone_format": self._format_phone,
            "email_lower": lambda x: str(x).lower().strip() if x else "",
            "boolean": lambda x: bool(x) if x else False,
            "number": lambda x: float(x) if x else 0.0,
            "integer": lambda x: int(float(x)) if x else 0,
            "remove_special_chars": self._remove_special_chars,
            "date_iso": self._format_date_iso
        }
    
    def _format_phone(self, phone):
        """Format phone number"""
        if not phone:
            return ""
        # Remove non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', str(phone))
        return cleaned
    
    def _remove_special_chars(self, text):
        """Remove special characters"""
        if not text:
            return ""
        return re.sub(r'[^\w\s]', '', str(text))
    
    def _format_date_iso(self, date_str):
        """Format date to ISO format"""
        if not date_str:
            return ""
        try:
            # Try to parse various date formats
            if isinstance(date_str, str):
                # Handle common date formats
                if '/' in date_str:
                    from datetime import datetime
                    date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                    return date_obj.isoformat()
                elif '-' in date_str:
                    from datetime import datetime
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    return date_obj.isoformat()
            return str(date_str)
        except:
            return str(date_str)
    
    def apply_mapping(self, df: pd.DataFrame, mapping_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Apply column mapping and transformations to DataFrame
        
        Args:
            df: Input DataFrame
            mapping_config: Mapping configuration
            
        Returns:
            List of mapped data dictionaries
        """
        mapped_data = []
        target_columns = mapping_config.get("target_columns", {})
        
        for _, row in df.iterrows():
            mapped_row = {}
            
            for target_field, mapping in target_columns.items():
                source_column = mapping.get("source_column")
                transformation = mapping.get("transformation")
                default_value = mapping.get("default_value")
                is_required = mapping.get("required", False)
                
                # Get value from source
                if source_column and source_column in df.columns:
                    value = row[source_column]
                    # Handle pandas NaN
                    if pd.isna(value):
                        value = default_value if default_value is not None else ""
                else:
                    value = default_value if default_value is not None else ""
                
                # Apply transformation
                if transformation and transformation in self.transformations:
                    try:
                        value = self.transformations[transformation](value)
                    except Exception as e:
                        # If transformation fails, use default value or original
                        value = default_value if default_value is not None else value
                
                # Handle required fields
                if is_required and not value:
                    raise ValueError(f"Required field '{target_field}' is empty for row {_ + 2}")
                
                mapped_row[target_field] = value
            
            mapped_data.append(mapped_row)
        
        return mapped_data
    
    def validate_mapping_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate mapping configuration
        
        Args:
            config: Mapping configuration to validate
            
        Returns:
            Dict with validation results
        """
        errors = []
        warnings = []
        
        # Basic validation
        if not config.get("mapping_name"):
            errors.append("Mapping name is required")
        
        if not config.get("source_columns"):
            errors.append("Source columns configuration is required")
        
        if not config.get("target_columns"):
            errors.append("Target columns configuration is required")
        
        # Validate source columns
        source_columns = config.get("source_columns", [])
        for i, col in enumerate(source_columns):
            if not col.get("name"):
                errors.append(f"Source column {i + 1} must have a name")
            if col.get("required") and not col.get("name"):
                errors.append(f"Required source column {i + 1} must have a name")
        
        # Validate target columns
        target_columns = config.get("target_columns", {})
        for target_field, mapping in target_columns.items():
            if not target_field:
                errors.append("Target field name cannot be empty")
            
            if mapping.get("required") and not mapping.get("source_column"):
                errors.append(f"Required target field '{target_field}' must have a source column mapping")
            
            # Validate transformation
            transformation = mapping.get("transformation")
            if transformation and transformation not in self.transformations:
                warnings.append(f"Unknown transformation '{transformation}' for field '{target_field}'")
        
        # Validate ERP endpoint
        erp_endpoint = config.get("erp_endpoint")
        valid_endpoints = ["customers", "products", "sales", "inventory", "orders"]
        if erp_endpoint and erp_endpoint not in valid_endpoints:
            warnings.append(f"ERP endpoint '{erp_endpoint}' may not be standard")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def generate_sample_mapping(self, data_type: str = "customers") -> Dict[str, Any]:
        """
        Generate sample mapping configuration for different data types
        
        Args:
            data_type: Type of data (customers, products, sales, etc.)
            
        Returns:
            Sample mapping configuration
        """
        samples = {
            "customers": {
                "mapping_name": "Customer Import Template",
                "description": "Sample mapping for customer data import",
                "source_columns": [
                    {"name": "Customer_ID", "type": "string", "required": True},
                    {"name": "Full_Name", "type": "string", "required": True},
                    {"name": "Email", "type": "string", "required": False},
                    {"name": "Phone", "type": "string", "required": False},
                    {"name": "Address", "type": "string", "required": False}
                ],
                "target_columns": {
                    "customer_code": {
                        "source_column": "Customer_ID",
                        "transformation": "uppercase",
                        "required": True,
                        "default_value": ""
                    },
                    "customer_name": {
                        "source_column": "Full_Name",
                        "transformation": "title_case",
                        "required": True,
                        "default_value": ""
                    },
                    "email_address": {
                        "source_column": "Email",
                        "transformation": "email_lower",
                        "required": False,
                        "default_value": ""
                    },
                    "phone_number": {
                        "source_column": "Phone",
                        "transformation": "phone_format",
                        "required": False,
                        "default_value": ""
                    }
                },
                "erp_endpoint": "customers"
            },
            "products": {
                "mapping_name": "Product Import Template",
                "description": "Sample mapping for product data import",
                "source_columns": [
                    {"name": "Product_Code", "type": "string", "required": True},
                    {"name": "Product_Name", "type": "string", "required": True},
                    {"name": "Price", "type": "number", "required": True},
                    {"name": "Stock_Qty", "type": "number", "required": False}
                ],
                "target_columns": {
                    "product_sku": {
                        "source_column": "Product_Code",
                        "transformation": "uppercase",
                        "required": True
                    },
                    "product_name": {
                        "source_column": "Product_Name",
                        "transformation": "trim",
                        "required": True
                    },
                    "unit_price": {
                        "source_column": "Price",
                        "transformation": "number",
                        "required": True
                    },
                    "stock_quantity": {
                        "source_column": "Stock_Qty",
                        "transformation": "integer",
                        "required": False,
                        "default_value": 0
                    }
                },
                "erp_endpoint": "products"
            }
        }
        
        return samples.get(data_type, samples["customers"])

# Global mapping engine instance
mapping_engine = MappingEngine()
