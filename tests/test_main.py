import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_dashboard_page():
    """Test dashboard page loads"""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_mapping_create_page():
    """Test mapping creation page loads"""
    response = client.get("/mapping/create")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_upload_status_page():
    """Test upload status page loads"""
    response = client.get("/upload/status")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_api_docs_available():
    """Test API documentation is available"""
    response = client.get("/api/docs")
    assert response.status_code == 200
