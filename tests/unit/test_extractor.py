"""
Unit tests for transaction extractor module.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fincli.extractors.transaction_extractor import (
    TransactionExtractor,
    ExtractedTransaction,
    TransactionExtractorError,
)
from fincli.clients.gmail_client import EmailMessage


class TestExtractedTransaction:
    """Test ExtractedTransaction class."""

    def test_create_transaction(self):
        """Test creating extracted transaction."""
        transaction = ExtractedTransaction(
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            transaction_date=datetime(2025, 11, 15),
            currency="INR",
        )

        assert transaction.amount == 100.50
        assert transaction.transaction_type == "debit"
        assert transaction.merchant == "Amazon"
        assert transaction.currency == "INR"

    def test_to_dict(self):
        """Test to_dict method."""
        transaction = ExtractedTransaction(
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            transaction_date=datetime(2025, 11, 15),
            currency="INR",
        )

        data = transaction.to_dict()

        assert data["amount"] == 100.50
        assert data["transaction_type"] == "debit"
        assert data["merchant"] == "Amazon"
        assert data["currency"] == "INR"
        assert "transaction_date" in data

    def test_is_valid(self):
        """Test is_valid method."""
        # Valid transaction
        valid = ExtractedTransaction(
            amount=100.50,
            transaction_type="debit",
            merchant="Amazon",
            transaction_date=datetime(2025, 11, 15),
        )
        assert valid.is_valid() is True

        # Invalid: zero amount
        invalid_amount = ExtractedTransaction(
            amount=0,
            transaction_type="debit",
            merchant="Amazon",
            transaction_date=datetime(2025, 11, 15),
        )
        assert invalid_amount.is_valid() is False

        # Invalid: wrong type
        invalid_type = ExtractedTransaction(
            amount=100,
            transaction_type="invalid",
            merchant="Amazon",
            transaction_date=datetime(2025, 11, 15),
        )
        assert invalid_type.is_valid() is False

        # Invalid: N/A merchant
        invalid_merchant = ExtractedTransaction(
            amount=100,
            transaction_type="debit",
            merchant="N/A",
            transaction_date=datetime(2025, 11, 15),
        )
        assert invalid_merchant.is_valid() is False


class TestTransactionExtractor:
    """Test TransactionExtractor class."""

    def test_extractor_initialization(self):
        """Test extractor initialization."""
        with patch('fincli.extractors.transaction_extractor.get_llm_client'):
            extractor = TransactionExtractor()
            assert extractor is not None

    def test_parse_date_valid(self):
        """Test parsing valid dates."""
        with patch('fincli.extractors.transaction_extractor.get_llm_client'):
            extractor = TransactionExtractor()

            # ISO format
            date1 = extractor._parse_date("2025-11-15")
            assert date1.year == 2025
            assert date1.month == 11
            assert date1.day == 15

            # Other formats
            date2 = extractor._parse_date("15 Nov 2025")
            assert date2.year == 2025
            assert date2.month == 11

    def test_parse_date_invalid(self):
        """Test parsing invalid dates."""
        with patch('fincli.extractors.transaction_extractor.get_llm_client'):
            extractor = TransactionExtractor()

            # N/A should return current date
            date = extractor._parse_date("N/A")
            assert isinstance(date, datetime)

            # Empty string
            date = extractor._parse_date("")
            assert isinstance(date, datetime)

    def test_validate_and_clean_valid(self):
        """Test validating valid data."""
        with patch('fincli.extractors.transaction_extractor.get_llm_client'):
            extractor = TransactionExtractor()

            raw_data = {
                "amount": 100.50,
                "type": "debit",
                "merchant": "Amazon",
                "date": "2025-11-15",
                "currency": "INR",
            }

            cleaned = extractor._validate_and_clean(raw_data)

            assert cleaned["amount"] == 100.50
            assert cleaned["type"] == "debit"
            assert cleaned["merchant"] == "Amazon"
            assert cleaned["currency"] == "INR"
            assert isinstance(cleaned["date"], datetime)

    def test_validate_and_clean_missing_field(self):
        """Test validation with missing field."""
        with patch('fincli.extractors.transaction_extractor.get_llm_client'):
            extractor = TransactionExtractor()

            raw_data = {
                "amount": 100.50,
                "type": "debit",
                # Missing merchant, date, currency
            }

            with pytest.raises(TransactionExtractorError):
                extractor._validate_and_clean(raw_data)

    def test_validate_and_clean_invalid_type(self):
        """Test validation with invalid transaction type."""
        with patch('fincli.extractors.transaction_extractor.get_llm_client'):
            extractor = TransactionExtractor()

            raw_data = {
                "amount": 100.50,
                "type": "invalid_type",
                "merchant": "Amazon",
                "date": "2025-11-15",
                "currency": "INR",
            }

            with pytest.raises(TransactionExtractorError):
                extractor._validate_and_clean(raw_data)

    def test_validate_and_clean_na_merchant(self):
        """Test validation with N/A merchant."""
        with patch('fincli.extractors.transaction_extractor.get_llm_client'):
            extractor = TransactionExtractor()

            raw_data = {
                "amount": 100.50,
                "type": "debit",
                "merchant": "N/A",
                "date": "2025-11-15",
                "currency": "INR",
            }

            with pytest.raises(TransactionExtractorError):
                extractor._validate_and_clean(raw_data)

    def test_validate_and_clean_default_currency(self):
        """Test default currency when N/A."""
        with patch('fincli.extractors.transaction_extractor.get_llm_client'):
            extractor = TransactionExtractor()

            raw_data = {
                "amount": 100.50,
                "type": "debit",
                "merchant": "Amazon",
                "date": "2025-11-15",
                "currency": "N/A",
            }

            cleaned = extractor._validate_and_clean(raw_data)
            assert cleaned["currency"] == "INR"

    @patch('fincli.extractors.transaction_extractor.get_llm_client')
    def test_extract_from_email_success(self, mock_get_client, sample_bedrock_response):
        """Test successful extraction from email."""
        # Mock Bedrock client
        mock_client = MagicMock()
        mock_client.extract_json.return_value = sample_bedrock_response
        mock_get_client.return_value = mock_client

        extractor = TransactionExtractor()

        email = EmailMessage(
            message_id="msg_123",
            subject="Transaction Alert",
            date="2025-11-15",
            snippet="Your card was debited for INR 100.50 at Amazon",
        )

        transaction = extractor.extract_from_email(email)

        assert transaction is not None
        assert isinstance(transaction, ExtractedTransaction)
        assert transaction.amount == 100.50
        assert transaction.merchant == "Amazon"

    @patch('fincli.extractors.transaction_extractor.get_llm_client')
    def test_extract_from_email_invalid_data(self, mock_get_client):
        """Test extraction with invalid data."""
        # Mock Bedrock client returning invalid data
        mock_client = MagicMock()
        mock_client.extract_json.return_value = {
            "amount": 100,
            "type": "debit",
            "merchant": "N/A",  # Invalid
            "date": "2025-11-15",
            "currency": "INR",
        }
        mock_get_client.return_value = mock_client

        extractor = TransactionExtractor()

        email = EmailMessage(
            message_id="msg_123",
            subject="Test",
            date="2025-11-15",
            snippet="Test snippet",
        )

        transaction = extractor.extract_from_email(email)

        # Should return None for invalid data
        assert transaction is None

    @patch('fincli.extractors.transaction_extractor.get_llm_client')
    def test_extract_batch(self, mock_get_client, sample_bedrock_response):
        """Test batch extraction."""
        mock_client = MagicMock()
        mock_client.extract_json.return_value = sample_bedrock_response
        mock_get_client.return_value = mock_client

        extractor = TransactionExtractor()

        emails = [
            EmailMessage(
                message_id=f"msg_{i}",
                subject="Transaction",
                date="2025-11-15",
                snippet="Test",
            )
            for i in range(3)
        ]

        results = extractor.extract_batch(emails)

        assert len(results) == 3
        assert all(isinstance(r, tuple) for r in results)
        assert all(isinstance(r[0], EmailMessage) for r in results)
