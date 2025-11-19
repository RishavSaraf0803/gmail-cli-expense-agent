"""
Operations API endpoints (fetch, init, health).
"""
import uuid
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from dateutil import parser as date_parser

from fincli.api.schemas import (
    FetchRequest,
    FetchResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    InitResponse,
    ErrorResponse
)
from fincli.api.dependencies import (
    get_db_manager,
    get_gmail,
    get_llm,
    get_extractor
)
from fincli.storage.database import DatabaseManager
from fincli.clients.gmail_client import GmailClient
from fincli.clients.base_llm_client import BaseLLMClient
from fincli.extractors.transaction_extractor import TransactionExtractor
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(
    tags=["operations"],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)

# In-memory conversation storage (in production, use Redis or database)
conversations: Dict[str, list] = {}


def parse_email_date(date_str: str) -> datetime:
    """
    Parse email date string to datetime object.

    Args:
        date_str: Email date string from Gmail headers

    Returns:
        Parsed datetime object, or current time if parsing fails
    """
    if not date_str or date_str == 'Unknown':
        return datetime.now()

    try:
        return date_parser.parse(date_str)
    except Exception as e:
        logger.warning("email_date_parse_failed", date_str=date_str, error=str(e))
        return datetime.now()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the API and its dependencies"
)
async def health_check(
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Comprehensive health check for all services.

    **Checks:**
    - API service status
    - Database connectivity
    - Gmail API availability (optional)
    - Bedrock API availability (optional)
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "gmail": None,
        "llm": None,
        "llm_provider": settings.llm_provider,
        "version": "1.0.0"
    }

    # Check database
    try:
        db.count_transactions()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check Gmail (optional - don't fail health check if not configured)
    try:
        gmail = get_gmail()
        gmail.get_user_profile()
        health_status["gmail"] = "connected"
    except Exception as e:
        health_status["gmail"] = f"not configured or error"
        logger.debug("gmail_health_check_failed", error=str(e))

    # Check LLM (optional - don't fail health check if not configured)
    try:
        llm = get_llm()
        if llm.health_check():
            health_status["llm"] = "connected"
        else:
            health_status["llm"] = "health check failed"
    except Exception as e:
        health_status["llm"] = f"not configured or error"
        logger.debug("llm_health_check_failed", error=str(e))

    logger.info("health_check_completed", status=health_status["status"])
    return HealthResponse(**health_status)


@router.post(
    "/init",
    response_model=InitResponse,
    summary="Initialize application",
    description="Initialize database tables and test API connections"
)
async def initialize(
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Initialize the application by creating database tables and testing connections.

    **Actions:**
    - Create database tables
    - Test Gmail API authentication
    - Test Bedrock API connection
    """
    result = {
        "database_created": False,
        "gmail_authenticated": False,
        "llm_connected": False,
        "message": ""
    }

    try:
        # Create database tables
        db.create_tables()
        result["database_created"] = True
        logger.info("database_tables_created")
    except Exception as e:
        result["message"] += f"Database initialization failed: {str(e)}. "
        logger.error("database_init_failed", error=str(e))

    # Test Gmail
    try:
        gmail = get_gmail()
        profile = gmail.get_user_profile()
        result["gmail_authenticated"] = True
        logger.info("gmail_test_successful", email=profile.get("emailAddress"))
    except Exception as e:
        result["message"] += f"Gmail test failed: {str(e)}. "
        logger.error("gmail_test_failed", error=str(e))

    # Test LLM
    try:
        llm = get_llm()
        if llm.health_check():
            result["llm_connected"] = True
            logger.info("llm_test_successful", provider=settings.llm_provider)
        else:
            result["message"] += f"LLM health check failed. "
    except Exception as e:
        result["message"] += f"LLM test failed: {str(e)}. "
        logger.error("llm_test_failed", error=str(e))

    if all([result["database_created"], result["gmail_authenticated"], result["llm_connected"]]):
        result["message"] = "All systems initialized successfully"
    elif not result["message"]:
        result["message"] = "Partial initialization completed"

    logger.info("initialization_completed", **result)
    return InitResponse(**result)


@router.post(
    "/fetch",
    response_model=FetchResponse,
    summary="Fetch emails and extract transactions",
    description="Fetch emails from Gmail and extract transaction data using AI"
)
async def fetch_emails(
    request: FetchRequest,
    db: DatabaseManager = Depends(get_db_manager),
    gmail: GmailClient = Depends(get_gmail),
    extractor: TransactionExtractor = Depends(get_extractor)
):
    """
    Fetch emails and extract transactions.

    **Parameters:**
    - `max_emails`: Maximum number of emails to fetch (default: 20, max: 500)
    - `force`: Force re-processing of existing emails (default: false)

    **Process:**
    1. Fetch emails from Gmail matching configured query
    2. Extract transaction data using Claude AI
    3. Store valid transactions in database
    4. Return summary of results
    """
    try:
        logger.info(
            "fetch_started",
            max_emails=request.max_emails,
            force=request.force
        )

        # Fetch emails
        emails = gmail.fetch_messages(
            query=settings.email_query,
            max_results=request.max_emails
        )

        logger.info("emails_fetched", count=len(emails))

        # Extract and save transactions
        new_count = 0
        skipped_count = 0
        error_count = 0

        for email, transaction in extractor.extract_batch(emails):
            if transaction is None:
                error_count += 1
                continue

            # Save to database
            saved = db.add_transaction(
                email_id=email.message_id,
                amount=transaction.amount,
                transaction_type=transaction.transaction_type,
                merchant=transaction.merchant,
                transaction_date=transaction.transaction_date,
                currency=transaction.currency,
                email_subject=email.subject,
                email_snippet=email.snippet,
                email_date=parse_email_date(email.date)
            )

            if saved:
                new_count += 1
            else:
                skipped_count += 1

        total_in_db = db.count_transactions()

        logger.info(
            "fetch_completed",
            new=new_count,
            skipped=skipped_count,
            errors=error_count,
            total=total_in_db
        )

        return FetchResponse(
            new_transactions=new_count,
            skipped_duplicates=skipped_count,
            errors=error_count,
            total_in_db=total_in_db
        )
    except Exception as e:
        logger.error("fetch_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email fetch failed: {str(e)}"
        )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask questions about expenses",
    description="Natural language Q&A about your transactions using AI"
)
async def chat(
    request: ChatRequest,
    db: DatabaseManager = Depends(get_db_manager),
    llm: BaseLLMClient = Depends(get_llm)
):
    """
    Ask natural language questions about your expenses.

    **Examples:**
    - "How much did I spend last month?"
    - "What are my top 5 merchants?"
    - "Show me all transactions over 1000 rupees"

    The AI will analyze your transaction data and provide answers.
    """
    try:
        # Get conversation ID or create new one
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Get all transactions for context
        transactions = db.get_all_transactions(limit=100)

        # Build context
        transaction_context = "\n".join([
            f"- {t.transaction_date.strftime('%Y-%m-%d')}: "
            f"{t.transaction_type.upper()} {t.currency} {t.amount} at {t.merchant}"
            for t in transactions[:50]  # Limit to avoid token limits
        ])

        # Build prompt
        system_prompt = f"""You are a helpful financial assistant analyzing transaction data.

Current transactions in database:
{transaction_context}

Answer the user's question based on this transaction data. Be concise and specific.
If you need to perform calculations, do them accurately.
"""

        # Get response from LLM
        answer = llm.generate_text(
            prompt=request.question,
            system_prompt=system_prompt,
            max_tokens=1000,
            temperature=0.3
        )

        # Store conversation (simplified - use database in production)
        if conversation_id not in conversations:
            conversations[conversation_id] = []

        conversations[conversation_id].append({
            "question": request.question,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(
            "chat_completed",
            conversation_id=conversation_id,
            question_length=len(request.question),
            answer_length=len(answer)
        )

        return ChatResponse(
            question=request.question,
            answer=answer,
            conversation_id=conversation_id,
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error("chat_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat request failed: {str(e)}"
        )
