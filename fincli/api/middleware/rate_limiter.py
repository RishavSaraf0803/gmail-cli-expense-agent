"""
Token bucket rate limiter for API endpoints.

Uses in-memory storage for simplicity. For production with multiple instances,
replace with Redis-backed storage.
"""
import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from threading import Lock
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: int  # Maximum tokens
    tokens: float  # Current tokens
    refill_rate: float  # Tokens per second
    last_refill: float  # Last refill timestamp

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens consumed, False if insufficient tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now

    def time_until_token(self) -> float:
        """
        Calculate seconds until next token available.

        Returns:
            Seconds until next token
        """
        if self.tokens >= 1:
            return 0.0

        tokens_needed = 1 - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """
    In-memory rate limiter using token bucket algorithm.

    Thread-safe for single-instance deployments.
    For multi-instance, replace with Redis-backed implementation.
    """

    def __init__(
        self,
        requests_per_minute: int = 100,
        requests_per_hour: int = 1000,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Max requests per minute per key
            requests_per_hour: Max requests per hour per key
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Storage: {api_key: (minute_bucket, hour_bucket)}
        self._buckets: Dict[str, Tuple[TokenBucket, TokenBucket]] = {}
        self._lock = Lock()

        logger.info(
            "rate_limiter_initialized",
            rpm=requests_per_minute,
            rph=requests_per_hour
        )

    def _get_or_create_buckets(self, key: str) -> Tuple[TokenBucket, TokenBucket]:
        """
        Get or create token buckets for a key.

        Args:
            key: API key or identifier

        Returns:
            Tuple of (minute_bucket, hour_bucket)
        """
        with self._lock:
            if key not in self._buckets:
                now = time.time()

                # Minute bucket: refills at requests_per_minute / 60 tokens/sec
                minute_bucket = TokenBucket(
                    capacity=self.requests_per_minute,
                    tokens=self.requests_per_minute,
                    refill_rate=self.requests_per_minute / 60.0,  # tokens per second
                    last_refill=now
                )

                # Hour bucket: refills at requests_per_hour / 3600 tokens/sec
                hour_bucket = TokenBucket(
                    capacity=self.requests_per_hour,
                    tokens=self.requests_per_hour,
                    refill_rate=self.requests_per_hour / 3600.0,  # tokens per second
                    last_refill=now
                )

                self._buckets[key] = (minute_bucket, hour_bucket)

            return self._buckets[key]

    def check_rate_limit(
        self,
        key: str,
        cost: int = 1
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if request is allowed under rate limits.

        Args:
            key: API key or identifier
            cost: Token cost of this request

        Returns:
            Tuple of (allowed: bool, retry_after: Optional[float])
            retry_after is seconds to wait if not allowed
        """
        minute_bucket, hour_bucket = self._get_or_create_buckets(key)

        # Try to consume from both buckets (must succeed on both)
        minute_ok = minute_bucket.consume(cost)
        hour_ok = hour_bucket.consume(cost)

        if minute_ok and hour_ok:
            logger.debug(
                "rate_limit_allowed",
                key_prefix=key[:8] + "...",
                cost=cost,
                minute_tokens=f"{minute_bucket.tokens:.1f}",
                hour_tokens=f"{hour_bucket.tokens:.1f}"
            )
            return True, None

        # Calculate retry-after (use the longer wait)
        retry_after = max(
            minute_bucket.time_until_token(),
            hour_bucket.time_until_token()
        )

        logger.warning(
            "rate_limit_exceeded",
            key_prefix=key[:8] + "...",
            cost=cost,
            minute_tokens=f"{minute_bucket.tokens:.1f}",
            hour_tokens=f"{hour_bucket.tokens:.1f}",
            retry_after=f"{retry_after:.1f}s"
        )

        return False, retry_after

    def get_remaining(self, key: str) -> Dict[str, int]:
        """
        Get remaining tokens for a key.

        Args:
            key: API key or identifier

        Returns:
            Dict with minute and hour remaining counts
        """
        minute_bucket, hour_bucket = self._get_or_create_buckets(key)

        return {
            "minute_remaining": int(minute_bucket.tokens),
            "minute_limit": self.requests_per_minute,
            "hour_remaining": int(hour_bucket.tokens),
            "hour_limit": self.requests_per_hour
        }

    def reset_key(self, key: str):
        """
        Reset rate limits for a key (admin function).

        Args:
            key: API key to reset
        """
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]
                logger.info("rate_limit_reset", key_prefix=key[:8] + "...")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get or create global rate limiter instance.

    Returns:
        RateLimiter instance
    """
    global _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            requests_per_minute=settings.rate_limit_per_minute,
            requests_per_hour=settings.rate_limit_per_hour
        )

    return _rate_limiter


# Endpoint-specific costs (how many tokens each endpoint consumes)
ENDPOINT_COSTS = {
    "/fetch": 10,          # Expensive: Gmail API + LLM extraction
    "/chat": 5,            # Moderate: LLM chat
    "/init": 2,            # Moderate: DB + LLM health check
    "/api/v1/analytics": 2,  # Moderate: Complex DB queries
    "default": 1           # Cheap: Simple DB queries
}


def get_endpoint_cost(path: str) -> int:
    """
    Get token cost for an endpoint.

    Args:
        path: Request path

    Returns:
        Token cost
    """
    # Check exact match
    for endpoint, cost in ENDPOINT_COSTS.items():
        if endpoint in path:
            return cost

    return ENDPOINT_COSTS["default"]


async def rate_limit_dependency(request: Request):
    """
    FastAPI dependency to enforce rate limits.

    Args:
        request: FastAPI request

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    # Skip rate limiting if auth is disabled (dev mode)
    if not settings.api_auth_enabled:
        return

    # Get API key from request (should be set by auth middleware)
    api_key = request.headers.get("X-API-Key", "anonymous")

    # Get endpoint cost
    cost = get_endpoint_cost(request.url.path)

    # Check rate limit
    rate_limiter = get_rate_limiter()
    allowed, retry_after = rate_limiter.check_rate_limit(api_key, cost)

    if not allowed:
        # Get remaining limits for headers
        remaining = rate_limiter.get_remaining(api_key)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after_seconds": int(retry_after) + 1,
                "limits": {
                    "per_minute": settings.rate_limit_per_minute,
                    "per_hour": settings.rate_limit_per_hour
                },
                "remaining": remaining
            },
            headers={
                "Retry-After": str(int(retry_after) + 1),
                "X-RateLimit-Limit-Minute": str(settings.rate_limit_per_minute),
                "X-RateLimit-Limit-Hour": str(settings.rate_limit_per_hour),
                "X-RateLimit-Remaining-Minute": str(remaining["minute_remaining"]),
                "X-RateLimit-Remaining-Hour": str(remaining["hour_remaining"]),
            }
        )

    # Add rate limit headers to response (via request state for middleware to add)
    remaining = rate_limiter.get_remaining(api_key)
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit-Minute": str(settings.rate_limit_per_minute),
        "X-RateLimit-Limit-Hour": str(settings.rate_limit_per_hour),
        "X-RateLimit-Remaining-Minute": str(remaining["minute_remaining"]),
        "X-RateLimit-Remaining-Hour": str(remaining["hour_remaining"]),
    }
