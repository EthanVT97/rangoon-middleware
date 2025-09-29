import pandas as pd
import io
import base64
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import logging
import chardet
from enum import Enum

logger = logging.getLogger(__name__)

class FileType(Enum):
    EXCEL = "excel"
    CSV = "csv"
    UNSUPPORTED = "unsupported"

class DataValidationError(Exception):
    """Custom exception for data validation errors"""
    pass

class FileProcessor:
    """Enhanced file processor with validation and mapping support"""
    
    def __init__(self):
        self.supported_formats = {'.xlsx', '.xls', '.csv'}
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.default_encoding = 'utf-8'
    
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
        Validate DataFrame against mapping configuration
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
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "columns_found": list(df.columns),
            "columns_required": required_columns
        }
    
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
                pd.to_datetime(series, errors='raise')
            except:
                errors.append(f"Column '{column_name}' contains invalid date values")
        
        elif expected_type == 'email':
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            invalid_emails = series.astype(str).str.match(email_pattern, na=False)
            if not invalid_emails.all():
                invalid_count = (~invalid_emails).sum()
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
    
    def convert_to_erp_format(self, df: pd.DataFrame, mapping_config: Dict) -> List[Dict[str, Any]]:
        """
        Convert DataFrame to ERP format using mapping configuration
        """
        try:
            erp_data = []
            source_columns = mapping_config.get('source_columns', [])
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
            
        except Exception as e:
            logger.error(f"Error converting to ERP format: {str(e)}")
            raise DataValidationError(f"Data conversion failed: {str(e)}")

# Global file processor instance
file_processor = FileProcessor()
