import re
from typing import Dict, Any, List
from datetime import datetime

def validate_customer_data(data: Dict[str, Any], rules: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Validate customer data according to business rules
    
    Args:
        data: Customer data to validate
        rules: Additional validation rules
        
    Returns:
        Dict with validation results
    """
    errors = []
    warnings = []
    
    # Required field validation
    required_fields = rules.get("required_fields", []) if rules else []
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"Required field '{field}' is missing or empty")
    
    # Email validation
    if data.get("email"):
        email = data["email"]
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("Invalid email format")
    
    # Phone number validation
    if data.get("phone") or data.get("mobile_number"):
        phone = data.get("phone") or data.get("mobile_number")
        if phone and not re.match(r'^\+?[0-9\s\-\(\)]{7,15}$', str(phone)):
            warnings.append("Phone number format may be invalid")
    
    # Date validation
    if data.get("date_of_birth"):
        try:
            datetime.fromisoformat(data["date_of_birth"].replace('Z', '+00:00'))
        except ValueError:
            errors.append("Invalid date format for date_of_birth")
    
    # Numeric field validation
    numeric_fields = rules.get("numeric_fields", []) if rules else []
    for field in numeric_fields:
        if field in data and data[field]:
            try:
                float(data[field])
            except ValueError:
                errors.append(f"Field '{field}' must be a valid number")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "validated_data": data
    }

def validate_product_data(data: Dict[str, Any], rules: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Validate product data according to business rules
    """
    errors = []
    warnings = []
    
    # Required fields for products
    required_fields = ["product_code", "product_name"]
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"Required field '{field}' is missing or empty")
    
    # Price validation
    if data.get("price"):
        try:
            price = float(data["price"])
            if price < 0:
                errors.append("Price cannot be negative")
        except ValueError:
            errors.append("Price must be a valid number")
    
    # Stock validation
    if data.get("stock_quantity"):
        try:
            stock = int(data["stock_quantity"])
            if stock < 0:
                errors.append("Stock quantity cannot be negative")
        except ValueError:
            errors.append("Stock quantity must be a valid integer")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "validated_data": data
    }

def validate_business_rules(data: Dict[str, Any], mapping_rules: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generic business rule validation
    
    Args:
        data: Data to validate
        mapping_rules: Mapping-specific rules
        
    Returns:
        Dict with validation results
    """
    errors = []
    
    # Apply mapping-specific rules
    if mapping_rules:
        # Required fields from mapping
        required_fields = mapping_rules.get("required_fields", [])
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"Required field '{field}' is missing")
        
        # Field length validation
        field_lengths = mapping_rules.get("field_lengths", {})
        for field, max_length in field_lengths.items():
            if field in data and len(str(data[field])) > max_length:
                errors.append(f"Field '{field}' exceeds maximum length of {max_length} characters")
        
        # Value constraints
        value_constraints = mapping_rules.get("value_constraints", {})
        for field, constraints in value_constraints.items():
            if field in data:
                value = data[field]
                if "min" in constraints and value < constraints["min"]:
                    errors.append(f"Field '{field}' must be at least {constraints['min']}")
                if "max" in constraints and value > constraints["max"]:
                    errors.append(f"Field '{field}' must be at most {constraints['max']}")
                if "allowed_values" in constraints and value not in constraints["allowed_values"]:
                    errors.append(f"Field '{field}' has invalid value. Allowed: {constraints['allowed_values']}")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "validated_data": data
    }

def validate_email_format(email: str) -> bool:
    """Validate email format"""
    if not email or not email.strip():
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def validate_phone_format(phone: str) -> bool:
    """Validate phone number format"""
    if not phone or not phone.strip():
        return False
    
    pattern = r'^\+?[0-9\s\-\(\)]{7,15}$'
    return bool(re.match(pattern, phone.strip()))

def validate_date_format(date_string: str) -> bool:
    """Validate date format"""
    try:
        datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False
