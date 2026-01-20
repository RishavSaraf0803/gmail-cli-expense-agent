"""
Circuit breaker pattern implementation.

Prevents cascading failures by stopping calls to failing services
and giving them time to recover.

States:
- CLOSED: Normal operation, allow all calls
- OPEN: Service is failing, reject all calls immediately
- HALF_OPEN: Testing if service recovered, allow limited calls
"""
import time
from enum import Enum
from typing import Callable, TypeVar, Optional, Any
from dataclasses import dataclass
from threading import Lock
from functools import wraps

from fincli.utils.logger import get_logger
from fincli.exceptions import RecoverableError

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout_seconds: int = 60   # Time before trying half-open
    excluded_exceptions: tuple = ()  # Exceptions that don't count as failures


class CircuitBreakerError(RecoverableError):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    Usage:
        cb = CircuitBreaker(name="anthropic-api")

        @cb
        def call_api():
            return client.call()

        # Or manually:
        with cb:
            result = client.call()
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Name for logging/identification
            config: Configuration (uses defaults if not provided)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

        logger.info(
            "circuit_breaker_created",
            name=name,
            failure_threshold=self.config.failure_threshold,
            timeout=self.config.timeout_seconds
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    def _should_attempt_reset(self) -> bool:
        """
        Check if circuit should attempt reset (OPEN → HALF_OPEN).

        Returns:
            True if timeout elapsed and should try half-open
        """
        if self._last_failure_time is None:
            return False

        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout_seconds

    def _transition_to_state(self, new_state: CircuitState, reason: str):
        """
        Transition to new state with logging.

        Args:
            new_state: New state to transition to
            reason: Reason for transition
        """
        old_state = self._state
        self._state = new_state

        logger.info(
            "circuit_state_changed",
            name=self.name,
            old_state=old_state.value,
            new_state=new_state.value,
            reason=reason,
            failure_count=self._failure_count,
            success_count=self._success_count
        )

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from func
        """
        with self._lock:
            # Check if circuit should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_state(
                        CircuitState.HALF_OPEN,
                        "timeout_elapsed"
                    )
                else:
                    # Circuit still open, reject call
                    time_until_reset = (
                        self.config.timeout_seconds -
                        (time.time() - self._last_failure_time)
                    )
                    logger.warning(
                        "circuit_breaker_open",
                        name=self.name,
                        retry_after=int(time_until_reset)
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry in {int(time_until_reset)}s",
                        details={
                            "name": self.name,
                            "state": self._state.value,
                            "retry_after_seconds": int(time_until_reset)
                        }
                    )

            # HALF_OPEN: Only allow one request at a time
            # (this is simplified; production would use semaphore)
            current_state = self._state

        # Execute the function
        try:
            result = func(*args, **kwargs)

            # Success - update circuit state
            with self._lock:
                self._on_success(current_state)

            return result

        except Exception as e:
            # Check if this exception should be ignored
            if isinstance(e, self.config.excluded_exceptions):
                raise

            # Failure - update circuit state
            with self._lock:
                self._on_failure(current_state, e)

            raise

    def _on_success(self, state_when_called: CircuitState):
        """
        Handle successful call.

        Args:
            state_when_called: State when call was made
        """
        if state_when_called == CircuitState.HALF_OPEN:
            self._success_count += 1

            if self._success_count >= self.config.success_threshold:
                # Enough successes, close circuit
                self._transition_to_state(
                    CircuitState.CLOSED,
                    f"success_threshold_reached ({self._success_count})"
                )
                self._failure_count = 0
                self._success_count = 0
                self._last_failure_time = None

        elif state_when_called == CircuitState.CLOSED:
            # Reset failure count on success in closed state
            if self._failure_count > 0:
                self._failure_count = 0

    def _on_failure(self, state_when_called: CircuitState, error: Exception):
        """
        Handle failed call.

        Args:
            state_when_called: State when call was made
            error: Exception that occurred
        """
        self._last_failure_time = time.time()

        if state_when_called == CircuitState.HALF_OPEN:
            # Failure in half-open, go back to open
            self._transition_to_state(
                CircuitState.OPEN,
                f"failure_in_half_open: {type(error).__name__}"
            )
            self._success_count = 0

        elif state_when_called == CircuitState.CLOSED:
            self._failure_count += 1

            if self._failure_count >= self.config.failure_threshold:
                # Too many failures, open circuit
                self._transition_to_state(
                    CircuitState.OPEN,
                    f"failure_threshold_reached ({self._failure_count})"
                )
                self._success_count = 0

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to wrap function with circuit breaker.

        Usage:
            cb = CircuitBreaker(name="my-service")

            @cb
            def my_function():
                return call_external_service()
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.call(func, *args, **kwargs)
        return wrapper

    def __enter__(self):
        """Context manager entry - check if call is allowed."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_state(
                        CircuitState.HALF_OPEN,
                        "timeout_elapsed"
                    )
                else:
                    time_until_reset = (
                        self.config.timeout_seconds -
                        (time.time() - self._last_failure_time)
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN",
                        details={
                            "retry_after_seconds": int(time_until_reset)
                        }
                    )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - record success/failure."""
        if exc_type is None:
            # Success
            with self._lock:
                self._on_success(self._state)
        elif not isinstance(exc_val, self.config.excluded_exceptions):
            # Failure (unless exception is excluded)
            with self._lock:
                self._on_failure(self._state, exc_val)
        # Don't suppress exception
        return False

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to_state(CircuitState.CLOSED, "manual_reset")
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None

    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics.

        Returns:
            Dict with current state and stats
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_seconds": self.config.timeout_seconds
                }
            }


# Global registry of circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = Lock()


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.

    Args:
        name: Circuit breaker name
        config: Configuration (only used when creating new breaker)

    Returns:
        CircuitBreaker instance
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, config)
        return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """
    Get all registered circuit breakers.

    Returns:
        Dict of {name: CircuitBreaker}
    """
    with _registry_lock:
        return _circuit_breakers.copy()


def reset_all_circuit_breakers():
    """Reset all circuit breakers (useful for testing)."""
    with _registry_lock:
        for cb in _circuit_breakers.values():
            cb.reset()
