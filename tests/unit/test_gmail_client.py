"""
Unit tests for Gmail client module.
"""
import pytest
from unittest.mock import MagicMock, patch

from fincli.clients.gmail_client import (
    GmailClient,
    EmailMessage,
    GmailClientError,
)


class TestEmailMessage:
    """Test EmailMessage class."""

    def test_create_email_message(self):
        """Test creating an email message."""
        email = EmailMessage(
            message_id="msg_123",
            subject="Transaction Alert",
            date="2025-11-15",
            snippet="Your card was debited",
        )

        assert email.message_id == "msg_123"
        assert email.subject == "Transaction Alert"
        assert email.date == "2025-11-15"
        assert email.snippet == "Your card was debited"

    def test_get_context_text(self):
        """Test get_context_text method."""
        email = EmailMessage(
            message_id="msg_123",
            subject="Transaction Alert",
            date="2025-11-15",
            snippet="Your card was debited for INR 100",
        )

        context = email.get_context_text()

        assert "Subject: Transaction Alert" in context
        assert "Date: 2025-11-15" in context
        assert "Content: Your card was debited for INR 100" in context

    def test_to_dict(self):
        """Test to_dict method."""
        email = EmailMessage(
            message_id="msg_123",
            subject="Transaction Alert",
            date="2025-11-15",
            snippet="Your card was debited",
            full_content="Full email content",
        )

        data = email.to_dict()

        assert data["message_id"] == "msg_123"
        assert data["subject"] == "Transaction Alert"
        assert data["date"] == "2025-11-15"
        assert data["snippet"] == "Your card was debited"
        assert data["full_content"] == "Full email content"


class TestGmailClient:
    """Test GmailClient class."""

    def test_client_initialization(self, mock_gmail_service):
        """Test client initialization."""
        client = GmailClient(service=mock_gmail_service)

        assert client.service is not None
        assert client.max_results == 100
        assert client.batch_size == 10

    def test_custom_settings(self, mock_gmail_service):
        """Test client with custom settings."""
        client = GmailClient(
            service=mock_gmail_service,
            max_results=50,
            batch_size=5,
        )

        assert client.max_results == 50
        assert client.batch_size == 5

    def test_get_header_value(self, mock_gmail_service):
        """Test _get_header_value method."""
        client = GmailClient(service=mock_gmail_service)

        headers = [
            {"name": "Subject", "value": "Test Subject"},
            {"name": "Date", "value": "2025-11-15"},
        ]

        subject = client._get_header_value(headers, "Subject")
        date = client._get_header_value(headers, "Date")
        missing = client._get_header_value(headers, "Missing")

        assert subject == "Test Subject"
        assert date == "2025-11-15"
        assert missing == "Unknown"

    def test_parse_message(self, mock_gmail_service):
        """Test _parse_message method."""
        client = GmailClient(service=mock_gmail_service)

        message = {
            "id": "msg_123",
            "snippet": "Your card was debited",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Transaction Alert"},
                    {"name": "Date", "value": "2025-11-15"},
                ]
            }
        }

        email = client._parse_message(message)

        assert isinstance(email, EmailMessage)
        assert email.message_id == "msg_123"
        assert email.subject == "Transaction Alert"
        assert email.date == "2025-11-15"
        assert email.snippet == "Your card was debited"

    @patch('time.sleep')
    def test_fetch_messages(self, mock_sleep, mock_gmail_service):
        """Test fetch_messages method."""
        client = GmailClient(service=mock_gmail_service, batch_size=1)

        messages = client.fetch_messages(query="transaction", max_results=2)

        assert len(messages) >= 1
        assert all(isinstance(msg, EmailMessage) for msg in messages)

    def test_fetch_messages_empty_result(self, mock_gmail_service):
        """Test fetch_messages with no results."""
        # Mock empty response
        mock_gmail_service.users().messages().list().execute.return_value = {
            "messages": []
        }

        client = GmailClient(service=mock_gmail_service)
        messages = client.fetch_messages()

        assert len(messages) == 0

    @patch('time.sleep')
    def test_fetch_messages_stream(self, mock_sleep, mock_gmail_service):
        """Test fetch_messages_stream method."""
        client = GmailClient(service=mock_gmail_service, batch_size=1)

        messages = list(client.fetch_messages_stream(max_results=2))

        assert len(messages) >= 1
        assert all(isinstance(msg, EmailMessage) for msg in messages)

    def test_get_user_profile(self, mock_gmail_service):
        """Test get_user_profile method."""
        # Mock profile response
        mock_gmail_service.users().getProfile().execute.return_value = {
            "emailAddress": "test@example.com",
            "messagesTotal": 100,
        }

        client = GmailClient(service=mock_gmail_service)
        profile = client.get_user_profile()

        assert profile["emailAddress"] == "test@example.com"
        assert profile["messagesTotal"] == 100

    def test_fetch_messages_with_labels(self, mock_gmail_service):
        """Test fetch_messages with label filtering."""
        client = GmailClient(service=mock_gmail_service)

        messages = client.fetch_messages(
            query="transaction",
            label_ids=["INBOX"],
            max_results=10,
        )

        # Verify list was called with label_ids
        mock_gmail_service.users().messages().list.assert_called()
        call_args = mock_gmail_service.users().messages().list.call_args
        assert "labelIds" in call_args[1] or len(call_args[0]) > 0
