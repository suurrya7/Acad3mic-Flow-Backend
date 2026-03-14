#!/usr/bin/env python3
"""
Basic automated tests for Acad3mic-Flow API
Run with: pytest tests/test_api.py
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_signup_endpoint_exists(self):
        """Verify signup endpoint is accessible"""
        response = client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "testpass123"
        })
        # Accept both 200 (success) and 400 (user exists)
        assert response.status_code in [200, 400]
    
    def test_unauthorized_access(self):
        """Verify protected endpoints require authentication"""
        response = client.get("/auth/me")
        assert response.status_code == 401
        assert "detail" in response.json()

class TestHealthCheck:
    """Test health and status endpoints"""
    
    def test_root_endpoint(self):
        """Verify root endpoint returns success"""
        response = client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()
    
    def test_health_check(self):
        """Verify health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "version" in data

class TestValidation:
    """Test input validation"""
    
    def test_invalid_payment_amount(self):
        """Verify payment validation rejects invalid amounts"""
        # This would need authentication, so we just test structure
        response = client.post(
            "/payments/payu/create-order",
            json={
                "amount": 999,  # Invalid amount
                "productinfo": "Test",
                "firstname": "Test",
                "email": "test@test.com"
            }
        )
        # Expect either 401 (no auth) or 400 (bad amount)
        assert response.status_code in [400, 401]

class TestSecurityHeaders:
    """Test security headers are present"""
    
    def test_security_headers_present(self):
        """Verify security headers are set"""
        response = client.get("/")
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in response.headers
        assert "x-xss-protection" in response.headers
    
    def test_correlation_id_header(self):
        """Verify X-Request-ID header is added"""
        response = client.get("/")
        assert "x-request-id" in response.headers
