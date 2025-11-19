"""
Pytest fixtures for API tests.
"""
import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

import fincli.api.dependencies as dependencies
from fincli.api.routers import transactions, analytics, operations
from fincli.storage.database import DatabaseManager


@pytest.fixture
def test_db():
    """Create in-memory test database with shared cache."""
    # Use file-based memory with shared cache so all connections see the same data
    db = DatabaseManager(database_url="sqlite:///file:testdb?mode=memory&cache=shared")
    # Drop tables first to ensure clean state
    try:
        db.drop_tables()
    except Exception:
        pass  # Tables might not exist on first run
    db.create_tables()
    yield db
    # Cleanup after test
    try:
        db.drop_tables()
    except Exception:
        pass


@pytest.fixture
def app(test_db):
    """Create FastAPI test app with mocked dependencies."""
    # Inject test database into the singleton
    # This ensures get_db_manager() returns the test database
    dependencies._db_manager = test_db

    # Clear other singletons so tests can inject their own mocks
    dependencies._gmail_client = None
    dependencies._llm_client = None
    dependencies._extractor = None

    # Create app without lifespan for testing
    app = FastAPI(
        title="FinCLI API Test",
        version="1.0.0"
    )

    # Include routers
    app.include_router(operations.router)
    app.include_router(transactions.router, prefix="/api/v1")
    app.include_router(analytics.router, prefix="/api/v1")

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "FinCLI API",
            "version": "1.0.0",
            "description": "Financial Transaction Tracker API",
            "docs_url": "/docs",
            "health_url": "/health"
        }

    yield app

    # Cleanup
    dependencies.reset_clients()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Auto-reset singleton clients before each test."""
    # Clear client singletons before each test
    # (but not database, which is managed by test_db fixture)
    dependencies._gmail_client = None
    dependencies._llm_client = None
    dependencies._extractor = None
    yield
    # Cleanup after test
    dependencies._gmail_client = None
    dependencies._llm_client = None
    dependencies._extractor = None


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_transactions(test_db):
    """Create sample transactions in database."""
    transactions = []
    for i in range(5):
        transaction = test_db.add_transaction(
            email_id=f"test_email_{i}",
            amount=100.0 + (i * 50),
            transaction_type="debit" if i % 2 == 0 else "credit",
            merchant=f"Merchant {i}",
            transaction_date=datetime(2025, 11, 15 + i),
            currency="INR",
            email_subject=f"Transaction {i}",
            email_snippet=f"Test transaction {i}"
        )
        transactions.append(transaction)
    return transactions


@pytest.fixture
def mock_gmail_client():
    """Create mock Gmail client and inject into singleton."""
    client = MagicMock()
    client.fetch_messages.return_value = []
    client.get_user_profile.return_value = {
        "emailAddress": "test@example.com",
        "messagesTotal": 100
    }
    # Inject into singleton
    dependencies._gmail_client = client
    return client


@pytest.fixture
def mock_bedrock_client():
    """Create mock Bedrock/LLM client and inject into singleton."""
    client = MagicMock()
    client.generate_text.return_value = "Mock AI response"
    client.health_check.return_value = True
    # Inject into singleton
    dependencies._llm_client = client
    return client


@pytest.fixture
def mock_extractor():
    """Create mock transaction extractor and inject into singleton."""
    extractor = MagicMock()
    extractor.extract_batch.return_value = []
    # Inject into singleton
    dependencies._extractor = extractor
    return extractor
