import re
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum
from decimal import Decimal, InvalidOperation
import phonenumbers
from email_validator import validate_email, EmailNotValidError
import pandas as pd

logger = logging.getLogger(__name__)

class ValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ValidationResult:
    """Structured validation result"""
    
    def __init__(self):
        self.is_valid = True
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.info: List[Dict[str, Any]] = []
    
    def add_error(self, field: str, message: str, value: Any = None, rule: str = None):
        """Add validation error"""
        self.is_valid = False
        self.errors.append({
            "field": field,
            "message": message,
            "value": value,
            "rule": rule,
            "severity": ValidationSeverity.ERROR.value,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_warning(self, field: str, message: str, value: Any = None, rule: str = None):
        """Add validation warning"""
        self.warnings.append({
            "field": field,
            "message": message,
            "value": value,
            "rule": rule,
            "severity": ValidationSeverity.WARNING.value,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_info(self, field: str, message: str, value: Any = None):
        """Add validation info"""
        self.info.append({
            "field": field,
            "message": message,
            "value": value,
            "severity": ValidationSeverity.INFO.value,
            "timestamp": datetime.now().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "summary": {
                "total_errors": len(self.errors),
                "total_warnings": len(self.warnings),
                "total_info": len(self.info)
            }
        }
    
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result"""
        self.is_valid = self.is_valid and other.is_valid
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)

class ValidationRule:
    """Individual validation rule"""
    
    def __init__(self, name: str, validator: Callable, message: str, 
                 severity: ValidationSeverity = ValidationSeverity.ERROR):
        self.name = name
        self.validator = validator
        self.message = message
        self.severity = severity
    
    def validate(self, value: Any, field: str = None) -> Optional[Dict[str, Any]]:
        """Validate value against rule"""
        try:
            if not self.validator(value):
                return {
                    "field": field,
                    "message": self.message,
                    "value": value,
                    "rule": self.name,
                    "severity": self.severity.value
                }
        except Exception as e:
            return {
                "field": field,
                "message": f"Validation error: {str(e)}",
                "value": value,
                "rule": self.name,
                "severity": ValidationSeverity.ERROR.value
            }
        return None

class Validator:
    """Main validator class with rule registry"""
    
    def __init__(self):
        self.rules: Dict[str, ValidationRule] = {}
        self._initialize_builtin_rules()
    
    def _initialize_builtin_rules(self):
        """Initialize built-in validation rules"""
        # Required field rules
        self.register_rule("required", self._validate_required, 
                          "Field is required", ValidationSeverity.ERROR)
        
        # String rules
        self.register_rule("not_empty", self._validate_not_empty,
                          "Field cannot be empty", ValidationSeverity.ERROR)
        self.register_rule("min_length", self._validate_min_length,
                          "Field is too short", ValidationSeverity.ERROR)
        self.register_rule("max_length", self._validate_max_length,
                          "Field is too long", ValidationSeverity.ERROR)
        self.register_rule("exact_length", self._validate_exact_length,
                          "Field must be exact length", ValidationSeverity.ERROR)
        self.register_rule("regex", self._validate_regex,
                          "Field format is invalid", ValidationSeverity.ERROR)
        self.register_rule("alphanumeric", self._validate_alphanumeric,
                          "Field must contain only letters and numbers", ValidationSeverity.ERROR)
        
        # Numeric rules
        self.register_rule("numeric", self._validate_numeric,
                          "Field must be a number", ValidationSeverity.ERROR)
        self.register_rule("integer", self._validate_integer,
                          "Field must be an integer", ValidationSeverity.ERROR)
        self.register_rule("min_value", self._validate_min_value,
                          "Value is too small", ValidationSeverity.ERROR)
        self.register_rule("max_value", self._validate_max_value,
                          "Value is too large", ValidationSeverity.ERROR)
        self.register_rule("positive", self._validate_positive,
                          "Value must be positive", ValidationSeverity.ERROR)
        self.register_rule("negative", self._validate_negative,
                          "Value must be negative", ValidationSeverity.ERROR)
        
        # Date rules
        self.register_rule("date", self._validate_date,
                          "Field must be a valid date", ValidationSeverity.ERROR)
        self.register_rule("min_date", self._validate_min_date,
                          "Date is too early", ValidationSeverity.ERROR)
        self.register_rule("max_date", self._validate_max_date,
                          "Date is too late", ValidationSeverity.ERROR)
        
        # Email and phone rules
        self.register_rule("email", self._validate_email,
                          "Field must be a valid email address", ValidationSeverity.ERROR)
        self.register_rule("phone", self._validate_phone,
                          "Field must be a valid phone number", ValidationSeverity.ERROR)
        
        # Business logic rules
        self.register_rule("unique", self._validate_unique,
                          "Value must be unique", ValidationSeverity.ERROR)
        self.register_rule("in_list", self._validate_in_list,
                          "Value is not in allowed list", ValidationSeverity.ERROR)
        self.register_rule("not_in_list", self._validate_not_in_list,
                          "Value is in disallowed list", ValidationSeverity.ERROR)
    
    def register_rule(self, name: str, validator: Callable, message: str, 
                     severity: ValidationSeverity = ValidationSeverity.ERROR):
        """Register custom validation rule"""
        self.rules[name] = ValidationRule(name, validator, message, severity)
        logger.info(f"Registered validation rule: {name}")
    
    def validate_field(self, value: Any, field: str, rules: Dict[str, Any]) -> ValidationResult:
        """Validate a single field against multiple rules"""
        result = ValidationResult()
        
        for rule_name, rule_config in rules.items():
            if rule_name in self.rules:
                rule = self.rules[rule_name]
                
                # Handle parameterized rules
                if isinstance(rule_config, dict):
                    # Rules with parameters (e.g., min_length: 5)
                    for param_name, param_value in rule_config.items():
                        full_rule_name = f"{rule_name}_{param_name}"
                        custom_validator = self._create_parameterized_validator(
                            rule.validator, param_name, param_value
                        )
                        custom_rule = ValidationRule(
                            full_rule_name, custom_validator, rule.message, rule.severity
                        )
                        
                        error = custom_rule.validate(value, field)
                        if error:
                            if rule.severity == ValidationSeverity.ERROR:
                                result.add_error(field, error["message"], value, full_rule_name)
                            elif rule.severity == ValidationSeverity.WARNING:
                                result.add_warning(field, error["message"], value, full_rule_name)
                else:
                    # Simple rules without parameters
                    error = rule.validate(value, field)
                    if error:
                        if rule.severity == ValidationSeverity.ERROR:
                            result.add_error(field, error["message"], value, rule_name)
                        elif rule.severity == ValidationSeverity.WARNING:
                            result.add_warning(field, error["message"], value, rule_name)
        
        return result
    
    def validate_object(self, data: Dict[str, Any], validation_schema: Dict[str, Any]) -> ValidationResult:
        """Validate entire object against schema"""
        result = ValidationResult()
        
        for field, rules in validation_schema.items():
            value = data.get(field)
            field_result = self.validate_field(value, field, rules)
            result.merge(field_result)
        
        return result
    
    def validate_dataframe(self, df: pd.DataFrame, validation_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate pandas DataFrame against schema"""
        results = {
            "valid_rows": [],
            "invalid_rows": [],
            "validation_errors": [],
            "summary": {
                "total_rows": len(df),
                "valid_rows": 0,
                "invalid_rows": 0,
                "total_errors": 0
            }
        }
        
        for index, row in df.iterrows():
            row_data = row.to_dict()
            validation_result = self.validate_object(row_data, validation_schema)
            
            row_result = {
                "row_index": index,
                "data": row_data,
                "validation": validation_result.to_dict()
            }
            
            if validation_result.is_valid:
                results["valid_rows"].append(row_result)
            else:
                results["invalid_rows"].append(row_result)
                results["validation_errors"].extend(validation_result.errors)
        
        results["summary"]["valid_rows"] = len(results["valid_rows"])
        results["summary"]["invalid_rows"] = len(results["invalid_rows"])
        results["summary"]["total_errors"] = len(results["validation_errors"])
        
        return results
    
    def _create_parameterized_validator(self, base_validator: Callable, param_name: str, param_value: Any) -> Callable:
        """Create parameterized validator function"""
        def parameterized_validator(value: Any) -> bool:
            return base_validator(value, param_value)
        return parameterized_validator
    
    # Built-in validator methods
    def _validate_required(self, value: Any) -> bool:
        """Validate required field"""
        return value is not None and value != ""
    
    def _validate_not_empty(self, value: Any) -> bool:
        """Validate non-empty string"""
        if value is None:
            return False
        return str(value).strip() != ""
    
    def _validate_min_length(self, value: Any, min_length: int) -> bool:
        """Validate minimum length"""
        if value is None:
            return False
        return len(str(value)) >= min_length
    
    def _validate_max_length(self, value: Any, max_length: int) -> bool:
        """Validate maximum length"""
        if value is None:
            return True
        return len(str(value)) <= max_length
    
    def _validate_exact_length(self, value: Any, exact_length: int) -> bool:
        """Validate exact length"""
        if value is None:
            return False
        return len(str(value)) == exact_length
    
    def _validate_regex(self, value: Any, pattern: str) -> bool:
        """Validate against regex pattern"""
        if value is None:
            return True
        return bool(re.match(pattern, str(value)))
    
    def _validate_alphanumeric(self, value: Any) -> bool:
        """Validate alphanumeric characters only"""
        if value is None:
            return True
        return bool(re.match(r'^[a-zA-Z0-9]+$', str(value)))
    
    def _validate_numeric(self, value: Any) -> bool:
        """Validate numeric value"""
        if value is None:
            return True
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_integer(self, value: Any) -> bool:
        """Validate integer value"""
        if value is None:
            return True
        try:
            int(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_min_value(self, value: Any, min_val: float) -> bool:
        """Validate minimum value"""
        if value is None:
            return True
        try:
            return float(value) >= min_val
        except (ValueError, TypeError):
            return False
    
    def _validate_max_value(self, value: Any, max_val: float) -> bool:
        """Validate maximum value"""
        if value is None:
            return True
        try:
            return float(value) <= max_val
        except (ValueError, TypeError):
            return False
    
    def _validate_positive(self, value: Any) -> bool:
        """Validate positive number"""
        return self._validate_min_value(value, 0)
    
    def _validate_negative(self, value: Any) -> bool:
        """Validate negative number"""
        if value is None:
            return True
        try:
            return float(value) < 0
        except (ValueError, TypeError):
            return False
    
    def _validate_date(self, value: Any) -> bool:
        """Validate date format"""
        if value is None:
            return True
        
        if isinstance(value, (datetime, date)):
            return True
        
        try:
            # Try ISO format
            datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            return True
        except ValueError:
            pass
        
        # Try other common formats
        date_formats = [
            '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d',
            '%m-%d-%Y', '%d-%m-%Y', '%Y.%m.%d', '%d.%m.%Y',
            '%b %d, %Y', '%B %d, %Y'
        ]
        
        for fmt in date_formats:
            try:
                datetime.strptime(str(value), fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    def _validate_min_date(self, value: Any, min_date: str) -> bool:
        """Validate minimum date"""
        if value is None:
            return True
        
        try:
            if isinstance(value, (datetime, date)):
                value_date = value.date() if isinstance(value, datetime) else value
            else:
                value_date = datetime.strptime(str(value), '%Y-%m-%d').date()
            
            min_date_obj = datetime.strptime(min_date, '%Y-%m-%d').date()
            return value_date >= min_date_obj
        except (ValueError, TypeError):
            return False
    
    def _validate_max_date(self, value: Any, max_date: str) -> bool:
        """Validate maximum date"""
        if value is None:
            return True
        
        try:
            if isinstance(value, (datetime, date)):
                value_date = value.date() if isinstance(value, datetime) else value
            else:
                value_date = datetime.strptime(str(value), '%Y-%m-%d').date()
            
            max_date_obj = datetime.strptime(max_date, '%Y-%m-%d').date()
            return value_date <= max_date_obj
        except (ValueError, TypeError):
            return False
    
    def _validate_email(self, value: Any) -> bool:
        """Validate email format using email-validator library"""
        if value is None:
            return True
        
        try:
            validate_email(str(value))
            return True
        except EmailNotValidError:
            return False
    
    def _validate_phone(self, value: Any) -> bool:
        """Validate phone number using phonenumbers library"""
        if value is None:
            return True
        
        try:
            phone_number = phonenumbers.parse(str(value), None)
            return phonenumbers.is_valid_number(phone_number)
        except phonenumbers.NumberParseException:
            # Fallback to regex for basic validation
            pattern = r'^\+?[1-9]\d{1,14}$|^[0-9\s\-\+\(\)]{7,20}$'
            return bool(re.match(pattern, str(value)))
    
    def _validate_unique(self, value: Any, existing_values: List) -> bool:
        """Validate unique value"""
        if value is None:
            return True
        return value not in existing_values
    
    def _validate_in_list(self, value: Any, allowed_list: List) -> bool:
        """Validate value is in allowed list"""
        if value is None:
            return True
        return value in allowed_list
    
    def _validate_not_in_list(self, value: Any, disallowed_list: List) -> bool:
        """Validate value is not in disallowed list"""
        if value is None:
            return True
        return value not in disallowed_list

# Domain-specific validators
class CustomerValidator:
    """Customer data validator"""
    
    def __init__(self):
        self.validator = Validator()
        self.schema = {
            "customer_code": {
                "required": True,
                "min_length": {"value": 3},
                "max_length": {"value": 50},
                "alphanumeric": True
            },
            "customer_name": {
                "required": True,
                "min_length": {"value": 2},
                "max_length": {"value": 100}
            },
            "email_address": {
                "email": True,
                "max_length": {"value": 255}
            },
            "phone_number": {
                "phone": True,
                "max_length": {"value": 20}
            },
            "address_line": {
                "max_length": {"value": 200}
            },
            "city": {
                "max_length": {"value": 100}
            },
            "postal_code": {
                "max_length": {"value": 20}
            },
            "country": {
                "max_length": {"value": 50}
            }
        }
    
    def validate_customer(self, customer_data: Dict[str, Any]) -> ValidationResult:
        """Validate customer data"""
        return self.validator.validate_object(customer_data, self.schema)
    
    def validate_customers_batch(self, customers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate batch of customers"""
        results = {
            "valid_customers": [],
            "invalid_customers": [],
            "summary": {
                "total": len(customers),
                "valid": 0,
                "invalid": 0
            }
        }
        
        for customer in customers:
            validation_result = self.validate_customer(customer)
            customer_result = {
                "data": customer,
                "validation": validation_result.to_dict()
            }
            
            if validation_result.is_valid:
                results["valid_customers"].append(customer_result)
            else:
                results["invalid_customers"].append(customer_result)
        
        results["summary"]["valid"] = len(results["valid_customers"])
        results["summary"]["invalid"] = len(results["invalid_customers"])
        
        return results

class ProductValidator:
    """Product data validator"""
    
    def __init__(self):
        self.validator = Validator()
        self.schema = {
            "product_sku": {
                "required": True,
                "min_length": {"value": 3},
                "max_length": {"value": 50}
            },
            "product_name": {
                "required": True,
                "min_length": {"value": 2},
                "max_length": {"value": 200}
            },
            "description": {
                "max_length": {"value": 1000}
            },
            "unit_price": {
                "required": True,
                "numeric": True,
                "min_value": {"value": 0},
                "max_value": {"value": 999999.99}
            },
            "cost_price": {
                "numeric": True,
                "min_value": {"value": 0},
                "max_value": {"value": 999999.99}
            },
            "stock_quantity": {
                "integer": True,
                "min_value": {"value": 0},
                "max_value": {"value": 999999}
            },
            "category": {
                "max_length": {"value": 100}
            },
            "supplier_code": {
                "max_length": {"value": 50}
            }
        }
    
    def validate_product(self, product_data: Dict[str, Any]) -> ValidationResult:
        """Validate product data"""
        return self.validator.validate_object(product_data, self.schema)
    
    def validate_products_batch(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate batch of products"""
        results = {
            "valid_products": [],
            "invalid_products": [],
            "summary": {
                "total": len(products),
                "valid": 0,
                "invalid": 0
            }
        }
        
        for product in products:
            validation_result = self.validate_product(product)
            product_result = {
                "data": product,
                "validation": validation_result.to_dict()
            }
            
            if validation_result.is_valid:
                results["valid_products"].append(product_result)
            else:
                results["invalid_products"].append(product_result)
        
        results["summary"]["valid"] = len(results["valid_products"])
        results["summary"]["invalid"] = len(results["invalid_products"])
        
        return results

# Utility functions (backward compatibility)
def validate_customer_data(data: Dict[str, Any], rules: Dict[str, Any] = None) -> Dict[str, Any]:
    """Legacy customer data validation (for backward compatibility)"""
    validator = CustomerValidator()
    result = validator.validate_customer(data)
    return result.to_dict()

def validate_product_data(data: Dict[str, Any], rules: Dict[str, Any] = None) -> Dict[str, Any]:
    """Legacy product data validation (for backward compatibility)"""
    validator = ProductValidator()
    result = validator.validate_product(data)
    return result.to_dict()

def validate_business_rules(data: Dict[str, Any], mapping_rules: Dict[str, Any] = None) -> Dict[str, Any]:
    """Legacy business rules validation (for backward compatibility)"""
    validator = Validator()
    
    if mapping_rules and "validation_rules" in mapping_rules:
        result = validator.validate_object(data, mapping_rules["validation_rules"])
    else:
        result = ValidationResult()
        result.add_info("general", "No validation rules provided")
    
    return result.to_dict()

def validate_email_format(email: str) -> bool:
    """Validate email format"""
    validator = Validator()
    return validator._validate_email(email)

def validate_phone_format(phone: str) -> bool:
    """Validate phone number format"""
    validator = Validator()
    return validator._validate_phone(phone)

def validate_date_format(date_string: str) -> bool:
    """Validate date format"""
    validator = Validator()
    return validator._validate_date(date_string)

# Global validator instances
validator = Validator()
customer_validator = CustomerValidator()
product_validator = ProductValidator()
