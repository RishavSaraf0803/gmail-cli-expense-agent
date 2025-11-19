"""
Main FastAPI application factory.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

from fincli.api.routers import transactions, analytics, operations
from fincli.api.dependencies import get_db_manager
from fincli.config import get_settings
from fincli.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("api_starting", version="1.0.0")

    # Setup logging
    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format
    )

    # Initialize database
    try:
        db = get_db_manager()
        db.create_tables()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))

    yield

    # Shutdown
    logger.info("api_shutting_down")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="FinCLI API",
        description="""
# FinCLI - Financial Transaction Tracker API

Automatically extract and analyze financial transactions from Gmail using AI.

## Features

- 📧 **Email Integration**: Connect to Gmail and fetch transaction emails
- 🤖 **AI Extraction**: Use Claude AI to extract structured transaction data
- 💾 **Transaction Storage**: Store and manage transactions in SQLite database
- 📊 **Analytics**: Get spending summaries and merchant insights
- 💬 **Natural Language Q&A**: Ask questions about your expenses in plain English

## Authentication

Currently, the API uses OAuth2 for Gmail access. Credentials are configured via environment variables.

## Rate Limits

- Gmail API: Subject to Google's quota limits
- Bedrock API: Subject to AWS rate limits and configured retry logic

## Common Workflows

### 1. Initial Setup
```
POST /init - Initialize database and test connections
```

### 2. Fetch Transactions
```
POST /fetch - Fetch emails and extract transactions
```

### 3. View Data
```
GET /transactions - List all transactions
GET /analytics/summary - View spending summary
GET /analytics/merchants/top - See top merchants
```

### 4. Ask Questions
```
POST /chat - Ask natural language questions about expenses
```
        """,
        version="1.0.0",
        contact={
            "name": "FinCLI",
            "url": "https://github.com/yourusername/fincli",
        },
        license_info={
            "name": "MIT",
        },
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions."""
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred",
                "error": str(exc) if settings.debug else "Internal server error"
            }
        )

    logger.info("fastapi_app_created")
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "fincli.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )
