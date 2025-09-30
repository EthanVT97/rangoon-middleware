import pandas as pd
import io
import base64
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import logging
import chardet
from enum import Enum
import re

from .models import ERPNextEndpoint, ERPNextCustomerCreate, ERPNextItemCreate, ERPNextSalesOrderCreate, ERPNextSalesInvoiceCreate

logger = logging.getLogger(__name__)

class FileType(Enum):
    EXCEL = "excel"
    CSV = "csv"
    UNSUPPORTED = "unsupported"

class DataValidationError(Exception):
    """Custom exception for data validation errors"""
    pass

class ERPNextDataMapper:
    """ERPNext specific data mapping and transformation"""
    
    @staticmethod
    def map_to_erpnext_customer(row: Dict, mapping_config: Dict) -> Dict:
        """Map row data to ERPNext customer format"""
        customer_data = {}
        
        for target_field, source_config in mapping_config.get('target_columns', {}).items():
            source_field = source_config.get('source_column')
            transformation = source_config.get('transformation')
            
            if source_field in row and pd.notna(row[source_field]):
                value = row[source_field]
                
                # Apply transformations
                value = ERPNextDataMapper.apply_transformation(value, transformation)
                
                customer_data[target_field] = value
        
        # Set default values for required fields if not provided
        customer_data.setdefault('customer_group', 'Individual')
        customer_data.setdefault('territory', 'Myanmar')
        
        return customer_data
    
    @staticmethod
    def map_to_erpnext_item(row: Dict, mapping_config: Dict) -> Dict:
        """Map row data to ERPNext item format"""
        item_data = {}
        
        for target_field, source_config in mapping_config.get('target_columns', {}).items():
            source_field = source_config.get('source_column')
            transformation = source_config.get('transformation')
            
            if source_field in row and pd.notna(row[source_field]):
                value = row[source_field]
                
                # Apply transformations
                value = ERPNextDataMapper.apply_transformation(value, transformation)
                
                item_data[target_field] = value
        
        # Set default values for required fields if not provided
        item_data.setdefault('item_group', 'Products')
        item_data.setdefault('stock_uom', 'Nos')
        
        return item_data
    
    @staticmethod
    def map_to_erpnext_sales_order(row: Dict, mapping_config: Dict) -> Dict:
        """Map row data to ERPNext sales order format"""
        order_data = {
            "items": []
        }
        
        # Map main order fields
        for target_field, source_config in mapping_config.get('target_columns', {}).items():
            if target_field != 'items':  # Handle items separately
                source_field = source_config.get('source_column')
                transformation = source_config.get('transformation')
                
                if source_field in row and pd.notna(row[source_field]):
                    value = row[source_field]
                    value = ERPNextDataMapper.apply_transformation(value, transformation)
                    order_data[target_field] = value
        
        # Map item data
        item_mapping = mapping_config.get('item_mapping', {})
        if item_mapping:
            item_data = {}
            for target_field, source_config in item_mapping.items():
                source_field = source_config.get('source_column')
                transformation = source_config.get('transformation')
                
                if source_field in row and pd.notna(row[source_field]):
                    value = row[source_field]
                    value = ERPNextDataMapper.apply_transformation(value, transformation)
                    item_data[target_field] = value
            
            if item_data:
                order_data["items"].append(item_data)
        
        # Set default values
        order_data.setdefault('company', 'Myanmar ShweTech')
        
        return order_data
    
    @staticmethod
    def apply_transformation(value: Any, transformation: Optional[str]) -> Any:
        """Apply data transformation"""
        if transformation == 'uppercase' and isinstance(value, str):
            return value.upper()
        elif transformation == 'lowercase' and isinstance(value, str):
            return value.lower()
        elif transformation == 'trim' and isinstance(value, str):
            return value.strip()
        elif transformation == 'numeric' and isinstance(value, str):
            # Extract numbers from string
            numbers = re.findall(r'\d+\.?\d*', value)
            return float(numbers[0]) if numbers else 0
        elif transformation == 'date':
            # Convert to YYYY-MM-DD format
            try:
                if isinstance(value, str):
                    return pd.to_datetime(value).strftime('%Y-%m-%d')
                elif isinstance(value, datetime):
                    return value.strftime('%Y-%m-%d')
            except:
                return value
        return value
    
    @staticmethod
    def get_required_fields(endpoint: ERPNextEndpoint) -> List[str]:
        """Get required fields for ERPNext endpoint"""
        required_fields = {
            ERPNextEndpoint.CUSTOMERS: ["customer_name", "customer_group"],
            ERPNextEndpoint.ITEMS: ["item_code", "item_name"],
            ERPNextEndpoint.SALES_ORDERS: ["customer", "items"],
            ERPNextEndpoint.SALES_INVOICES: ["customer", "items"],
            ERPNextEndpoint.PAYMENTS: ["payment_type", "party", "paid_amount"]
        }
        return required_fields.get(endpoint, [])
    
    @staticmethod
    def validate_erpnext_data(data: Dict, endpoint: ERPNextEndpoint) -> List[str]:
        """Validate data for ERPNext endpoint requirements"""
        errors = []
        required_fields = ERPNextDataMapper.get_required_fields(endpoint)
        
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                errors.append(f"Missing required field: {field}")
            
            # Special validation for items in sales orders and invoices
            if field == 'items' and endpoint in [ERPNextEndpoint.SALES_ORDERS, ERPNextEndpoint.SALES_INVOICES]:
                if not data.get('items') or len(data['items']) == 0:
                    errors.append("Sales order/invoice must contain at least one item")
                else:
                    for item in data['items']:
                        if not item.get('item_code'):
                            errors.append("Item must have item_code")
                        if not item.get('qty') or item['qty'] <= 0:
                            errors.append("Item must have valid quantity")
        
        return errors

class FileProcessor:
    """Enhanced file processor with ERPNext integration support"""
    
    def __init__(self):
        self.supported_formats = {'.xlsx', '.xls', '.csv'}
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.default_encoding = 'utf-8'
        self.erpnext_mapper = ERPNextDataMapper()
    
    def process_uploaded_file(self, file_content: str, filename: str, mapping_config: Optional[Dict] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Process uploaded file with comprehensive validation
        
        Args:
            file_content: Base64 encoded file content
            filename: Original filename
            mapping_config: Optional mapping configuration for validation
            
        Returns:
            Tuple of (DataFrame, metadata_dict)
        """
        try:
            # Validate file extension
            if not self.validate_file_extension(filename):
                raise DataValidationError(f"Unsupported file format. Supported: {', '.join(self.supported_formats)}")
            
            # Decode base64 content
            file_bytes = self.decode_base64_file(file_content)
            
            # Validate file size
            self.validate_file_size(file_bytes, filename)
            
            # Detect file type and process
            file_type = self.detect_file_type(filename)
            
            if file_type == FileType.EXCEL:
                df = self.process_excel_file(file_bytes)
            elif file_type == FileType.CSV:
                df = self.process_csv_file(file_bytes)
            else:
                raise DataValidationError("Unsupported file type")
            
            # Basic data cleaning
            df = self.clean_dataframe(df)
            
            # Apply mapping validation if provided
            if mapping_config:
                validation_result = self.validate_with_mapping(df, mapping_config)
                if not validation_result["is_valid"]:
                    raise DataValidationError(f"Data validation failed: {validation_result['errors']}")
            
            # Generate comprehensive metadata
            metadata = self.get_file_metadata(df, filename, file_bytes)
            
            logger.info(f"Successfully processed file: {filename} with {len(df)} records")
            
            return df, metadata
            
        except Exception as e:
            logger.error(f"File processing failed for {filename}: {str(e)}")
            raise
    
    def process_excel_file(self, file_content: bytes) -> pd.DataFrame:
        """
        Process Excel file with enhanced error handling
        """
        try:
            # Try reading with different engines
            try:
                df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
            except Exception:
                try:
                    df = pd.read_excel(io.BytesIO(file_content), engine='xlrd')
                except Exception as e:
                    raise DataValidationError(f"Cannot read Excel file with any available engine: {str(e)}")
            
            # Validate DataFrame
            self.validate_dataframe(df, "Excel")
            
            return df
            
        except pd.errors.EmptyDataError:
            raise DataValidationError("Excel file is empty")
        except pd.errors.ParserError as e:
            raise DataValidationError(f"Excel file parsing error: {str(e)}")
        except Exception as e:
            raise DataValidationError(f"Error processing Excel file: {str(e)}")
    
    def process_csv_file(self, file_content: bytes) -> pd.DataFrame:
        """
        Process CSV file with encoding detection and enhanced handling
        """
        try:
            # Detect encoding
            encoding = self.detect_encoding(file_content)
            
            # Read CSV with detected encoding
            try:
                df = pd.read_csv(
                    io.BytesIO(file_content), 
                    encoding=encoding,
                    on_bad_lines='skip',  # Skip problematic lines
                    skip_blank_lines=True
                )
            except Exception:
                # Fallback to utf-8
                df = pd.read_csv(
                    io.BytesIO(file_content), 
                    encoding='utf-8',
                    on_bad_lines='skip',
                    skip_blank_lines=True
                )
            
            # Validate DataFrame
            self.validate_dataframe(df, "CSV")
            
            return df
            
        except pd.errors.EmptyDataError:
            raise DataValidationError("CSV file is empty")
        except pd.errors.ParserError as e:
            raise DataValidationError(f"CSV file parsing error: {str(e)}")
        except Exception as e:
            raise DataValidationError(f"Error processing CSV file: {str(e)}")
    
    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize DataFrame
        """
        # Create a copy to avoid modifying original
        df_clean = df.copy()
        
        # Clean column names
        df_clean.columns = [self.clean_column_name(col) for col in df_clean.columns]
        
        # Remove completely empty rows and columns
        df_clean = df_clean.dropna(how='all')
        df_clean = df_clean.loc[:, ~df_clean.columns.str.contains('^Unnamed')]
        
        # Fill NaN values appropriately
        for col in df_clean.columns:
            if df_clean[col].dtype in ['object', 'string']:
                df_clean[col] = df_clean[col].fillna('')
            else:
                df_clean[col] = df_clean[col].fillna(0)
        
        # Remove duplicate rows
        initial_count = len(df_clean)
        df_clean = df_clean.drop_duplicates()
        duplicates_removed = initial_count - len(df_clean)
        
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate rows")
        
        return df_clean
    
    def clean_column_name(self, column_name: Any) -> str:
        """
        Clean and standardize column names
        """
        if pd.isna(column_name):
            return "unknown_column"
        
        name = str(column_name).strip().lower()
        name = ''.join(c if c.isalnum() or c in ['_', ' '] else '_' for c in name)
        name = '_'.join(name.split())
        
        return name if name else "unknown_column"
    
    def validate_dataframe(self, df: pd.DataFrame, file_type: str):
        """
        Basic DataFrame validation
        """
        if df.empty:
            raise DataValidationError(f"{file_type} file contains no data")
        
        if len(df.columns) == 0:
            raise DataValidationError(f"{file_type} file has no columns")
        
        # Check for reasonable row count (prevent extremely large files)
        if len(df) > 100000:  # 100K records max
            raise DataValidationError(f"File too large: {len(df)} records. Maximum allowed: 100,000")
    
    def validate_with_mapping(self, df: pd.DataFrame, mapping_config: Dict) -> Dict[str, Any]:
        """
        Validate DataFrame against mapping configuration with ERPNext specific validation
        """
        errors = []
        warnings = []
        
        source_columns = mapping_config.get('source_columns', [])
        required_columns = [col['name'] for col in source_columns if col.get('required', False)]
        
        # Check required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        
        # Validate data types if specified in mapping
        for col_config in source_columns:
            col_name = col_config.get('name')
            expected_type = col_config.get('data_type')
            
            if col_name in df.columns and expected_type:
                type_errors = self.validate_column_data_type(df[col_name], expected_type, col_name)
                errors.extend(type_errors)
        
        # Check for empty required columns
        for col in required_columns:
            if col in df.columns and df[col].isna().all():
                warnings.append(f"Required column '{col}' is completely empty")
        
        # ERPNext specific validation if endpoint is specified
        erp_endpoint = mapping_config.get('erp_endpoint')
        if erp_endpoint:
            erp_errors = self.validate_erpnext_requirements(df, erp_endpoint, mapping_config)
            errors.extend(erp_errors)
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "columns_found": list(df.columns),
            "columns_required": required_columns,
            "erp_endpoint": erp_endpoint
        }
    
    def validate_erpnext_requirements(self, df: pd.DataFrame, endpoint: str, mapping_config: Dict) -> List[str]:
        """Validate data against ERPNext endpoint requirements"""
        errors = []
        
        try:
            erp_endpoint = ERPNextEndpoint(endpoint)
            required_fields = self.erpnext_mapper.get_required_fields(erp_endpoint)
            
            # Check if mapped fields cover required fields
            target_mapping = mapping_config.get('target_columns', {})
            mapped_fields = set(target_mapping.keys())
            
            missing_required = set(required_fields) - mapped_fields
            if missing_required:
                errors.append(f"ERPNext {endpoint} requires mapping for: {', '.join(missing_required)}")
            
            # Validate sample data conversion
            if len(df) > 0:
                sample_data = self.convert_to_erpnext_format(df.head(1), mapping_config, erp_endpoint)
                if sample_data:
                    sample_errors = self.erpnext_mapper.validate_erpnext_data(sample_data[0], erp_endpoint)
                    errors.extend(sample_errors)
            
        except ValueError:
            errors.append(f"Invalid ERPNext endpoint: {endpoint}")
        
        return errors
    
    def validate_column_data_type(self, series: pd.Series, expected_type: str, column_name: str) -> List[str]:
        """
        Validate column data type
        """
        errors = []
        
        if expected_type == 'numeric':
            non_numeric = pd.to_numeric(series, errors='coerce').isna() & (series != '')
            if non_numeric.any():
                invalid_count = non_numeric.sum()
                errors.append(f"Column '{column_name}' has {invalid_count} non-numeric values")
        
        elif expected_type == 'date':
            # Try to parse as date
            try:
                pd.to_datetime(series, errors='coerce')
                invalid_dates = pd.to_datetime(series, errors='coerce').isna() & (series != '')
                if invalid_dates.any():
                    invalid_count = invalid_dates.sum()
                    errors.append(f"Column '{column_name}' has {invalid_count} invalid date values")
            except:
                errors.append(f"Column '{column_name}' contains invalid date values")
        
        elif expected_type == 'email':
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            invalid_emails = ~series.astype(str).str.match(email_pattern, na=False)
            if invalid_emails.any():
                invalid_count = invalid_emails.sum()
                errors.append(f"Column '{column_name}' has {invalid_count} invalid email addresses")
        
        return errors
    
    def detect_encoding(self, file_content: bytes) -> str:
        """
        Detect file encoding for CSV files
        """
        try:
            result = chardet.detect(file_content)
            encoding = result.get('encoding', self.default_encoding)
            confidence = result.get('confidence', 0)
            
            if confidence < 0.7:
                encoding = self.default_encoding
            
            return encoding.lower()
        except:
            return self.default_encoding
    
    def detect_file_type(self, filename: str) -> FileType:
        """
        Detect file type from filename
        """
        filename_lower = filename.lower()
        
        if any(filename_lower.endswith(ext) for ext in ['.xlsx', '.xls']):
            return FileType.EXCEL
        elif filename_lower.endswith('.csv'):
            return FileType.CSV
        else:
            return FileType.UNSUPPORTED
    
    def validate_file_extension(self, filename: str) -> bool:
        """
        Validate file extension
        """
        return any(filename.lower().endswith(ext) for ext in self.supported_formats)
    def validate_file_size(self, file_bytes: bytes, filename: str):
        """
        Validate file size
        """
        file_size = len(file_bytes)
        
        if file_size == 0:
            raise DataValidationError("File is empty")
        
        if file_size > self.max_file_size:
            size_mb = file_size / (1024 * 1024)
            max_mb = self.max_file_size / (1024 * 1024)
            raise DataValidationError(f"File too large: {size_mb:.1f}MB. Maximum allowed: {max_mb}MB")
    
    def decode_base64_file(self, file_content: str) -> bytes:
        """
        Decode base64 encoded file content
        """
        try:
            # Remove data URL prefix if present
            if file_content.startswith('data:'):
                file_content = file_content.split(',')[1]
            
            return base64.b64decode(file_content)
        except Exception as e:
            raise DataValidationError(f"Error decoding base64 file: {str(e)}")
    
    def get_file_metadata(self, df: pd.DataFrame, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """
        Get comprehensive file metadata and statistics
        """
        file_size = len(file_bytes)
        
        # Basic statistics for numeric columns
        numeric_stats = {}
        for col in df.select_dtypes(include=['number']).columns:
            numeric_stats[col] = {
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'mean': float(df[col].mean()),
                'null_count': int(df[col].isna().sum())
            }
        
        # Data quality metrics
        total_cells = df.size
        null_cells = df.isna().sum().sum()
        empty_string_cells = (df == '').sum().sum()
        
        data_quality = {
            'completeness_score': round((1 - (null_cells / total_cells)) * 100, 2) if total_cells > 0 else 0,
            'null_percentage': round((null_cells / total_cells) * 100, 2) if total_cells > 0 else 0,
            'empty_string_percentage': round((empty_string_cells / total_cells) * 100, 2) if total_cells > 0 else 0,
        }
        
        return {
            "filename": filename,
            "total_records": len(df),
            "total_columns": len(df.columns),
            "column_names": list(df.columns),
            "file_size_bytes": file_size,
            "file_size_kb": round(file_size / 1024, 2),
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "data_types": {col: str(df[col].dtype) for col in df.columns},
            "numeric_columns_statistics": numeric_stats,
            "data_quality_metrics": data_quality,
            "processing_timestamp": datetime.now().isoformat(),
            "memory_usage_kb": round(df.memory_usage(deep=True).sum() / 1024, 2)
        }
    
    def convert_to_erpnext_format(self, df: pd.DataFrame, mapping_config: Dict, endpoint: ERPNextEndpoint) -> List[Dict[str, Any]]:
        """
        Convert DataFrame to ERPNext specific format using mapping configuration
        """
        try:
            erp_data = []
            
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                
                # Map based on endpoint type
                if endpoint == ERPNextEndpoint.CUSTOMERS:
                    mapped_data = self.erpnext_mapper.map_to_erpnext_customer(row_dict, mapping_config)
                elif endpoint == ERPNextEndpoint.ITEMS:
                    mapped_data = self.erpnext_mapper.map_to_erpnext_item(row_dict, mapping_config)
                elif endpoint == ERPNextEndpoint.SALES_ORDERS:
                    mapped_data = self.erpnext_mapper.map_to_erpnext_sales_order(row_dict, mapping_config)
                elif endpoint == ERPNextEndpoint.SALES_INVOICES:
                    mapped_data = self.erpnext_mapper.map_to_erpnext_sales_order(row_dict, mapping_config)
                else:
                    # Generic mapping for other endpoints
                    mapped_data = {}
                    for target_field, source_config in mapping_config.get('target_columns', {}).items():
                        source_field = source_config.get('source_column')
                        transformation = source_config.get('transformation')
                        
                        if source_field in row_dict and pd.notna(row_dict[source_field]):
                            value = row_dict[source_field]
                            value = self.erpnext_mapper.apply_transformation(value, transformation)
                            mapped_data[target_field] = value
                
                # Validate the mapped data
                validation_errors = self.erpnext_mapper.validate_erpnext_data(mapped_data, endpoint)
                if validation_errors:
                    logger.warning(f"Validation errors for record: {validation_errors}")
                    # Continue processing but log errors
                
                erp_data.append(mapped_data)
            
            logger.info(f"Successfully converted {len(erp_data)} records to ERPNext format for {endpoint.value}")
            return erp_data
            
        except Exception as e:
            logger.error(f"Error converting to ERPNext format: {str(e)}")
            raise DataValidationError(f"ERPNext data conversion failed: {str(e)}")
    
    def convert_to_erp_format(self, df: pd.DataFrame, mapping_config: Dict) -> List[Dict[str, Any]]:
        """
        Legacy method for backward compatibility
        """
        endpoint_str = mapping_config.get('erp_endpoint', 'customers')
        try:
            endpoint = ERPNextEndpoint(endpoint_str)
            return self.convert_to_erpnext_format(df, mapping_config, endpoint)
        except ValueError:
            # Fallback to generic conversion
            return self._convert_to_generic_erp_format(df, mapping_config)
    
    def _convert_to_generic_erp_format(self, df: pd.DataFrame, mapping_config: Dict) -> List[Dict[str, Any]]:
        """
        Generic ERP format conversion (fallback)
        """
        erp_data = []
        target_mapping = mapping_config.get('target_columns', {})
        
        for _, row in df.iterrows():
            erp_record = {}
            
            for target_field, source_config in target_mapping.items():
                source_field = source_config.get('source_column')
                transformation = source_config.get('transformation')
                
                if source_field in df.columns:
                    value = row[source_field]
                    
                    # Apply transformations if specified
                    if transformation == 'uppercase' and isinstance(value, str):
                        value = value.upper()
                    elif transformation == 'lowercase' and isinstance(value, str):
                        value = value.lower()
                    elif transformation == 'trim' and isinstance(value, str):
                        value = value.strip()
                    
                    erp_record[target_field] = value
                else:
                    erp_record[target_field] = None
            
            erp_data.append(erp_record)
        
        return erp_data

# Global file processor instance
file_processor = FileProcessor()
  
