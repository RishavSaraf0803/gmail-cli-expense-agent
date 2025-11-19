"""
Unit tests for database models.
"""
import pytest
from datetime import datetime

from fincli.storage.models import Transaction


class TestTransactionModel:
    """Test Transaction model."""

    def test_create_transaction(self, test_db):
        """Test creating a transaction."""
        transaction = Transaction(
            email_id="test_123",
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            currency="INR",
            transaction_date=datetime(2025, 11, 15),
        )

        test_db.add(transaction)
        test_db.commit()

        assert transaction.id is not None
        assert transaction.email_id == "test_123"
        assert transaction.amount == 100.50

    def test_transaction_repr(self, test_db):
        """Test transaction string representation."""
        transaction = Transaction(
            email_id="test_123",
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            currency="INR",
            transaction_date=datetime(2025, 11, 15),
        )

        test_db.add(transaction)
        test_db.commit()

        repr_str = repr(transaction)

        assert "Transaction" in repr_str
        assert "debit" in repr_str
        assert "Amazon" in repr_str
        assert "100.5" in repr_str

    def test_transaction_to_dict(self, test_db):
        """Test transaction to_dict method."""
        transaction = Transaction(
            email_id="test_123",
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            currency="INR",
            transaction_date=datetime(2025, 11, 15),
            email_subject="Test Subject",
        )

        test_db.add(transaction)
        test_db.commit()

        data = transaction.to_dict()

        assert isinstance(data, dict)
        assert data["email_id"] == "test_123"
        assert data["amount"] == 100.50
        assert data["type"] == "debit"
        assert data["merchant"] == "Amazon"
        assert data["currency"] == "INR"
        assert "transaction_date" in data

    def test_unique_email_id_constraint(self, test_db):
        """Test unique constraint on email_id."""
        # Add first transaction
        transaction1 = Transaction(
            email_id="test_123",
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            currency="INR",
            transaction_date=datetime(2025, 11, 15),
        )
        test_db.add(transaction1)
        test_db.commit()

        # Try to add duplicate email_id
        transaction2 = Transaction(
            email_id="test_123",  # Same email_id
            amount=200.00,
            transaction_type="credit",
            merchant="Paypal",
            currency="USD",
            transaction_date=datetime(2025, 11, 16),
        )
        test_db.add(transaction2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            test_db.commit()

    def test_transaction_defaults(self, test_db):
        """Test default values."""
        transaction = Transaction(
            email_id="test_123",
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            transaction_date=datetime(2025, 11, 15),
        )

        test_db.add(transaction)
        test_db.commit()

        # Check defaults
        assert transaction.currency == "INR"
        assert transaction.created_at is not None
        assert transaction.updated_at is not None

    def test_transaction_timestamps(self, test_db):
        """Test created_at and updated_at timestamps."""
        transaction = Transaction(
            email_id="test_123",
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            currency="INR",
            transaction_date=datetime(2025, 11, 15),
        )

        test_db.add(transaction)
        test_db.commit()

        created_at = transaction.created_at
        updated_at = transaction.updated_at

        assert created_at is not None
        assert updated_at is not None

        # Update transaction
        transaction.amount = 200.00
        test_db.commit()
        test_db.refresh(transaction)

        # updated_at should change
        assert transaction.updated_at > updated_at
        # created_at should not change
        assert transaction.created_at == created_at

    def test_optional_fields(self, test_db):
        """Test optional fields can be None."""
        transaction = Transaction(
            email_id="test_123",
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            currency="INR",
            transaction_date=datetime(2025, 11, 15),
            # Optional fields not provided
        )

        test_db.add(transaction)
        test_db.commit()

        assert transaction.email_subject is None
        assert transaction.email_snippet is None
        assert transaction.email_date is None
        assert transaction.category is None
        assert transaction.notes is None
