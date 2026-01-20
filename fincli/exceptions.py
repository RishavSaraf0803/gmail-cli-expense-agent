"""
Custom exception hierarchy for FinCLI.

Exceptions are categorized by severity:
- Critical: Must fail fast, cannot continue (DB, config)
- Recoverable: Can retry or degrade gracefully (LLM, external APIs)
- Client: User error, return 4xx (bad request, auth)
"""
from typing import Optional, Dict, Any


class FinCLIException(Exception):
    """Base exception for all FinCLI errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            details: Additional context (dict)
            original_error: Original exception if wrapping
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.original_error = original_error

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dict for API responses.

        Returns:
            Dict with error details
        """
        result = {
            "error": self.__class__.__name__,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


# =============================================================================
# CRITICAL ERRORS - Must fail fast, cannot continue
# =============================================================================

class CriticalError(FinCLIException):
    """
    Critical error that requires immediate shutdown.

    Use for: Database unavailable, critical config missing, corrupt data.
    App should NOT continue serving requests with these errors.
    """
    pass


class ConfigurationError(CriticalError):
    """
    Configuration error preventing app startup.

    Examples:
    - Missing required environment variables
    - Invalid configuration values
    - Conflicting settings
    """
    pass


class DatabaseError(CriticalError):
    """
    Database error preventing core functionality.

    Examples:
    - Cannot connect to database
    - Schema mismatch
    - Migration failure
    """
    pass


# =============================================================================
# RECOVERABLE ERRORS - Can retry or degrade gracefully
# =============================================================================

class RecoverableError(FinCLIException):
    """
    Recoverable error that can be retried or handled gracefully.

    Use for: External API failures, temporary network issues, rate limits.
    """
    pass


class LLMError(RecoverableError):
    """
    LLM provider error.

    Examples:
    - API timeout
    - Rate limit from provider
    - Model unavailable
    - Invalid response format
    """
    pass


class GmailAPIError(RecoverableError):
    """
    Gmail API error.

    Examples:
    - Rate limit exceeded
    - Network timeout
    - Invalid credentials (401)
    - Quota exceeded
    """
    pass


class ExtractionError(RecoverableError):
    """
    Transaction extraction error.

    Examples:
    - Could not parse email content
    - Missing required fields
    - Invalid data format
    """
    pass


class CacheError(RecoverableError):
    """
    Cache operation error (non-critical).

    Cache failures should not break the app, just reduce performance.
    """
    pass


# =============================================================================
# CLIENT ERRORS - User/client made a mistake (4xx responses)
# =============================================================================

class ClientError(FinCLIException):
    """
    Client error (bad request, auth failure, etc).

    Use for: Invalid input, missing auth, validation errors.
    Return 4xx status codes.
    """
    pass


class AuthenticationError(ClientError):
    """
    Authentication/authorization error.

    Examples:
    - Missing API key
    - Invalid API key
    - Expired token
    """
    pass


class ValidationError(ClientError):
    """
    Input validation error.

    Examples:
    - Missing required field
    - Invalid format
    - Out of range value
    """
    pass


class RateLimitError(ClientError):
    """
    Rate limit exceeded error.

    Client is making too many requests.
    """
    def __init__(
        self,
        message: str,
        retry_after: int,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retry
            details: Additional details
        """
        super().__init__(message, details)
        self.retry_after = retry_after

    def to_dict(self) -> Dict[str, Any]:
        """Include retry_after in response."""
        result = super().to_dict()
        result["retry_after_seconds"] = self.retry_after
        return result


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_critical(error: Exception) -> bool:
    """
    Check if error is critical (requires fail-fast).

    Args:
        error: Exception to check

    Returns:
        True if critical, False otherwise
    """
    return isinstance(error, CriticalError)


def is_recoverable(error: Exception) -> bool:
    """
    Check if error is recoverable (can retry).

    Args:
        error: Exception to check

    Returns:
        True if recoverable, False otherwise
    """
    return isinstance(error, RecoverableError)


def wrap_error(
    error: Exception,
    message: str,
    error_class: type = FinCLIException
) -> FinCLIException:
    """
    Wrap an exception with additional context.

    Args:
        error: Original exception
        message: Additional context message
        error_class: Exception class to wrap with

    Returns:
        Wrapped exception
    """
    return error_class(
        message=message,
        original_error=error,
        details={"original_error_type": type(error).__name__}
    )
