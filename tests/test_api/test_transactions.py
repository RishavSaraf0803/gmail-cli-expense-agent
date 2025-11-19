"""
Tests for transaction API endpoints.
"""
import pytest
from datetime import datetime


class TestTransactionEndpoints:
    """Test transaction API endpoints."""

    def test_list_transactions_empty(self, client):
        """Test listing transactions when database is empty."""
        response = client.get("/api/v1/transactions")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_list_transactions(self, client, sample_transactions):
        """Test listing transactions."""
        response = client.get("/api/v1/transactions")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 5
        assert data["total"] == 5

    def test_list_transactions_pagination(self, client, sample_transactions):
        """Test transaction pagination."""
        response = client.get("/api/v1/transactions?limit=2&offset=1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 1

    def test_list_transactions_filter_by_type(self, client, sample_transactions):
        """Test filtering transactions by type."""
        response = client.get("/api/v1/transactions?transaction_type=debit")
        assert response.status_code == 200

        data = response.json()
        # Should have 3 debit transactions (i=0,2,4)
        assert len(data["items"]) == 3
        assert all(t["transaction_type"] == "debit" for t in data["items"])

    def test_list_transactions_filter_by_merchant(self, client, sample_transactions):
        """Test filtering transactions by merchant."""
        response = client.get("/api/v1/transactions?merchant=Merchant 1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) >= 1
        assert any("Merchant 1" in t["merchant"] for t in data["items"])

    def test_list_transactions_invalid_type(self, client):
        """Test filtering with invalid transaction type."""
        response = client.get("/api/v1/transactions?transaction_type=invalid")
        assert response.status_code == 422  # Validation error

    def test_get_transaction_by_id(self, client, sample_transactions):
        """Test getting a specific transaction by ID."""
        transaction_id = sample_transactions[0].id
        response = client.get(f"/api/v1/transactions/{transaction_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == transaction_id
        assert data["merchant"] == "Merchant 0"

    def test_get_transaction_not_found(self, client):
        """Test getting non-existent transaction."""
        response = client.get("/api/v1/transactions/9999")
        assert response.status_code == 404

    def test_get_transaction_by_email_id(self, client, sample_transactions):
        """Test getting transaction by email ID."""
        response = client.get("/api/v1/transactions/email/test_email_0")
        assert response.status_code == 200

        data = response.json()
        assert data["email_id"] == "test_email_0"

    def test_get_transaction_by_email_not_found(self, client):
        """Test getting transaction by non-existent email ID."""
        response = client.get("/api/v1/transactions/email/nonexistent")
        assert response.status_code == 404

    def test_create_transaction(self, client):
        """Test creating a new transaction."""
        transaction_data = {
            "email_id": "new_email_123",
            "amount": 250.50,
            "transaction_type": "debit",
            "merchant": "Test Merchant",
            "transaction_date": "2025-11-20T10:30:00",
            "currency": "INR",
            "email_subject": "Test Subject"
        }

        response = client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 201

        data = response.json()
        assert data["email_id"] == "new_email_123"
        assert data["amount"] == 250.50
        assert data["merchant"] == "Test Merchant"

    def test_create_transaction_duplicate(self, client, sample_transactions):
        """Test creating duplicate transaction."""
        transaction_data = {
            "email_id": "test_email_0",  # Already exists
            "amount": 100.0,
            "transaction_type": "debit",
            "merchant": "Test",
            "transaction_date": "2025-11-20T10:30:00"
        }

        response = client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 409  # Conflict

    def test_create_transaction_invalid_amount(self, client):
        """Test creating transaction with invalid amount."""
        transaction_data = {
            "email_id": "test_email_new",
            "amount": -100.0,  # Negative amount
            "transaction_type": "debit",
            "merchant": "Test",
            "transaction_date": "2025-11-20T10:30:00"
        }

        response = client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 422  # Validation error

    def test_create_transaction_invalid_type(self, client):
        """Test creating transaction with invalid type."""
        transaction_data = {
            "email_id": "test_email_new",
            "amount": 100.0,
            "transaction_type": "invalid",  # Invalid type
            "merchant": "Test",
            "transaction_date": "2025-11-20T10:30:00"
        }

        response = client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 422  # Validation error

    def test_create_transaction_missing_fields(self, client):
        """Test creating transaction with missing required fields."""
        transaction_data = {
            "email_id": "test_email_new",
            "amount": 100.0
            # Missing transaction_type, merchant, transaction_date
        }

        response = client.post("/api/v1/transactions", json=transaction_data)
        assert response.status_code == 422  # Validation error
