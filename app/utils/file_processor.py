import pandas as pd
import io
from typing import Dict, Any, List
import base64

def process_excel_file(file_content: bytes) -> pd.DataFrame:
    """
    Process Excel file and return DataFrame
    
    Args:
        file_content: Bytes content of the uploaded file
        
    Returns:
        pandas.DataFrame: Processed data
    """
    try:
        # Read Excel file
        df = pd.read_excel(io.BytesIO(file_content))
        
        # Clean column names (remove extra spaces, make consistent)
        df.columns = [str(col).strip() for col in df.columns]
        
        # Handle empty files
        if df.empty:
            raise ValueError("Uploaded file is empty")
        
        # Replace NaN values with empty strings
        df = df.fillna('')
            
        return df
        
    except Exception as e:
        raise Exception(f"Error reading Excel file: {str(e)}")

def process_csv_file(file_content: bytes) -> pd.DataFrame:
    """
    Process CSV file and return DataFrame
    
    Args:
        file_content: Bytes content of the uploaded file
        
    Returns:
        pandas.DataFrame: Processed data
    """
    try:
        # Read CSV file
        df = pd.read_csv(io.StringIO(file_content.decode('utf-8')))
        
        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        
        # Handle empty files
        if df.empty:
            raise ValueError("Uploaded file is empty")
        
        # Replace NaN values with empty strings
        df = df.fillna('')
            
        return df
        
    except Exception as e:
        raise Exception(f"Error reading CSV file: {str(e)}")

def validate_file_extension(filename: str) -> bool:
    """
    Validate file extension
    
    Args:
        filename: Name of the uploaded file
        
    Returns:
        bool: True if valid extension
    """
    valid_extensions = {'.xlsx', '.xls', '.csv'}
    return any(filename.lower().endswith(ext) for ext in valid_extensions)

def get_file_metadata(df: pd.DataFrame, filename: str) -> Dict[str, Any]:
    """
    Get file metadata and statistics
    
    Args:
        df: Processed DataFrame
        filename: Original filename
        
    Returns:
        Dict with file metadata
    """
    return {
        "filename": filename,
        "total_records": len(df),
        "total_columns": len(df.columns),
        "column_names": list(df.columns),
        "file_size_kb": df.memory_usage(deep=True).sum() / 1024,
        "data_types": {col: str(df[col].dtype) for col in df.columns}
    }

def decode_base64_file(file_content: str) -> bytes:
    """
    Decode base64 encoded file content
    
    Args:
        file_content: Base64 encoded string
        
    Returns:
        bytes: Decoded file content
    """
    try:
        # Remove data URL prefix if present
        if file_content.startswith('data:'):
            file_content = file_content.split(',')[1]
        
        return base64.b64decode(file_content)
    except Exception as e:
        raise Exception(f"Error decoding base64 file: {str(e)}")
