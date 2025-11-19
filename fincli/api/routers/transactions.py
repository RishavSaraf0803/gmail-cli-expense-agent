"""
Transaction management API endpoints.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from fincli.api.schemas import (
    TransactionResponse,
    TransactionListResponse,
    TransactionCreate,
    TransactionUpdateRequest,
    ErrorResponse
)
from fincli.api.dependencies import get_db_manager
from fincli.storage.database import DatabaseManager
from fincli.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    responses={
        404: {"model": ErrorResponse, "description": "Transaction not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List transactions",
    description="Get a paginated list of transactions with optional filtering"
)
async def list_transactions(
    limit: int = Query(default=10, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    transaction_type: Optional[str] = Query(
        default=None,
        pattern="^(debit|credit)$",
        description="Filter by transaction type"
    ),
    merchant: Optional[str] = Query(default=None, description="Filter by merchant name (fuzzy match)"),
    start_date: Optional[datetime] = Query(default=None, description="Filter by start date (inclusive)"),
    end_date: Optional[datetime] = Query(default=None, description="Filter by end date (inclusive)"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Retrieve transactions with optional filtering and pagination.

    **Filters:**
    - `transaction_type`: Filter by 'debit' or 'credit'
    - `merchant`: Fuzzy search by merchant name
    - `start_date` and `end_date`: Filter by date range
    """
    try:
        # Apply filters
        if start_date and end_date:
            transactions = db.get_transactions_by_date_range(
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
            # Apply offset manually for date range queries
            transactions = transactions[offset:offset + limit] if offset else transactions[:limit]
        elif transaction_type:
            transactions = db.get_transactions_by_type(
                transaction_type=transaction_type,
                limit=limit
            )
            transactions = transactions[offset:offset + limit] if offset else transactions[:limit]
        elif merchant:
            transactions = db.get_transactions_by_merchant(
                merchant=merchant,
                limit=limit
            )
            transactions = transactions[offset:offset + limit] if offset else transactions[:limit]
        else:
            transactions = db.get_all_transactions(limit=limit, offset=offset)

        # Get total count
        total = db.count_transactions()

        logger.info(
            "transactions_listed",
            count=len(transactions),
            limit=limit,
            offset=offset
        )

        return TransactionListResponse(
            items=[TransactionResponse.model_validate(t) for t in transactions],
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error("transactions_list_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transactions: {str(e)}"
        )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get transaction by ID",
    description="Retrieve a single transaction by its ID"
)
async def get_transaction(
    transaction_id: int,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get a specific transaction by ID."""
    try:
        # Get all transactions and find by ID
        # Note: DatabaseManager doesn't have get_by_id, so we'll query all
        transactions = db.get_all_transactions()
        transaction = next((t for t in transactions if t.id == transaction_id), None)

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with ID {transaction_id} not found"
            )

        logger.info("transaction_retrieved", transaction_id=transaction_id)
        return TransactionResponse.model_validate(transaction)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("transaction_get_failed", transaction_id=transaction_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transaction: {str(e)}"
        )


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create transaction",
    description="Manually create a new transaction"
)
async def create_transaction(
    transaction: TransactionCreate,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Create a new transaction manually.

    This endpoint allows manual transaction entry without email processing.
    """
    try:
        created = db.add_transaction(
            email_id=transaction.email_id,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type,
            merchant=transaction.merchant,
            transaction_date=transaction.transaction_date,
            currency=transaction.currency,
            email_subject=transaction.email_subject,
            email_snippet=transaction.email_snippet,
            email_date=transaction.email_date,
            category=transaction.category,
            notes=transaction.notes
        )

        if created is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transaction with email_id '{transaction.email_id}' already exists"
            )

        logger.info(
            "transaction_created",
            email_id=transaction.email_id,
            merchant=transaction.merchant
        )
        return TransactionResponse.model_validate(created)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("transaction_create_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transaction: {str(e)}"
        )


@router.get(
    "/email/{email_id}",
    response_model=TransactionResponse,
    summary="Get transaction by email ID",
    description="Retrieve a transaction by its associated Gmail message ID"
)
async def get_transaction_by_email(
    email_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get a transaction by its Gmail message ID."""
    try:
        transaction = db.get_transaction_by_email_id(email_id)

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction with email_id '{email_id}' not found"
            )

        logger.info("transaction_retrieved_by_email", email_id=email_id)
        return TransactionResponse.model_validate(transaction)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("transaction_get_by_email_failed", email_id=email_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transaction: {str(e)}"
        )
