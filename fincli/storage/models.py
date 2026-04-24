"""
SQLAlchemy database models for FinCLI.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Index, LargeBinary, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Transaction(Base):
    """Model for storing transaction data extracted from emails."""

    __tablename__ = "transactions"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Email reference
    email_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Gmail message ID"
    )

    # Transaction details
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Transaction amount"
    )

    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Transaction type: debit or credit"
    )

    merchant: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Merchant or source name"
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="INR",
        comment="Currency code (e.g., INR, USD)"
    )

    transaction_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Date of transaction"
    )

    # Email metadata
    email_subject: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Email subject line"
    )

    email_snippet: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Email snippet/preview"
    )

    email_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Email received date"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Record creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Record last update timestamp"
    )

    # Additional fields
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Transaction category (e.g., Food & Dining, Shopping)"
    )

    payment_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Payment method (e.g., Credit Card, UPI, Cash)"
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Additional notes"
    )

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_date_type', 'transaction_date', 'transaction_type'),
        Index('idx_merchant_date', 'merchant', 'transaction_date'),
        Index('idx_amount_date', 'amount', 'transaction_date'),
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, "
            f"type={self.transaction_type}, "
            f"amount={self.amount} {self.currency}, "
            f"merchant='{self.merchant}', "
            f"date={self.transaction_date.strftime('%Y-%m-%d')})>"
        )

    def to_embedding_text(self) -> str:
        """Canonical text representation used for embedding — keep stable across re-indexes."""
        date_str = self.transaction_date.strftime('%Y-%m-%d')
        parts = [
            self.transaction_type,
            f"{self.currency} {self.amount}",
            f"at {self.merchant}",
            f"on {date_str}",
        ]
        if self.category:
            parts.append(f"category: {self.category}")
        if self.payment_method:
            parts.append(f"via {self.payment_method}")
        return " ".join(parts)

    def to_dict(self) -> dict:
        """Convert transaction to dictionary."""
        return {
            "id": self.id,
            "email_id": self.email_id,
            "amount": self.amount,
            "type": self.transaction_type,
            "merchant": self.merchant,
            "currency": self.currency,
            "transaction_date": self.transaction_date.isoformat(),
            "email_subject": self.email_subject,
            "email_snippet": self.email_snippet,
            "email_date": self.email_date.isoformat() if self.email_date else None,
            "category": self.category,
            "payment_method": self.payment_method,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TransactionEmbedding(Base):
    """
    RAG CONCEPT — Embeddings table:
    Each transaction gets a vector (list of floats) that encodes its semantic meaning.
    Stored as raw bytes (BLOB) and deserialized back to numpy arrays at query time.
    1:1 with Transaction — one embedding per transaction.
    """
    __tablename__ = "transaction_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # The actual vector — serialized float32 numpy array
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # What text was embedded — critical for debugging and re-indexing
    embedding_text: Mapped[str] = mapped_column(String(2000), nullable=False)

    # Track which model produced this embedding (vectors from different models are incompatible)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="nomic-embed-text")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<TransactionEmbedding(transaction_id={self.transaction_id}, model={self.model})>"
