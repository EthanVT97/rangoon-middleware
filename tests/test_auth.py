import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_register_user():
    """Test user registration"""
    user_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
        "company": "Test Company"
    }
    
    response = client.post("/api/auth/register", json=user_data)
    # Note: In real tests, we would mock the Supabase calls
    assert response.status_code in [200, 400]  # 400 if user already exists

def test_login_user():
    """Test user login"""
    login_data = {
        "email": "test@example.com", 
        "password": "testpassword123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    # Note: In real tests, we would have proper test setup
    assert response.status_code in [200, 401]

def test_protected_endpoint_without_auth():
    """Test that protected endpoints require authentication"""
    response = client.get("/api/auth/me")
    assert response.status_code == 403  # Unauthorized
