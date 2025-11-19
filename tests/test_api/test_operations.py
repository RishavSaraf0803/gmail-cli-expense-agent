"""
Tests for operations API endpoints.
"""
import pytest
from unittest.mock import patch


class TestOperationsEndpoints:
    """Test operations API endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "version" in data
        assert data["database"] == "connected"

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "FinCLI API"
        assert "version" in data
        assert "docs_url" in data

    def test_init_database(self, client):
        """Test initialization endpoint."""
        with patch("fincli.api.dependencies.get_gmail") as mock_gmail, \
             patch("fincli.api.dependencies.get_llm") as mock_llm:

            mock_gmail.return_value.get_user_profile.return_value = {
                "emailAddress": "test@example.com"
            }
            mock_llm.return_value = None

            response = client.post("/init")
            assert response.status_code == 200

            data = response.json()
            assert "database_created" in data
            assert "gmail_authenticated" in data
            assert "llm_connected" in data
            assert "message" in data

    def test_fetch_emails(self, client, mock_gmail_client, mock_extractor):
        """Test email fetch endpoint."""
        request_data = {
            "max_emails": 10,
            "force": False
        }

        response = client.post("/fetch", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "new_transactions" in data
        assert "skipped_duplicates" in data
        assert "errors" in data
        assert "total_in_db" in data

    def test_fetch_emails_with_defaults(self, client, mock_gmail_client, mock_extractor):
        """Test email fetch with default parameters."""
        response = client.post("/fetch", json={})
        assert response.status_code == 200

    def test_fetch_emails_invalid_max(self, client, mock_gmail_client, mock_extractor):
        """Test email fetch with invalid max_emails."""
        request_data = {
            "max_emails": 1000,  # Exceeds limit of 500
            "force": False
        }

        response = client.post("/fetch", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_chat(self, client, sample_transactions, mock_bedrock_client):
        """Test chat endpoint."""
        request_data = {
            "question": "How much did I spend?"
        }

        response = client.post("/chat", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["question"] == "How much did I spend?"
        assert "answer" in data
        assert "conversation_id" in data
        assert "timestamp" in data

    def test_chat_with_conversation_id(self, client, mock_bedrock_client):
        """Test chat with existing conversation."""
        request_data = {
            "question": "Tell me more",
            "conversation_id": "test-conv-123"
        }

        response = client.post("/chat", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["conversation_id"] == "test-conv-123"

    def test_chat_empty_question(self, client):
        """Test chat with empty question."""
        request_data = {
            "question": ""
        }

        response = client.post("/chat", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_chat_too_long_question(self, client):
        """Test chat with question that's too long."""
        request_data = {
            "question": "x" * 1001  # Exceeds 1000 char limit
        }

        response = client.post("/chat", json=request_data)
        assert response.status_code == 422  # Validation error
