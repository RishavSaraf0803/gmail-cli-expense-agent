"""
Startup validation and health checks.

Validates critical dependencies before app starts serving requests.
Fails fast if critical requirements are not met.
"""
from typing import List, Tuple
import sys

from fincli.config import get_settings
from fincli.storage.database import DatabaseManager
from fincli.exceptions import (
    ConfigurationError,
    DatabaseError,
    CriticalError
)
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


def validate_config() -> None:
    """
    Validate critical configuration.

    Raises:
        ConfigurationError: If configuration is invalid
    """
    settings = get_settings()
    errors = []

    # Check API authentication
    if settings.api_auth_enabled and not settings.api_key:
        errors.append(
            "API authentication is enabled but FINCLI_API_KEY is not set. "
            "Either set FINCLI_API_KEY or disable auth with FINCLI_API_AUTH_ENABLED=false"
        )

    # Check database URL
    if not settings.database_url:
        errors.append("FINCLI_DATABASE_URL is not set")

    # Check LLM provider configuration
    if settings.llm_provider not in ["ollama", "bedrock", "openai", "anthropic"]:
        errors.append(
            f"Invalid LLM provider: {settings.llm_provider}. "
            f"Must be one of: ollama, bedrock, openai, anthropic"
        )

    # Provider-specific validation
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        errors.append(
            "LLM provider is 'anthropic' but FINCLI_ANTHROPIC_API_KEY is not set"
        )

    if settings.llm_provider == "openai" and not settings.openai_api_key:
        errors.append(
            "LLM provider is 'openai' but FINCLI_OPENAI_API_KEY is not set"
        )

    # Check rate limits are sane
    if settings.rate_limit_per_minute > settings.rate_limit_per_hour:
        errors.append(
            f"Rate limit per minute ({settings.rate_limit_per_minute}) cannot be "
            f"greater than rate limit per hour ({settings.rate_limit_per_hour})"
        )

    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error("config_validation_failed", errors=errors)
        raise ConfigurationError(
            error_msg,
            details={"validation_errors": errors}
        )

    logger.info("config_validated", provider=settings.llm_provider)


def validate_database() -> None:
    """
    Validate database connectivity and schema.

    Raises:
        DatabaseError: If database is not accessible
    """
    try:
        db = DatabaseManager()

        # Test connection
        with db.get_session() as session:
            session.execute("SELECT 1")

        logger.info("database_validated", url=db.database_url)

    except Exception as e:
        error_msg = f"Database validation failed: {str(e)}"
        logger.error("database_validation_failed", error=str(e), exc_info=True)
        raise DatabaseError(
            error_msg,
            original_error=e,
            details={"database_url": str(get_settings().database_url)}
        )


def validate_llm_provider() -> Tuple[bool, str]:
    """
    Validate LLM provider configuration (non-critical).

    Returns:
        Tuple of (success: bool, message: str)
    """
    settings = get_settings()

    try:
        from fincli.clients.llm_factory import get_llm_client

        client = get_llm_client(use_case="default")
        is_healthy = client.health_check()

        if is_healthy:
            logger.info(
                "llm_provider_validated",
                provider=settings.llm_provider
            )
            return True, f"LLM provider '{settings.llm_provider}' is healthy"
        else:
            logger.warning(
                "llm_provider_unhealthy",
                provider=settings.llm_provider
            )
            return False, f"LLM provider '{settings.llm_provider}' health check failed"

    except Exception as e:
        logger.warning(
            "llm_provider_validation_failed",
            provider=settings.llm_provider,
            error=str(e)
        )
        return False, f"LLM provider validation failed: {str(e)}"


def run_startup_checks(fail_on_llm_error: bool = False) -> None:
    """
    Run all startup validation checks.

    This is called during app startup to ensure all critical
    dependencies are available before serving requests.

    Args:
        fail_on_llm_error: If True, fail if LLM provider is unavailable.
                          If False, only warn (app can still serve cached data).

    Raises:
        CriticalError: If any critical check fails
    """
    logger.info("startup_checks_begin")

    try:
        # Critical checks - must pass
        logger.info("validating_config")
        validate_config()

        logger.info("validating_database")
        validate_database()

        # Non-critical checks - warn but don't fail
        logger.info("validating_llm_provider")
        llm_ok, llm_msg = validate_llm_provider()

        if not llm_ok:
            if fail_on_llm_error:
                raise CriticalError(
                    f"LLM provider validation failed: {llm_msg}",
                    details={"provider": get_settings().llm_provider}
                )
            else:
                logger.warning(
                    "llm_provider_degraded",
                    message="App will start but LLM features may be unavailable",
                    details=llm_msg
                )

        logger.info("startup_checks_complete", all_healthy=llm_ok)

    except CriticalError:
        # Re-raise critical errors
        raise
    except Exception as e:
        # Wrap unexpected errors as critical
        logger.error("startup_check_unexpected_error", error=str(e), exc_info=True)
        raise CriticalError(
            f"Unexpected error during startup checks: {str(e)}",
            original_error=e
        )


def fail_fast_on_startup_error():
    """
    Decorator to fail fast if startup validation fails.

    Usage:
        @fail_fast_on_startup_error()
        def create_app():
            run_startup_checks()
            # ... rest of app creation
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CriticalError as e:
                logger.error(
                    "app_startup_failed",
                    error=str(e),
                    details=e.details,
                    exc_info=True
                )
                print(f"\n❌ CRITICAL ERROR - App cannot start:\n{e.message}\n", file=sys.stderr)
                if e.details:
                    print(f"Details: {e.details}\n", file=sys.stderr)
                sys.exit(1)
        return wrapper
    return decorator
