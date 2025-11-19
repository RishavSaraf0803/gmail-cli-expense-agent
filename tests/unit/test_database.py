"""
Unit tests for database module.
"""
import pytest
from datetime import datetime, timedelta

from fincli.storage.database import DatabaseManager
from fincli.storage.models import Transaction


class TestDatabaseManager:
    """Test DatabaseManager class."""

    def test_create_tables(self, db_manager):
        """Test table creation."""
        # Tables should be created in fixture
        assert db_manager.engine is not None

    def test_add_transaction(self, db_manager, sample_transaction):
        """Test adding a transaction."""
        transaction = db_manager.add_transaction(**sample_transaction)

        assert transaction is not None
        assert transaction.email_id == sample_transaction["email_id"]
        assert transaction.amount == sample_transaction["amount"]
        assert transaction.merchant == sample_transaction["merchant"]

    def test_add_duplicate_transaction(self, db_manager, sample_transaction):
        """Test adding duplicate transaction returns None."""
        # Add first time
        transaction1 = db_manager.add_transaction(**sample_transaction)
        assert transaction1 is not None

        # Add duplicate (same email_id)
        transaction2 = db_manager.add_transaction(**sample_transaction)
        assert transaction2 is None

    def test_get_transaction_by_email_id(self, db_manager, sample_transaction):
        """Test getting transaction by email ID."""
        # Add transaction
        db_manager.add_transaction(**sample_transaction)

        # Retrieve it
        transaction = db_manager.get_transaction_by_email_id(
            sample_transaction["email_id"]
        )

        assert transaction is not None
        assert transaction.email_id == sample_transaction["email_id"]

    def test_get_all_transactions(self, db_manager, sample_transaction):
        """Test getting all transactions."""
        # Add multiple transactions
        for i in range(5):
            data = sample_transaction.copy()
            data["email_id"] = f"test_email_{i}"
            db_manager.add_transaction(**data)

        # Get all
        transactions = db_manager.get_all_transactions()

        assert len(transactions) == 5

    def test_get_transactions_with_pagination(self, db_manager, sample_transaction):
        """Test pagination."""
        # Add 10 transactions
        for i in range(10):
            data = sample_transaction.copy()
            data["email_id"] = f"test_email_{i}"
            db_manager.add_transaction(**data)

        # Get first 5
        transactions = db_manager.get_all_transactions(limit=5, offset=0)
        assert len(transactions) == 5

        # Get next 5
        transactions = db_manager.get_all_transactions(limit=5, offset=5)
        assert len(transactions) == 5

    def test_get_transactions_by_type(self, db_manager, sample_transaction):
        """Test filtering by transaction type."""
        # Add debits
        for i in range(3):
            data = sample_transaction.copy()
            data["email_id"] = f"debit_{i}"
            data["transaction_type"] = "debit"
            db_manager.add_transaction(**data)

        # Add credits
        for i in range(2):
            data = sample_transaction.copy()
            data["email_id"] = f"credit_{i}"
            data["transaction_type"] = "credit"
            db_manager.add_transaction(**data)

        # Get debits
        debits = db_manager.get_transactions_by_type("debit")
        assert len(debits) == 3

        # Get credits
        credits = db_manager.get_transactions_by_type("credit")
        assert len(credits) == 2

    def test_get_transactions_by_merchant(self, db_manager, sample_transaction):
        """Test filtering by merchant."""
        # Add Amazon transactions
        for i in range(3):
            data = sample_transaction.copy()
            data["email_id"] = f"amazon_{i}"
            data["merchant"] = "Amazon"
            db_manager.add_transaction(**data)

        # Add Swiggy transactions
        for i in range(2):
            data = sample_transaction.copy()
            data["email_id"] = f"swiggy_{i}"
            data["merchant"] = "Swiggy"
            db_manager.add_transaction(**data)

        # Get Amazon transactions
        amazon = db_manager.get_transactions_by_merchant("Amazon")
        assert len(amazon) == 3

        # Partial match should work
        amazon_partial = db_manager.get_transactions_by_merchant("Ama")
        assert len(amazon_partial) == 3

    def test_get_transactions_by_date_range(self, db_manager, sample_transaction):
        """Test filtering by date range."""
        base_date = datetime(2025, 11, 1)

        # Add transactions across different dates
        for i in range(10):
            data = sample_transaction.copy()
            data["email_id"] = f"date_{i}"
            data["transaction_date"] = base_date + timedelta(days=i)
            db_manager.add_transaction(**data)

        # Get transactions from day 2 to day 5
        start_date = base_date + timedelta(days=2)
        end_date = base_date + timedelta(days=5)

        transactions = db_manager.get_transactions_by_date_range(
            start_date, end_date
        )

        assert len(transactions) == 4  # Days 2, 3, 4, 5

    def test_get_total_by_type(self, db_manager, sample_transaction):
        """Test calculating totals by type."""
        # Add debits
        for i in range(3):
            data = sample_transaction.copy()
            data["email_id"] = f"debit_{i}"
            data["transaction_type"] = "debit"
            data["amount"] = 100.0
            db_manager.add_transaction(**data)

        # Add credits
        for i in range(2):
            data = sample_transaction.copy()
            data["email_id"] = f"credit_{i}"
            data["transaction_type"] = "credit"
            data["amount"] = 50.0
            db_manager.add_transaction(**data)

        # Calculate totals
        total_debit = db_manager.get_total_by_type("debit")
        total_credit = db_manager.get_total_by_type("credit")

        assert total_debit == 300.0
        assert total_credit == 100.0

    def test_get_top_merchants(self, db_manager, sample_transaction):
        """Test getting top merchants."""
        # Add transactions
        merchants = ["Amazon", "Amazon", "Amazon", "Swiggy", "Swiggy", "Uber"]

        for i, merchant in enumerate(merchants):
            data = sample_transaction.copy()
            data["email_id"] = f"txn_{i}"
            data["merchant"] = merchant
            db_manager.add_transaction(**data)

        # Get top merchants
        top = db_manager.get_top_merchants(limit=3)

        assert len(top) == 3
        assert top[0][0] == "Amazon"  # Most frequent
        assert top[0][1] == 3  # Count
        assert top[1][0] == "Swiggy"
        assert top[1][1] == 2

    def test_count_transactions(self, db_manager, sample_transaction):
        """Test counting transactions."""
        # Initially empty
        assert db_manager.count_transactions() == 0

        # Add transactions
        for i in range(5):
            data = sample_transaction.copy()
            data["email_id"] = f"txn_{i}"
            db_manager.add_transaction(**data)

        # Count should be 5
        assert db_manager.count_transactions() == 5
