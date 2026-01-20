"""
API Key authentication middleware for securing API endpoints.
"""
from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
from typing import Optional, Set
import secrets

from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Define API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# Paths that don't require authentication
EXEMPT_PATHS: Set[str] = {
    "/",
    "/health",
    "/ready",
    "/startup",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def is_path_exempt(path: str) -> bool:
    """
    Check if path is exempt from authentication.

    Args:
        path: Request path

    Returns:
        True if exempt, False otherwise
    """
    # Exact match
    if path in EXEMPT_PATHS:
        return True

    # Prefix match for docs
    if path.startswith(("/docs", "/redoc", "/openapi")):
        return True

    return False


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key against configured keys.

    Args:
        api_key: API key to validate

    Returns:
        True if valid, False otherwise
    """
    if not api_key:
        return False

    # Get valid API keys from config
    valid_keys = getattr(settings, 'api_keys', set())

    # If no keys configured, check single key
    single_key = getattr(settings, 'api_key', None)
    if single_key:
        valid_keys = {single_key}

    # If still no keys configured, REJECT (fail secure)
    if not valid_keys:
        logger.warning(
            "api_key_validation_no_keys_configured",
            message="No API keys configured - rejecting all requests"
        )
        return False

    # Constant-time comparison to prevent timing attacks
    return any(secrets.compare_digest(api_key, valid_key) for valid_key in valid_keys)


async def verify_api_key(request: Request, api_key: Optional[str] = None):
    """
    Dependency to verify API key for protected endpoints.

    Args:
        request: FastAPI request
        api_key: API key from header

    Raises:
        HTTPException: 401 if authentication fails

    Returns:
        API key if valid
    """
    path = request.url.path

    # Skip auth if disabled (development only!)
    if not settings.api_auth_enabled:
        logger.warning(
            "api_auth_disabled",
            message="API authentication is DISABLED - this is insecure!"
        )
        return None

    # Skip auth for exempt paths
    if is_path_exempt(path):
        return None

    # Extract API key from header
    if not api_key:
        api_key = request.headers.get("X-API-Key")

    # Validate
    if not api_key:
        logger.warning(
            "api_key_missing",
            path=path,
            client_ip=request.client.host if request.client else "unknown"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not validate_api_key(api_key):
        logger.warning(
            "api_key_invalid",
            path=path,
            client_ip=request.client.host if request.client else "unknown",
            key_prefix=api_key[:8] + "..." if len(api_key) > 8 else "***"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    logger.debug(
        "api_key_validated",
        path=path,
        key_prefix=api_key[:8] + "..."
    )

    return api_key


def generate_api_key() -> str:
    """
    Generate a secure random API key.

    Returns:
        Hex-encoded random API key (64 characters)
    """
    return secrets.token_hex(32)


if __name__ == "__main__":
    # Utility to generate API keys
    print("Generated API Key:")
    print(generate_api_key())
    print("\nAdd to .env file:")
    print(f"FINCLI_API_KEY={generate_api_key()}")
