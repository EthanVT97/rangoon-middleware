from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

SQLALCHEMY_DATABASE_URL = "sqlite:///./middleware.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ColumnMapping(Base):
    __tablename__ = "column_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    mapping_name = Column(String, unique=True, index=True)
    source_columns = Column(JSON)  # Excel column definitions
    target_columns = Column(JSON)  # ERP field mappings
    mapping_rules = Column(JSON)   # Transformation rules
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ImportJob(Base):
    __tablename__ = "import_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)
    mapping_id = Column(Integer)
    filename = Column(String)
    status = Column(String)  # pending, processing, completed, failed
    total_records = Column(Integer, default=0)
    processed_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)
    error_log = Column(JSON)
    erp_response = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class ERPConnection(Base):
    __tablename__ = "erp_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    base_url = Column(String)
    api_key = Column(String)
    endpoints = Column(JSON)  # { "customers": "/api/customers", "products": "/api/products" }
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
