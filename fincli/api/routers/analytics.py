"""
Analytics and reporting API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from fincli.api.schemas import (
    SummaryResponse,
    TopMerchantsResponse,
    MerchantStats,
    ErrorResponse
)
from fincli.api.dependencies import get_db_manager
from fincli.storage.database import DatabaseManager
from fincli.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Get financial summary",
    description="Get overall financial summary including totals and net amount"
)
async def get_summary(
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Retrieve comprehensive financial summary.

    **Returns:**
    - Total spent (debits)
    - Total credited (credits)
    - Net amount (credits - debits)
    - Total transaction count
    """
    try:
        total_spent = db.get_total_by_type("debit")
        total_credited = db.get_total_by_type("credit")
        total_count = db.count_transactions()

        net = total_credited - total_spent

        logger.info(
            "summary_retrieved",
            total_spent=total_spent,
            total_credited=total_credited,
            net=net
        )

        return SummaryResponse(
            total_spent=total_spent,
            total_credited=total_credited,
            net=net,
            total_transactions=total_count,
            currency="INR"
        )
    except Exception as e:
        logger.error("summary_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summary: {str(e)}"
        )


@router.get(
    "/merchants/top",
    response_model=TopMerchantsResponse,
    summary="Get top merchants",
    description="Get top merchants by transaction count"
)
async def get_top_merchants(
    limit: int = Query(default=10, ge=1, le=100, description="Number of merchants to return"),
    transaction_type: Optional[str] = Query(
        default=None,
        pattern="^(debit|credit)$",
        description="Filter by transaction type"
    ),
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Retrieve top merchants ranked by transaction count.

    **Parameters:**
    - `limit`: Number of top merchants to return (default: 10)
    - `transaction_type`: Optional filter for 'debit' or 'credit' transactions
    """
    try:
        # Get top merchants as tuples (merchant, count)
        top_merchants_data = db.get_top_merchants(
            transaction_type=transaction_type,
            limit=limit
        )

        # Convert to MerchantStats objects
        merchants = []
        for merchant_name, count in top_merchants_data:
            # Calculate total amount for this merchant
            merchant_transactions = db.get_transactions_by_merchant(merchant=merchant_name)
            if transaction_type:
                merchant_transactions = [
                    t for t in merchant_transactions
                    if t.transaction_type == transaction_type
                ]

            total_amount = sum(t.amount for t in merchant_transactions)

            merchants.append(
                MerchantStats(
                    merchant=merchant_name,
                    transaction_count=count,
                    total_amount=total_amount
                )
            )

        logger.info(
            "top_merchants_retrieved",
            count=len(merchants),
            transaction_type=transaction_type
        )

        return TopMerchantsResponse(
            merchants=merchants,
            transaction_type=transaction_type
        )
    except Exception as e:
        logger.error("top_merchants_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve top merchants: {str(e)}"
        )
