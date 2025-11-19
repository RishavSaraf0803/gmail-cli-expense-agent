"""
Pydantic schemas for API request/response models.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class TransactionResponse(BaseModel):
    """Response model for a single transaction."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique transaction ID")
    email_id: str = Field(..., description="Gmail message ID")
    amount: float = Field(..., description="Transaction amount")
    transaction_type: str = Field(..., description="Transaction type (debit/credit)")
    merchant: str = Field(..., description="Merchant name")
    currency: str = Field(default="INR", description="Currency code")
    transaction_date: datetime = Field(..., description="Date of transaction")
    email_subject: Optional[str] = Field(None, description="Email subject")
    email_snippet: Optional[str] = Field(None, description="Email snippet")
    email_date: Optional[datetime] = Field(None, description="Email date")
    category: Optional[str] = Field(None, description="Transaction category")
    notes: Optional[str] = Field(None, description="Additional notes")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TransactionListResponse(BaseModel):
    """Response model for paginated transaction list."""

    items: List[TransactionResponse] = Field(..., description="List of transactions")
    total: int = Field(..., description="Total number of transactions")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Number of items skipped")


class TransactionCreate(BaseModel):
    """Request model for creating a transaction."""

    email_id: str = Field(..., description="Gmail message ID")
    amount: float = Field(..., gt=0, description="Transaction amount (must be positive)")
    transaction_type: str = Field(..., pattern="^(debit|credit)$", description="Transaction type")
    merchant: str = Field(..., min_length=1, description="Merchant name")
    transaction_date: datetime = Field(..., description="Date of transaction")
    currency: str = Field(default="INR", description="Currency code")
    email_subject: Optional[str] = None
    email_snippet: Optional[str] = None
    email_date: Optional[datetime] = None
    category: Optional[str] = None
    notes: Optional[str] = None


class SummaryResponse(BaseModel):
    """Response model for financial summary."""

    total_spent: float = Field(..., description="Total debit amount")
    total_credited: float = Field(..., description="Total credit amount")
    net: float = Field(..., description="Net amount (credit - debit)")
    total_transactions: int = Field(..., description="Total number of transactions")
    currency: str = Field(default="INR", description="Currency code")


class MerchantStats(BaseModel):
    """Statistics for a single merchant."""

    merchant: str = Field(..., description="Merchant name")
    transaction_count: int = Field(..., description="Number of transactions")
    total_amount: float = Field(..., description="Total amount spent/received")


class TopMerchantsResponse(BaseModel):
    """Response model for top merchants."""

    merchants: List[MerchantStats] = Field(..., description="List of top merchants")
    transaction_type: Optional[str] = Field(None, description="Filter applied (debit/credit)")


class FetchRequest(BaseModel):
    """Request model for fetching emails."""

    max_emails: int = Field(default=20, ge=1, le=500, description="Maximum emails to fetch")
    force: bool = Field(default=False, description="Force re-processing of existing emails")


class FetchResponse(BaseModel):
    """Response model for email fetch operation."""

    new_transactions: int = Field(..., description="Number of new transactions added")
    skipped_duplicates: int = Field(..., description="Number of duplicates skipped")
    errors: int = Field(..., description="Number of processing errors")
    total_in_db: int = Field(..., description="Total transactions in database")


class ChatRequest(BaseModel):
    """Request model for chat/Q&A."""

    question: str = Field(..., min_length=1, max_length=1000, description="User question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for multi-turn chat")


class ChatResponse(BaseModel):
    """Response model for chat/Q&A."""

    question: str = Field(..., description="User question")
    answer: str = Field(..., description="AI-generated answer")
    conversation_id: str = Field(..., description="Conversation ID for follow-up questions")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str = Field(..., description="Service status")
    database: str = Field(..., description="Database connection status")
    gmail: Optional[str] = Field(None, description="Gmail API status")
    llm: Optional[str] = Field(None, description="LLM service status")
    llm_provider: Optional[str] = Field(None, description="LLM provider (bedrock/ollama)")
    version: str = Field(..., description="API version")


class InitResponse(BaseModel):
    """Response model for initialization."""

    database_created: bool = Field(..., description="Database tables created successfully")
    gmail_authenticated: bool = Field(..., description="Gmail authentication successful")
    llm_connected: bool = Field(..., description="LLM service connection successful")
    message: str = Field(..., description="Status message")


class ErrorResponse(BaseModel):
    """Response model for errors."""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")


class TransactionUpdateRequest(BaseModel):
    """Request model for updating a transaction."""

    category: Optional[str] = Field(None, description="Transaction category")
    notes: Optional[str] = Field(None, description="Additional notes")
    merchant: Optional[str] = Field(None, min_length=1, description="Merchant name")
