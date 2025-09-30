import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable, Union
import re
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import json
from enum import Enum

from .models import ERPNextEndpoint

logger = logging.getLogger(__name__)

class TransformationType(Enum):
    STRING = "string"
    NUMERIC = "numeric"
    DATE = "date"
    BOOLEAN = "boolean"
    CUSTOM = "custom"
    ERPNEXT = "erpnext"  # New type for ERPNext specific transformations

class ValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class MappingError(Exception):
    """Custom exception for mapping errors"""
    pass

class TransformationResult:
    """Result of a transformation operation"""
    
    def __init__(self, value: Any, success: bool = True, error: Optional[str] = None):
        self.value = value
        self.success = success
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "success": self.success,
            "error": self.error
        }

class MappingEngine:
    """Enhanced mapping engine with ERPNext specific transformations and validation"""
    
    def __init__(self):
        self.transformations = self._initialize_transformations()
        self.custom_transformations: Dict[str, Callable] = {}
        self.erpnext_transformations = self._initialize_erpnext_transformations()
        self.performance_stats = {
            "total_records_processed": 0,
            "total_transformations": 0,
            "transformation_errors": 0,
            "average_processing_time": 0.0
        }
    
    def _initialize_transformations(self) -> Dict[str, Dict[str, Any]]:
        """Initialize built-in transformation functions"""
        return {
            # String transformations
            "uppercase": {
                "function": lambda x: str(x).upper() if x is not None else "",
                "type": TransformationType.STRING,
                "description": "Convert text to uppercase"
            },
            "lowercase": {
                "function": lambda x: str(x).lower() if x is not None else "",
                "type": TransformationType.STRING,
                "description": "Convert text to lowercase"
            },
            "title_case": {
                "function": lambda x: str(x).title() if x is not None else "",
                "type": TransformationType.STRING,
                "description": "Convert text to title case"
            },
            "trim": {
                "function": lambda x: str(x).strip() if x is not None else "",
                "type": TransformationType.STRING,
                "description": "Remove leading and trailing whitespace"
            },
            "remove_extra_spaces": {
                "function": lambda x: re.sub(r'\s+', ' ', str(x).strip()) if x is not None else "",
                "type": TransformationType.STRING,
                "description": "Remove extra whitespace between words"
            },
            "remove_special_chars": {
                "function": self._remove_special_chars,
                "type": TransformationType.STRING,
                "description": "Remove special characters"
            },
            "keep_alphanumeric": {
                "function": lambda x: re.sub(r'[^a-zA-Z0-9\s]', '', str(x)) if x is not None else "",
                "type": TransformationType.STRING,
                "description": "Keep only alphanumeric characters and spaces"
            },
            "email_normalize": {
                "function": self._normalize_email,
                "type": TransformationType.STRING,
                "description": "Normalize email address format"
            },
            "phone_international": {
                "function": self._format_phone_international,
                "type": TransformationType.STRING,
                "description": "Format phone number to international format"
            },
            
            # Numeric transformations
            "to_float": {
                "function": self._to_float,
                "type": TransformationType.NUMERIC,
                "description": "Convert to floating point number"
            },
            "to_integer": {
                "function": self._to_integer,
                "type": TransformationType.NUMERIC,
                "description": "Convert to integer"
            },
            "to_decimal": {
                "function": self._to_decimal,
                "type": TransformationType.NUMERIC,
                "description": "Convert to decimal for precise arithmetic"
            },
            "round_decimal": {
                "function": self._round_decimal,
                "type": TransformationType.NUMERIC,
                "description": "Round to specified decimal places"
            },
            "currency_format": {
                "function": self._format_currency,
                "type": TransformationType.NUMERIC,
                "description": "Format as currency with two decimal places"
            },
            "percentage": {
                "function": self._to_percentage,
                "type": TransformationType.NUMERIC,
                "description": "Convert to percentage (multiply by 100)"
            },
            
            # Date transformations
            "date_iso": {
                "function": self._format_date_iso,
                "type": TransformationType.DATE,
                "description": "Parse and format date to ISO 8601"
            },
            "date_us": {
                "function": self._format_date_us,
                "type": TransformationType.DATE,
                "description": "Format date as MM/DD/YYYY"
            },
            "date_european": {
                "function": self._format_date_european,
                "type": TransformationType.DATE,
                "description": "Format date as DD/MM/YYYY"
            },
            "extract_year": {
                "function": self._extract_year,
                "type": TransformationType.NUMERIC,
                "description": "Extract year from date"
            },
            "extract_month": {
                "function": self._extract_month,
                "type": TransformationType.NUMERIC,
                "description": "Extract month from date"
            },
            "extract_day": {
                "function": self._extract_day,
                "type": TransformationType.NUMERIC,
                "description": "Extract day from date"
            },
            
            # Boolean transformations
            "to_boolean": {
                "function": self._to_boolean,
                "type": TransformationType.BOOLEAN,
                "description": "Convert to boolean (true/false)"
            },
            "yes_no_to_boolean": {
                "function": self._yes_no_to_boolean,
                "type": TransformationType.BOOLEAN,
                "description": "Convert 'yes'/'no' to boolean"
            },
            "one_zero_to_boolean": {
                "function": self._one_zero_to_boolean,
                "type": TransformationType.BOOLEAN,
                "description": "Convert 1/0 to boolean"
            },
            
            # Complex transformations
            "concat": {
                "function": self._concat_fields,
                "type": TransformationType.STRING,
                "description": "Concatenate multiple fields"
            },
            "conditional": {
                "function": self._conditional_transform,
                "type": TransformationType.CUSTOM,
                "description": "Apply conditional transformation"
            },
            "lookup": {
                "function": self._lookup_value,
                "type": TransformationType.CUSTOM,
                "description": "Lookup value from mapping table"
            },
            "default_if_empty": {
                "function": self._default_if_empty,
                "type": TransformationType.CUSTOM,
                "description": "Use default value if source is empty"
            }
        }
    
    def _initialize_erpnext_transformations(self) -> Dict[str, Dict[str, Any]]:
        """Initialize ERPNext specific transformation functions"""
        return {
            # ERPNext Customer transformations
            "erpnext_customer_code": {
                "function": self._format_erpnext_customer_code,
                "type": TransformationType.ERPNEXT,
                "description": "Format customer code for ERPNext"
            },
            "erpnext_customer_name": {
                "function": self._format_erpnext_customer_name,
                "type": TransformationType.ERPNEXT,
                "description": "Format customer name for ERPNext"
            },
            "erpnext_territory": {
                "function": self._format_erpnext_territory,
                "type": TransformationType.ERPNEXT,
                "description": "Format territory for ERPNext"
            },
            
            # ERPNext Item transformations
            "erpnext_item_code": {
                "function": self._format_erpnext_item_code,
                "type": TransformationType.ERPNEXT,
                "description": "Format item code for ERPNext"
            },
            "erpnext_item_name": {
                "function": self._format_erpnext_item_name,
                "type": TransformationType.ERPNEXT,
                "description": "Format item name for ERPNext"
            },
            "erpnext_item_group": {
                "function": self._format_erpnext_item_group,
                "type": TransformationType.ERPNEXT,
                "description": "Format item group for ERPNext"
            },
            
            # ERPNext Sales transformations
            "erpnext_quantity": {
                "function": self._format_erpnext_quantity,
                "type": TransformationType.ERPNEXT,
                "description": "Format quantity for ERPNext sales"
            },
            "erpnext_rate": {
                "function": self._format_erpnext_rate,
                "type": TransformationType.ERPNEXT,
                "description": "Format rate/price for ERPNext"
            },
            "erpnext_uom": {
                "function": self._format_erpnext_uom,
                "type": TransformationType.ERPNEXT,
                "description": "Format unit of measure for ERPNext"
            },
            
            # ERPNext General transformations
            "erpnext_company": {
                "function": self._format_erpnext_company,
                "type": TransformationType.ERPNEXT,
                "description": "Format company name for ERPNext"
            },
            "erpnext_warehouse": {
                "function": self._format_erpnext_warehouse,
                "type": TransformationType.ERPNEXT,
                "description": "Format warehouse for ERPNext"
            },
            "erpnext_payment_type": {
                "function": self._format_erpnext_payment_type,
                "type": TransformationType.ERPNEXT,
                "description": "Format payment type for ERPNext"
            }
        }
    
    # ERPNext Specific Transformation Methods
    def _format_erpnext_customer_code(self, value: Any) -> str:
        """Format customer code for ERPNext"""
        if not value:
            return ""
        
        code = str(value).strip().upper()
        # Remove special characters, keep alphanumeric and hyphens/underscores
        code = re.sub(r'[^a-zA-Z0-9_-]', '', code)
        return code
    
    def _format_erpnext_customer_name(self, value: Any) -> str:
        """Format customer name for ERPNext"""
        if not value:
            return ""
        
        name = str(value).strip()
        # Title case but preserve acronyms
        words = name.split()
        formatted_words = []
        for word in words:
            if word.isupper() or word.islower():
                formatted_words.append(word.title())
            else:
                formatted_words.append(word)
        return ' '.join(formatted_words)
    
    def _format_erpnext_territory(self, value: Any) -> str:
        """Format territory for ERPNext"""
        if not value:
            return "Myanmar"  # Default territory
        
        territory = str(value).strip().title()
        # Map common territory variations
        territory_map = {
            "burma": "Myanmar",
            "myanmar (burma)": "Myanmar",
            "mm": "Myanmar",
            "mmr": "Myanmar"
        }
        return territory_map.get(territory.lower(), territory)
    
    def _format_erpnext_item_code(self, value: Any) -> str:
        """Format item code for ERPNext"""
        if not value:
            return ""
        
        code = str(value).strip().upper()
        # Remove special characters, keep alphanumeric and hyphens
        code = re.sub(r'[^a-zA-Z0-9-]', '', code)
        return code
    
    def _format_erpnext_item_name(self, value: Any) -> str:
        """Format item name for ERPNext"""
        if not value:
            return ""
        
        name = str(value).strip()
        return name.title()
    
    def _format_erpnext_item_group(self, value: Any) -> str:
        """Format item group for ERPNext"""
        if not value:
            return "Products"  # Default item group
        
        group = str(value).strip().title()
        # Map common item groups
        group_map = {
            "product": "Products",
            "goods": "Products",
            "material": "Products",
            "service": "Services",
            "raw material": "Raw Materials"
        }
        return group_map.get(group.lower(), group)
    
    def _format_erpnext_quantity(self, value: Any) -> float:
        """Format quantity for ERPNext sales"""
        try:
            quantity = float(value)
            return max(0.0, quantity)  # Ensure non-negative
        except (ValueError, TypeError):
            return 1.0  # Default quantity
    
    def _format_erpnext_rate(self, value: Any) -> float:
        """Format rate/price for ERPNext"""
        try:
            rate = float(value)
            return max(0.0, round(rate, 2))  # Ensure non-negative, 2 decimal places
        except (ValueError, TypeError):
            return 0.0
    
    def _format_erpnext_uom(self, value: Any) -> str:
        """Format unit of measure for ERPNext"""
        if not value:
            return "Nos"  # Default UOM
        
        uom = str(value).strip().title()
        # Map common UOM variations
        uom_map = {
            "piece": "Nos",
            "pieces": "Nos",
            "unit": "Nos",
            "units": "Nos",
            "kilogram": "Kg",
            "kilograms": "Kg",
            "gram": "Gram",
            "grams": "Gram",
            "meter": "Meter",
            "meters": "Meter"
        }
        return uom_map.get(uom.lower(), uom)
    
    def _format_erpnext_company(self, value: Any) -> str:
        """Format company name for ERPNext"""
        if not value:
            return "Myanmar ShweTech"  # Default company
        
        return str(value).strip()
    
    def _format_erpnext_warehouse(self, value: Any) -> str:
        """Format warehouse for ERPNext"""
        if not value:
            return "Stores - MST"  # Default warehouse
        
        warehouse = str(value).strip()
        # Ensure proper warehouse format
        if " - MST" not in warehouse:
            warehouse = f"{warehouse} - MST"
        return warehouse
    
    def _format_erpnext_payment_type(self, value: Any) -> str:
        """Format payment type for ERPNext"""
        if not value:
            return "Receive"  # Default payment type
        
        payment_type = str(value).strip().title()
        # Map common payment types
        payment_map = {
            "payment": "Pay",
            "receipt": "Receive",
            "income": "Receive",
            "expense": "Pay",
            "in": "Receive",
            "out": "Pay"
        }
        return payment_map.get(payment_type.lower(), "Receive")
    
    # Existing transformation methods (unchanged but included for completeness)
    def _remove_special_chars(self, text: Any, allowed_chars: str = "") -> str:
        """Remove special characters with configurable allowed characters"""
        if text is None:
            return ""
        pattern = f'[^a-zA-Z0-9\\s{re.escape(allowed_chars)}]'
        return re.sub(pattern, '', str(text))
    
    def _normalize_email(self, email: Any) -> str:
        """Normalize email address"""
        if not email:
            return ""
        email_str = str(email).lower().strip()
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_str):
            return email_str
        return ""
    
    def _format_phone_international(self, phone: Any) -> str:
        """Format phone number to international format"""
        if not phone:
            return ""
        cleaned = re.sub(r'[^\d+]', '', str(phone))
        if cleaned.startswith('0'):
            cleaned = cleaned[1:]
        if not cleaned.startswith('+'):
            cleaned = '+1' + cleaned
        return cleaned
    
    def _to_float(self, value: Any) -> float:
        """Convert to float with error handling"""
        if value is None or value == "":
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _to_integer(self, value: Any) -> int:
        """Convert to integer with error handling"""
        if value is None or value == "":
            return 0
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    
    def _to_decimal(self, value: Any, precision: int = 2) -> Decimal:
        """Convert to Decimal with specified precision"""
        if value is None or value == "":
            return Decimal('0.00')
        try:
            return Decimal(str(value)).quantize(Decimal('1.' + '0' * precision))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal('0.00')
    
    def _round_decimal(self, value: Any, decimals: int = 2) -> float:
        """Round to specified decimal places"""
        try:
            return round(float(value), decimals)
        except (ValueError, TypeError):
            return 0.0
    
    def _format_currency(self, value: Any) -> str:
        """Format as currency string"""
        try:
            amount = float(value)
            return f"${amount:,.2f}"
        except (ValueError, TypeError):
            return "$0.00"
    
    def _to_percentage(self, value: Any) -> float:
        """Convert to percentage (multiply by 100)"""
        try:
            return float(value) * 100
        except (ValueError, TypeError):
            return 0.0
    
    def _format_date_iso(self, date_str: Any) -> str:
        """Parse and format date to ISO 8601"""
        if not date_str:
            return ""
        try:
            if isinstance(date_str, (datetime, date)):
                return date_str.isoformat()
            date_str = str(date_str).strip()
            date_formats = [
                '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d',
                '%m-%d-%Y', '%d-%m-%Y', '%Y.%m.%d', '%d.%m.%Y',
                '%b %d, %Y', '%B %d, %Y', '%d %b %Y', '%d %B %Y'
            ]
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.date().isoformat()
                except ValueError:
                    continue
            return date_str
        except Exception as e:
            logger.warning(f"Date parsing failed for '{date_str}': {e}")
           return str(date_str)
    
    def _format_date_us(self, date_str: Any) -> str:
        """Format date as MM/DD/YYYY"""
        iso_date = self._format_date_iso(date_str)
        if iso_date and len(iso_date) >= 10:
            try:
                date_obj = datetime.strptime(iso_date[:10], '%Y-%m-%d')
                return date_obj.strftime('%m/%d/%Y')
            except ValueError:
                pass
        return str(date_str)
    
    def _format_date_european(self, date_str: Any) -> str:
        """Format date as DD/MM/YYYY"""
        iso_date = self._format_date_iso(date_str)
        if iso_date and len(iso_date) >= 10:
            try:
                date_obj = datetime.strptime(iso_date[:10], '%Y-%m-%d')
                return date_obj.strftime('%d/%m/%Y')
            except ValueError:
                pass
        return str(date_str)
    
    def _extract_year(self, date_str: Any) -> int:
        """Extract year from date"""
        iso_date = self._format_date_iso(date_str)
        if iso_date and len(iso_date) >= 4:
            try:
                return int(iso_date[:4])
            except ValueError:
                pass
        return 0
    
    def _extract_month(self, date_str: Any) -> int:
        """Extract month from date"""
        iso_date = self._format_date_iso(date_str)
        if iso_date and len(iso_date) >= 7:
            try:
                return int(iso_date[5:7])
            except ValueError:
                pass
        return 0
    
    def _extract_day(self, date_str: Any) -> int:
        """Extract day from date"""
        iso_date = self._format_date_iso(date_str)
        if iso_date and len(iso_date) >= 10:
            try:
                return int(iso_date[8:10])
            except ValueError:
                pass
        return 0
    
    def _to_boolean(self, value: Any) -> bool:
        """Convert to boolean"""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        str_val = str(value).lower().strip()
        true_values = ['true', 'yes', 'y', '1', 'on', 't']
        return str_val in true_values
    
    def _yes_no_to_boolean(self, value: Any) -> bool:
        """Convert 'yes'/'no' to boolean"""
        if value is None:
            return False
        str_val = str(value).lower().strip()
        return str_val in ['yes', 'y', 'true']
    
    def _one_zero_to_boolean(self, value: Any) -> bool:
        """Convert 1/0 to boolean"""
        if value is None:
            return False
        try:
            return bool(int(value))
        except (ValueError, TypeError):
            return False
    
    def _concat_fields(self, row: pd.Series, fields: List[str], separator: str = " ") -> str:
        """Concatenate multiple fields with separator"""
        values = []
        for field in fields:
            value = row.get(field, "")
            if value is not None and str(value).strip():
                values.append(str(value).strip())
        return separator.join(values)
    
    def _conditional_transform(self, row: pd.Series, condition: Dict, transformations: Dict) -> Any:
        """Apply conditional transformation based on condition"""
        try:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")
            
            if field not in row:
                return transformations.get("else")
            
            field_value = row[field]
            
            condition_met = False
            if operator == "equals":
                condition_met = str(field_value) == str(value)
            elif operator == "not_equals":
                condition_met = str(field_value) != str(value)
            elif operator == "contains":
                condition_met = str(value) in str(field_value)
            elif operator == "greater_than":
                condition_met = float(field_value) > float(value)
            elif operator == "less_than":
                condition_met = float(field_value) < float(value)
            elif operator == "empty":
                condition_met = not field_value or str(field_value).strip() == ""
            elif operator == "not_empty":
                condition_met = bool(field_value) and str(field_value).strip() != ""
            
            return transformations.get("then") if condition_met else transformations.get("else")
            
        except Exception as e:
            logger.error(f"Conditional transformation failed: {e}")
            return transformations.get("else")
    
    def _lookup_value(self, value: Any, lookup_table: Dict, default: Any = None) -> Any:
        """Lookup value from mapping table"""
        if value is None:
            return default
        return lookup_table.get(str(value).strip(), default)
    
    def _default_if_empty(self, value: Any, default: Any) -> Any:
        """Use default value if source is empty"""
        if value is None or (isinstance(value, str) and not value.strip()):
            return default
        return value
    
    # Core Mapping Methods
    def _get_source_value(self, row: pd.Series, mapping: Dict, row_index: int) -> Any:
        """Get source value from row based on mapping configuration"""
        try:
            source_field = mapping.get("source_column")
            if not source_field:
                return None
            
            if source_field in row:
                return row[source_field]
            else:
                logger.warning(f"Source field '{source_field}' not found in row {row_index}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting source value for row {row_index}: {e}")
            return None
    
    def _apply_transformations(self, value: Any, mapping: Dict, row: pd.Series, row_index: int) -> Any:
        """Apply transformations to value"""
        try:
            transformations = mapping.get("transformations", [])
            current_value = value
            
            for transform_config in transformations:
                transform_name = transform_config.get("name")
                transform_params = transform_config.get("parameters", {})
                
                # Check ERPNext transformations first
                if transform_name in self.erpnext_transformations:
                    transform_func = self.erpnext_transformations[transform_name]["function"]
                elif transform_name in self.transformations:
                    transform_func = self.transformations[transform_name]["function"]
                elif transform_name in self.custom_transformations:
                    transform_func = self.custom_transformations[transform_name]["function"]
                else:
                    logger.warning(f"Unknown transformation: {transform_name}")
                    continue
                
                # Apply transformation
                try:
                    if transform_name in ["concat", "conditional"]:
                        # These transformations need the entire row
                        current_value = transform_func(row, **transform_params)
                    else:
                        current_value = transform_func(current_value, **transform_params)
                        
                    self.performance_stats["total_transformations"] += 1
                    
                except Exception as e:
                    logger.error(f"Transformation '{transform_name}' failed for row {row_index}: {e}")
                    self.performance_stats["transformation_errors"] += 1
            
            return current_value
            
        except Exception as e:
            logger.error(f"Error applying transformations for row {row_index}: {e}")
            return value
    
    def _validate_field(self, value: Any, field_name: str, validation_rules: Dict, row_index: int) -> Dict[str, Any]:
        """Validate field value against validation rules"""
        errors = []
        warnings = []
        severity = ValidationSeverity.INFO
        
        field_rules = validation_rules.get(field_name, {})
        
        # Required field validation
        if field_rules.get("required", False):
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Required field '{field_name}' is empty")
                severity = ValidationSeverity.ERROR
        
        # Data type validation
        expected_type = field_rules.get("data_type")
        if expected_type and value is not None:
            type_valid = self._validate_data_type(value, expected_type)
            if not type_valid:
                errors.append(f"Field '{field_name}' has invalid data type. Expected: {expected_type}")
                severity = ValidationSeverity.ERROR
        
        # Range validation for numeric fields
        if expected_type == "numeric" and value is not None:
            min_val = field_rules.get("min_value")
            max_val = field_rules.get("max_value")
            
            try:
                num_value = float(value)
                if min_val is not None and num_value < min_val:
                    errors.append(f"Field '{field_name}' value {num_value} is below minimum {min_val}")
                    severity = ValidationSeverity.ERROR
                if max_val is not None and num_value > max_val:
                    errors.append(f"Field '{field_name}' value {num_value} is above maximum {max_val}")
                    severity = ValidationSeverity.ERROR
            except (ValueError, TypeError):
                pass
        
        # Pattern validation for string fields
        pattern = field_rules.get("pattern")
        if pattern and value is not None and isinstance(value, str):
            if not re.match(pattern, value):
                errors.append(f"Field '{field_name}' does not match required pattern")
                severity = ValidationSeverity.ERROR
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "severity": severity
        }
    
    def _validate_data_type(self, value: Any, expected_type: str) -> bool:
        """Validate data type of value"""
        try:
            if expected_type == "string":
                return isinstance(value, str) or value is None
            elif expected_type == "numeric":
                return isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '').isdigit())
            elif expected_type == "date":
                if isinstance(value, (datetime, date)):
                    return True
                # Try to parse as date
                try:
                    pd.to_datetime(value)
                    return True
                except:
                    return False
            elif expected_type == "boolean":
                return isinstance(value, bool) or str(value).lower() in ['true', 'false', 'yes', 'no', '1', '0']
            return True
        except:
            return False
    
    # Public methods
    def register_custom_transformation(self, name: str, function: Callable, 
                                    transformation_type: TransformationType = TransformationType.CUSTOM):
        """Register custom transformation function"""
        self.custom_transformations[name] = {
            "function": function,
            "type": transformation_type,
            "description": "Custom transformation"
        }
        logger.info(f"Registered custom transformation: {name}")
    
    def get_available_transformations(self, endpoint: Optional[ERPNextEndpoint] = None) -> Dict[str, Any]:
        """Get available transformations, optionally filtered by ERPNext endpoint"""
        all_transformations = {**self.transformations, **self.erpnext_transformations, **self.custom_transformations}
        
        if endpoint:
            # Filter transformations relevant to the endpoint
            endpoint_specific = {}
            for name, config in all_transformations.items():
                if config.get("type") == TransformationType.ERPNEXT:
                    endpoint_specific[name] = config
                elif config.get("type") != TransformationType.ERPNEXT:
                    endpoint_specific[name] = config
            return endpoint_specific
        
        return all_transformations
    
    def apply_mapping(self, df: pd.DataFrame, mapping_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply column mapping and transformations to DataFrame with enhanced error handling
        
        Args:
            df: Input DataFrame
            mapping_config: Mapping configuration
            
        Returns:
            Dict containing mapped data and processing metadata
        """
        start_time = datetime.now()
        mapped_data = []
        processing_errors = []
        validation_errors = []
        
        target_columns = mapping_config.get("target_columns", {})
        validation_rules = mapping_config.get("validation_rules", {})
        erp_endpoint = mapping_config.get("erp_endpoint")
        
        try:
            for row_index, row in df.iterrows():
                row_errors = []
                mapped_row = {}
                row_valid = True
                
                for target_field, mapping in target_columns.items():
                    try:
                        # Get source value
                        source_value = self._get_source_value(row, mapping, row_index)
                        
                        # Apply transformations
                        transformed_value = self._apply_transformations(
                            source_value, mapping, row, row_index
                        )
                        
                        # Validate transformed value
                        validation_result = self._validate_field(
                            transformed_value, target_field, validation_rules, row_index
                        )
                        
                        if not validation_result["is_valid"]:
                            row_errors.extend(validation_result["errors"])
                            if validation_result["severity"] == ValidationSeverity.ERROR:
                                row_valid = False
                        
                        # Add to mapped row
                        mapped_row[target_field] = transformed_value
                        
                    except Exception as e:
                        error_msg = f"Error mapping field '{target_field}' in row {row_index}: {str(e)}"
                        row_errors.append(error_msg)
                        row_valid = False
                        logger.error(error_msg)
                
                # Add row to results if valid
                if row_valid:
                    mapped_data.append(mapped_row)
                else:
                    validation_errors.append({
                        "row_index": row_index,
                        "errors": row_errors,
                        "original_data": row.to_dict()
                    })
                
                self.performance_stats["total_records_processed"] += 1
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            self.performance_stats["average_processing_time"] = processing_time / len(df) if len(df) > 0 else 0
            
            # Prepare result
            result = {
                "mapped_data": mapped_data,
                "processing_metadata": {
                    "total_records_processed": len(df),
                    "successful_records": len(mapped_data),
                    "failed_records": len(validation_errors),
                    "success_rate": (len(mapped_data) / len(df)) * 100 if len(df) > 0 else 0,
                    "processing_time_seconds": processing_time,
                    "performance_stats": self.performance_stats.copy()
                },
                "validation_errors": validation_errors,
                "erp_endpoint": erp_endpoint
            }
            
            logger.info(f"Mapping completed: {len(mapped_data)}/{len(df)} records successful")
            return result
            
        except Exception as e:
            logger.error(f"Mapping process failed: {e}")
            raise MappingError(f"Mapping process failed: {str(e)}")

# Global mapping engine instance
mapping_engine = MappingEngine()
