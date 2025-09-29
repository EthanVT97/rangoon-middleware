import pandas as pd
from typing import Dict, Any, List
import json

class MappingEngine:
    def __init__(self):
        self.transformations = {
            "uppercase": lambda x: str(x).upper() if x else "",
            "lowercase": lambda x: str(x).lower() if x else "",
            "trim": lambda x: str(x).strip() if x else "",
            "phone_format": self._format_phone,
            "email_lower": lambda x: str(x).lower().strip() if x else "",
            "boolean": lambda x: bool(x) if x else False,
            "number": lambda x: float(x) if x else 0.0
        }
    
    def _format_phone(self, phone):
        """Format phone number"""
        if not phone:
            return ""
        # Remove non-digit characters
        cleaned = ''.join(filter(str.isdigit, str(phone)))
        return cleaned
    
    def apply_mapping(self, df: pd.DataFrame, mapping_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Apply column mapping and transformations to DataFrame
        """
        mapped_data = []
        
        for _, row in df.iterrows():
            mapped_row = {}
            
            for target_field, mapping in mapping_config["target_columns"].items():
                source_column = mapping.get("source_column")
                transformation = mapping.get("transformation")
                default_value = mapping.get("default_value")
                
                # Get value from source
                if source_column and source_column in df.columns:
                    value = row[source_column]
                else:
                    value = default_value
                
                # Apply transformation
                if transformation and transformation in self.transformations:
                    try:
                        value = self.transformations[transformation](value)
                    except Exception as e:
                        value = default_value
                
                # Handle required fields
                if mapping.get("required") and not value:
                    raise ValueError(f"Required field {target_field} is empty")
                
                mapped_row[target_field] = value
            
            mapped_data.append(mapped_row)
        
        return mapped_data
    
    def validate_mapping_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate mapping configuration
        """
        errors = []
        
        if not config.get("mapping_name"):
            errors.append("Mapping name is required")
        
        if not config.get("source_columns"):
            errors.append("Source columns configuration is required")
        
        if not config.get("target_columns"):
            errors.append("Target columns configuration is required")
        
        # Validate required target columns have source mappings
        for target_field, mapping in config.get("target_columns", {}).items():
            if mapping.get("required") and not mapping.get("source_column"):
                errors.append(f"Required field {target_field} must have a source column mapping")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }
