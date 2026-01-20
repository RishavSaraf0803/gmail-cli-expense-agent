"""
Main FastAPI application factory.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

from fincli.api.routers import transactions, analytics, operations, health
from fincli.api.dependencies import get_db_manager
from fincli.api.middleware.auth import verify_api_key
from fincli.api.middleware.rate_limiter import rate_limit_dependency
from fincli.config import get_settings
from fincli.utils.logger import get_logger, setup_logging
from fincli.startup import run_startup_checks
from fincli.exceptions import (
    FinCLIException,
    CriticalError,
    ClientError,
    AuthenticationError,
    ValidationError,
    RateLimitError
)

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance

    Raises:
        CriticalError: If startup validation fails (app will not start)
    """
    # Startup
    logger.info("api_starting", version="1.0.0")

    # Setup logging
    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format
    )

    # Run startup checks - FAIL FAST if critical dependencies unavailable
    # This will raise CriticalError and prevent app from starting
    run_startup_checks(fail_on_llm_error=False)

    # Create database tables (only runs if startup checks passed)
    db = get_db_manager()
    db.create_tables()
    logger.info("database_tables_ready")

    logger.info("api_startup_complete", version="1.0.0")

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

    # Middleware to add rate limit headers to responses
    @app.middleware("http")
    async def add_rate_limit_headers(request: Request, call_next):
        """Add rate limit headers to response if available."""
        response = await call_next(request)

        # Add rate limit headers if they were set by rate limiter
        if hasattr(request.state, "rate_limit_headers"):
            for header, value in request.state.rate_limit_headers.items():
                response.headers[header] = value

        return response

    # Include routers
    app.include_router(health.router)  # Health checks at root level (no auth, no rate limit)
    app.include_router(
        operations.router,
        dependencies=[Depends(verify_api_key), Depends(rate_limit_dependency)]
    )
    app.include_router(
        transactions.router,
        prefix="/api/v1",
        dependencies=[Depends(verify_api_key), Depends(rate_limit_dependency)]
    )
    app.include_router(
        analytics.router,
        prefix="/api/v1",
        dependencies=[Depends(verify_api_key), Depends(rate_limit_dependency)]
    )

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "FinCLI API",
            "version": "1.0.0",
            "description": "Financial Transaction Tracker API",
            "docs_url": "/docs",
            "health_url": "/health",
            "ready_url": "/ready",
            "startup_url": "/startup"
        }

    # Custom exception handlers
    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(request: Request, exc: AuthenticationError):
        """Handle authentication errors."""
        logger.warning(
            "authentication_error",
            path=request.url.path,
            error=str(exc)
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=exc.to_dict()
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """Handle validation errors."""
        logger.warning(
            "validation_error",
            path=request.url.path,
            error=str(exc),
            details=exc.details
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=exc.to_dict()
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_error_handler(request: Request, exc: RateLimitError):
        """Handle rate limit errors."""
        logger.warning(
            "rate_limit_error",
            path=request.url.path,
            retry_after=exc.retry_after
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=exc.to_dict(),
            headers={"Retry-After": str(exc.retry_after)}
        )

    @app.exception_handler(ClientError)
    async def client_error_handler(request: Request, exc: ClientError):
        """Handle generic client errors."""
        logger.warning(
            "client_error",
            path=request.url.path,
            error=str(exc)
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=exc.to_dict()
        )

    @app.exception_handler(FinCLIException)
    async def fincli_exception_handler(request: Request, exc: FinCLIException):
        """Handle application-specific errors."""
        logger.error(
            "fincli_error",
            path=request.url.path,
            error_type=type(exc).__name__,
            error=str(exc),
            details=exc.details,
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=exc.to_dict()
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions."""
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
            error=str(exc),
            exc_info=True
        )

        # In development, show full error
        # In production, hide details for security
        if settings.debug:
            error_detail = {
                "error": "InternalServerError",
                "message": str(exc),
                "type": type(exc).__name__,
                "path": request.url.path
            }
        else:
            error_detail = {
                "error": "InternalServerError",
                "message": "An internal server error occurred. Please contact support.",
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_detail
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
