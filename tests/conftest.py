"""
Pytest configuration and fixtures for FinCLI tests.
"""
import os
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fincli.config import Settings
from fincli.storage.models import Base, Transaction
from fincli.storage.database import DatabaseManager


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        debug=True,
        gmail_credentials_path=Path("test_credentials.json"),
        gmail_token_path=Path("test_token.json"),
        bedrock_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        database_url="sqlite:///:memory:",
        log_level="DEBUG",
        log_format="console",
    )


@pytest.fixture
def test_db():
    """Create in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_manager():
    """Create test database manager."""
    manager = DatabaseManager(database_url="sqlite:///:memory:")
    manager.create_tables()
    return manager


@pytest.fixture
def sample_transaction():
    """Create sample transaction data."""
    return {
        "email_id": "test_email_123",
        "amount": 100.50,
        "transaction_type": "debit",
        "merchant": "Amazon",
        "currency": "INR",
        "transaction_date": datetime(2025, 11, 15, 10, 30),
        "email_subject": "Transaction Alert",
        "email_snippet": "Your card was debited for INR 100.50",
        "email_date": datetime(2025, 11, 15, 10, 31),
    }


@pytest.fixture
def mock_gmail_service():
    """Create mock Gmail service."""
    service = MagicMock()

    # Mock users().messages().list()
    messages_list = MagicMock()
    messages_list.execute.return_value = {
        "messages": [
            {"id": "msg_1"},
            {"id": "msg_2"},
        ]
    }

    # Mock users().messages().get()
    message_get = MagicMock()
    message_get.execute.return_value = {
        "id": "msg_1",
        "snippet": "Your card was debited for INR 100.50",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Transaction Alert"},
                {"name": "Date", "value": "2025-11-15"},
            ]
        }
    }

    service.users().messages().list.return_value = messages_list
    service.users().messages().get.return_value = message_get

    return service


@pytest.fixture
def mock_bedrock_client():
    """Create mock Bedrock client."""
    client = MagicMock()

    # Mock invoke_model response
    response = {
        "body": MagicMock()
    }
    response["body"].read.return_value = b'{"content": [{"text": "{\\"amount\\": 100.50, \\"type\\": \\"debit\\", \\"merchant\\": \\"Amazon\\", \\"date\\": \\"2025-11-15\\", \\"currency\\": \\"INR\\"}"}], "usage": {"input_tokens": 100, "output_tokens": 50}}'

    client.invoke_model.return_value = response

    return client


@pytest.fixture
def sample_email_data():
    """Create sample email data."""
    return {
        "message_id": "test_msg_123",
        "subject": "Transaction Alert",
        "date": "2025-11-15",
        "snippet": "Your card was debited for INR 100.50 at Amazon",
    }


@pytest.fixture
def sample_bedrock_response():
    """Create sample Bedrock extraction response."""
    return {
        "amount": 100.50,
        "type": "debit",
        "merchant": "Amazon",
        "date": "2025-11-15",
        "currency": "INR",
    }


@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment variables before each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_credentials_file(tmp_path):
    """Create temporary credentials file."""
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {"client_id": "test_id"}}')
    return creds_file


@pytest.fixture
def temp_token_file(tmp_path):
    """Create temporary token file."""
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token": "test_token", "refresh_token": "test_refresh"}')
    return token_file
