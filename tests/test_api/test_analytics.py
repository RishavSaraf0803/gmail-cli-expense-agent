"""
Tests for analytics API endpoints.
"""
import pytest


class TestAnalyticsEndpoints:
    """Test analytics API endpoints."""

    def test_get_summary_empty(self, client):
        """Test getting summary with no transactions."""
        response = client.get("/api/v1/analytics/summary")
        assert response.status_code == 200

        data = response.json()
        assert data["total_spent"] == 0.0
        assert data["total_credited"] == 0.0
        assert data["net"] == 0.0
        assert data["total_transactions"] == 0

    def test_get_summary(self, client, sample_transactions):
        """Test getting financial summary."""
        response = client.get("/api/v1/analytics/summary")
        assert response.status_code == 200

        data = response.json()
        # 3 debits: 100, 200, 300 = 600
        assert data["total_spent"] == 600.0
        # 2 credits: 150, 250 = 400
        assert data["total_credited"] == 400.0
        # Net: 400 - 600 = -200
        assert data["net"] == -200.0
        assert data["total_transactions"] == 5
        assert data["currency"] == "INR"

    def test_get_top_merchants_empty(self, client):
        """Test getting top merchants with no transactions."""
        response = client.get("/api/v1/analytics/merchants/top")
        assert response.status_code == 200

        data = response.json()
        assert data["merchants"] == []

    def test_get_top_merchants(self, client, sample_transactions):
        """Test getting top merchants."""
        response = client.get("/api/v1/analytics/merchants/top")
        assert response.status_code == 200

        data = response.json()
        assert len(data["merchants"]) == 5
        assert data["transaction_type"] is None

        # Verify structure
        for merchant in data["merchants"]:
            assert "merchant" in merchant
            assert "transaction_count" in merchant
            assert "total_amount" in merchant
            assert merchant["transaction_count"] == 1

    def test_get_top_merchants_with_limit(self, client, sample_transactions):
        """Test getting top merchants with limit."""
        response = client.get("/api/v1/analytics/merchants/top?limit=3")
        assert response.status_code == 200

        data = response.json()
        assert len(data["merchants"]) == 3

    def test_get_top_merchants_filter_by_type(self, client, sample_transactions):
        """Test getting top merchants filtered by type."""
        response = client.get("/api/v1/analytics/merchants/top?transaction_type=debit")
        assert response.status_code == 200

        data = response.json()
        # Should have 3 merchants with debit transactions
        assert len(data["merchants"]) == 3
        assert data["transaction_type"] == "debit"

    def test_get_top_merchants_invalid_type(self, client):
        """Test getting top merchants with invalid type."""
        response = client.get("/api/v1/analytics/merchants/top?transaction_type=invalid")
        assert response.status_code == 422  # Validation error

    def test_get_top_merchants_invalid_limit(self, client):
        """Test getting top merchants with invalid limit."""
        response = client.get("/api/v1/analytics/merchants/top?limit=0")
        assert response.status_code == 422  # Validation error

        response = client.get("/api/v1/analytics/merchants/top?limit=1000")
        assert response.status_code == 422  # Validation error
