import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable, Union
import re
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import json
from enum import Enum

logger = logging.getLogger(__name__)

class TransformationType(Enum):
    STRING = "string"
    NUMERIC = "numeric"
    DATE = "date"
    BOOLEAN = "boolean"
    CUSTOM = "custom"

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
    """Enhanced mapping engine with advanced transformations and validation"""
    
    def __init__(self):
        self.transformations = self._initialize_transformations()
        self.custom_transformations: Dict[str, Callable] = {}
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
    
    # String transformation methods
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
        # Basic email validation and normalization
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_str):
            return email_str
        return ""
    
    def _format_phone_international(self, phone: Any) -> str:
        """Format phone number to international format"""
        if not phone:
            return ""
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', str(phone))
        
        # If starts with 0, remove it (assuming local format)
        if cleaned.startswith('0'):
            cleaned = cleaned[1:]
        
        # Add country code if missing (default to +1 for US)
        if not cleaned.startswith('+'):
            cleaned = '+1' + cleaned
        
        return cleaned
    
    # Numeric transformation methods
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
    
    # Date transformation methods
    def _format_date_iso(self, date_str: Any) -> str:
        """Parse and format date to ISO 8601"""
        if not date_str:
            return ""
        
        try:
            # Handle pandas Timestamp and datetime objects
            if isinstance(date_str, (datetime, date)):
                return date_str.isoformat()
            
            # Handle string dates
            date_str = str(date_str).strip()
            
            # Try common date formats
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
            
            # If all formats fail, return original string
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
    
    # Boolean transformation methods
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
    
    # Complex transformation methods
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
            
            # Evaluate condition
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
        
        try:
            for row_index, row in df.iterrows():
                row_errors = []
                mapped_row = {}
                
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
                                # Skip this row if critical error
                           break
                        
                        mapped_row[target_field] = transformed_value
                        self.performance_stats["total_transformations"] += 1
                        
                    except MappingError as e:
                        row_errors.append({
                            "field": target_field,
                            "error": str(e),
                            "row_index": row_index,
                            "severity": ValidationSeverity.ERROR.value
                        })
                        break
                    except Exception as e:
                        row_errors.append({
                            "field": target_field,
                            "error": f"Unexpected error: {str(e)}",
                            "row_index": row_index,
                            "severity": ValidationSeverity.ERROR.value
                        })
                        self.performance_stats["transformation_errors"] += 1
                        break
                
                if not row_errors or all(error["severity"] != ValidationSeverity.ERROR.value for error in row_errors):
                    mapped_data.append(mapped_row)
                
                if row_errors:
                    processing_errors.extend(row_errors)
                
                self.performance_stats["total_records_processed"] += 1
            
            # Calculate performance metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            if self.performance_stats["total_records_processed"] > 0:
                self.performance_stats["average_processing_time"] = (
                    processing_time / self.performance_stats["total_records_processed"]
                )
            
            return {
                "mapped_data": mapped_data,
                "processing_errors": processing_errors,
                "validation_errors": validation_errors,
                "performance_metrics": self.performance_stats.copy(),
                "summary": {
                    "total_records": len(df),
                    "successful_records": len(mapped_data),
                    "failed_records": len(processing_errors),
                    "processing_time_seconds": processing_time
                }
            }
            
        except Exception as e:
            logger.error(f"Mapping engine failed: {e}")
            raise MappingError(f"Mapping processing failed: {str(e)}")
    
    def _get_source_value(self, row: pd.Series, mapping: Dict, row_index: int) -> Any:
        """Get source value from row with error handling"""
        source_column = mapping.get("source_column")
        default_value = mapping.get("default_value")
        is_required = mapping.get("required", False)
        
        if source_column and source_column in row:
            value = row[source_column]
            if pd.isna(value) or value is None:
                value = default_value
        else:
            value = default_value
        
        # Check required fields
        if is_required and (value is None or (isinstance(value, str) and not value.strip())):
            raise MappingError(f"Required field '{source_column}' is empty or missing")
        
        return value
    
    def _apply_transformations(self, value: Any, mapping: Dict, row: pd.Series, row_index: int) -> Any:
        """Apply transformations to value"""
        transformations = mapping.get("transformations", [])
        current_value = value
        
        for transform_config in transformations:
            try:
                transform_name = transform_config.get("name")
                transform_params = transform_config.get("parameters", {})
                
                # Check built-in transformations
                if transform_name in self.transformations:
                    transform_func = self.transformations[transform_name]["function"]
                    current_value = transform_func(current_value, **transform_params)
                
                # Check custom transformations
                elif transform_name in self.custom_transformations:
                    transform_func = self.custom_transformations[transform_name]["function"]
                    current_value = transform_func(current_value, **transform_params)
                
                # Handle complex transformations that need the entire row
                elif transform_name == "concat":
                    fields = transform_params.get("fields", [])
                    separator = transform_params.get("separator", " ")
                    current_value = self._concat_fields(row, fields, separator)
                
                elif transform_name == "conditional":
                    current_value = self._conditional_transform(row, 
                        transform_params.get("condition", {}),
                        transform_params.get("transformations", {})
                    )
                
                elif transform_name == "lookup":
                    lookup_table = transform_params.get("lookup_table", {})
                    default = transform_params.get("default")
                    current_value = self._lookup_value(current_value, lookup_table, default)
                
                else:
                    logger.warning(f"Unknown transformation: {transform_name}")
                
            except Exception as e:
                logger.warning(f"Transformation '{transform_name}' failed for row {row_index}: {e}")
                # Continue with current value if transformation fails
                continue
        
        return current_value
    
    def _validate_field(self, value: Any, field_name: str, validation_rules: Dict, row_index: int) -> Dict[str, Any]:
        """Validate field value against validation rules"""
        field_rules = validation_rules.get(field_name, {})
        errors = []
        is_valid = True
        
        for rule_name, rule_config in field_rules.items():
            try:
                if rule_name == "required" and rule_config and (value is None or not str(value).strip()):
                    errors.append({
                        "rule": rule_name,
                        "message": f"Field '{field_name}' is required",
                        "severity": ValidationSeverity.ERROR.value
                    })
                    is_valid = False
                
                elif rule_name == "min_length" and value is not None:
                    min_len = rule_config
                    if len(str(value)) < min_len:
                        errors.append({
                            "rule": rule_name,
                            "message": f"Field '{field_name}' must be at least {min_len} characters",
                            "severity": ValidationSeverity.ERROR.value
                        })
                        is_valid = False
                
                elif rule_name == "max_length" and value is not None:
                    max_len = rule_config
                    if len(str(value)) > max_len:
                        errors.append({
                            "rule": rule_name,
                            "message": f"Field '{field_name}' must be at most {max_len} characters",
                            "severity": ValidationSeverity.ERROR.value
                        })
                        is_valid = False
                
                elif rule_name == "pattern" and value is not None:
                    pattern = rule_config
                    if not re.match(pattern, str(value)):
                        errors.append({
                            "rule": rule_name,
                            "message": f"Field '{field_name}' does not match required pattern",
                            "severity": ValidationSeverity.ERROR.value
                        })
                        is_valid = False
                
                elif rule_name == "min_value" and value is not None:
                    try:
                        min_val = float(rule_config)
                        if float(value) < min_val:
                            errors.append({
                                "rule": rule_name,
                                "message": f"Field '{field_name}' must be at least {min_val}",
                                "severity": ValidationSeverity.ERROR.value
                            })
                            is_valid = False
                    except (ValueError, TypeError):
                        pass
                
                elif rule_name == "max_value" and value is not None:
                    try:
                        max_val = float(rule_config)
                        if float(value) > max_val:
                            errors.append({
                                "rule": rule_name,
                                "message": f"Field '{field_name}' must be at most {max_val}",
                                "severity": ValidationSeverity.ERROR.value
                            })
                            is_valid = False
                    except (ValueError, TypeError):
                        pass
                
                elif rule_name == "data_type" and value is not None:
                    expected_type = rule_config
                    if expected_type == "email" and not re.match(r'^[^@]+@[^@]+\.[^@]+$', str(value)):
                        errors.append({
                            "rule": rule_name,
                            "message": f"Field '{field_name}' must be a valid email address",
                            "severity": ValidationSeverity.ERROR.value
                        })
                        is_valid = False
                    
                    elif expected_type == "phone" and not re.match(r'^[\d\s\-\+\(\)]+$', str(value)):
                        errors.append({
                            "rule": rule_name,
                            "message": f"Field '{field_name}' must be a valid phone number",
                            "severity": ValidationSeverity.WARNING.value
                        })
            except Exception as e:
                logger.warning(f"Validation rule '{rule_name}' failed: {e}")
        
        return {
            "is_valid": is_valid,
            "errors": errors,
            "severity": ValidationSeverity.ERROR if any(e["severity"] == ValidationSeverity.ERROR.value for e in errors) else ValidationSeverity.WARNING
        }
    
    def validate_mapping_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive mapping configuration validation
        
        Args:
            config: Mapping configuration to validate
            
        Returns:
            Dict with validation results
        """
        errors = []
        warnings = []
        
        # Basic structure validation
        required_fields = ["mapping_name", "source_columns", "target_columns"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Validate source columns
        source_columns = config.get("source_columns", [])
        for i, col in enumerate(source_columns):
            if not col.get("name"):
                errors.append(f"Source column {i + 1} must have a name")
            
            # Validate data types
            if col.get("data_type") and col["data_type"] not in ["string", "number", "date", "boolean"]:
                warnings.append(f"Source column '{col.get('name')}' has unknown data type: {col.get('data_type')}")
        
        # Validate target columns
        target_columns = config.get("target_columns", {})
        for target_field, mapping in target_columns.items():
            if not target_field:
                errors.append("Target field name cannot be empty")
            
            # Validate transformations
            transformations = mapping.get("transformations", [])
            for transform in transformations:
                transform_name = transform.get("name")
                if (transform_name not in self.transformations and 
                    transform_name not in self.custom_transformations and
                    transform_name not in ["concat", "conditional", "lookup"]):
                    warnings.append(f"Unknown transformation '{transform_name}' for field '{target_field}'")
        
        # Validate ERP endpoint
        erp_endpoint = config.get("erp_endpoint")
        valid_endpoints = ["customers", "products", "sales", "inventory", "orders", "suppliers"]
        if erp_endpoint and erp_endpoint not in valid_endpoints:
            warnings.append(f"ERP endpoint '{erp_endpoint}' may not be supported")
        
        # Validate validation rules
        validation_rules = config.get("validation_rules", {})
        for field_name, rules in validation_rules.items():
            if field_name not in target_columns:
                warnings.append(f"Validation rules defined for unknown field: {field_name}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "total_errors": len(errors),
                "total_warnings": len(warnings),
                "source_columns_count": len(source_columns),
                "target_columns_count": len(target_columns)
            }
        }
    
    def get_available_transformations(self) -> Dict[str, Any]:
        """Get list of available transformations"""
        transformations_info = {}
        
        for name, info in self.transformations.items():
            transformations_info[name] = {
                "type": info["type"].value,
                "description": info["description"],
                "category": info["type"].value.capitalize()
            }
        
        for name, info in self.custom_transformations.items():
            transformations_info[name] = {
                "type": info["type"].value,
                "description": info["description"],
                "category": "Custom"
            }
        
        # Add complex transformations
        complex_transforms = {
            "concat": {
                "type": "string",
                "description": "Concatenate multiple fields",
                "category": "Complex"
            },
            "conditional": {
                "type": "custom",
                "description": "Apply conditional transformation",
                "category": "Complex"
            },
            "lookup": {
                "type": "custom",
                "description": "Lookup value from mapping table",
                "category": "Complex"
            }
        }
        
        transformations_info.update(complex_transforms)
        return transformations_info
    
    def generate_sample_mapping(self, data_type: str = "customers") -> Dict[str, Any]:
        """
        Generate comprehensive sample mapping configuration
        
        Args:
            data_type: Type of data (customers, products, sales, etc.)
            
        Returns:
            Sample mapping configuration
        """
        base_config = {
            "mapping_name": f"{data_type.title()} Import Mapping",
            "description": f"Sample mapping configuration for {data_type} data import",
            "erp_endpoint": data_type,
            "validation_rules": {},
            "processing_options": {
                "skip_empty_rows": True,
                "stop_on_critical_error": False,
                "batch_size": 100
            }
        }
        
        samples = {
            "customers": {
                **base_config,
                "source_columns": [
                    {"name": "Customer_ID", "data_type": "string", "required": True},
                    {"name": "Full_Name", "data_type": "string", "required": True},
                    {"name": "Email", "data_type": "string", "required": False},
                    {"name": "Phone", "data_type": "string", "required": False},
                    {"name": "Address", "data_type": "string", "required": False},
                    {"name": "City", "data_type": "string", "required": False},
                    {"name": "Country", "data_type": "string", "required": False},
                    {"name": "Status", "data_type": "string", "required": False}
                ],
                "target_columns": {
                    "customer_code": {
                        "source_column": "Customer_ID",
                        "transformations": [
                            {"name": "uppercase"},
                            {"name": "trim"}
                        ],
                        "required": True,
                        "default_value": ""
                    },
                    "customer_name": {
                        "source_column": "Full_Name",
                        "transformations": [
                            {"name": "title_case"},
                            {"name": "remove_extra_spaces"}
                        ],
                        "required": True
                    },
                    "email_address": {
                        "source_column": "Email",
                        "transformations": [
                            {"name": "email_normalize"},
                            {"name": "lowercase"}
                        ],
                        "required": False
                    },
                    "phone_number": {
                        "source_column": "Phone",
                        "transformations": [
                            {"name": "phone_international"}
                        ],
                        "required": False
                    },
                    "address_line": {
                        "source_column": "Address",
                        "transformations": [
                            {"name": "trim"},
                            {"name": "remove_extra_spaces"}
                        ],
                        "required": False
                    }
                },
                "validation_rules": {
                    "email_address": {
                        "data_type": "email",
                        "required": False
                    },
                    "customer_code": {
                        "required": True,
                        "min_length": 3
                    }
                }
            },
            "products": {
                **base_config,
                "source_columns": [
                    {"name": "Product_Code", "data_type": "string", "required": True},
                    {"name": "Product_Name", "data_type": "string", "required": True},
                    {"name": "Description", "data_type": "string", "required": False},
                    {"name": "Price", "data_type": "number", "required": True},
                    {"name": "Cost", "data_type": "number", "required": False},
                    {"name": "Stock_Qty", "data_type": "number", "required": False},
                    {"name": "Category", "data_type": "string", "required": False}
                ],
                "target_columns": {
                    "product_sku": {
                        "source_column": "Product_Code",
                        "transformations": [
                            {"name": "uppercase"},
                            {"name": "trim"}
                        ],
                        "required": True
                    },
                    "product_name": {
                        "source_column": "Product_Name",
                        "transformations": [
                            {"name": "trim"},
                            {"name": "remove_extra_spaces"}
                        ],
                        "required": True
                    },
                    "description": {
                        "source_column": "Description",
                        "transformations": [
                            {"name": "trim"},
                            {"name": "remove_extra_spaces"}
                        ],
                        "required": False
                    },
                    "unit_price": {
                        "source_column": "Price",
                        "transformations": [
                            {"name": "to_decimal", "parameters": {"precision": 2}}
                        ],
                        "required": True
                    },
                    "cost_price": {
                        "source_column": "Cost",
                        "transformations": [
                            {"name": "to_decimal", "parameters": {"precision": 2}}
                        ],
                        "required": False,
                        "default_value": 0.0
                    },
                    "stock_quantity": {
                        "source_column": "Stock_Qty",
                        "transformations": [
                            {"name": "to_integer"}
                        ],
                        "required": False,
                        "default_value": 0
                    }
                },
                "validation_rules": {
                    "unit_price": {
                        "required": True,
                        "min_value": 0
                    },
                    "stock_quantity": {
                        "min_value": 0
                    }
                }
            }
        }
        
        return samples.get(data_type, samples["customers"])
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return self.performance_stats.copy()
    
    def reset_performance_stats(self):
        """Reset performance statistics"""
        self.performance_stats = {
            "total_records_processed": 0,
            "total_transformations": 0,
            "transformation_errors": 0,
            "average_processing_time": 0.0
        }

# Global mapping engine instance
mapping_engine = MappingEngine()
