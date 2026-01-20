"""
Health and readiness check endpoints for monitoring and load balancers.
"""
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from typing import Dict, Any
import time

from fincli.api.dependencies import get_db_manager
from fincli.clients.llm_factory import get_llm_client, LLMClientError
from fincli.resilience import get_all_circuit_breakers
from fincli.utils.logger import get_logger
from fincli.config import get_settings

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(tags=["health"])

# Track startup time for uptime calculation
START_TIME = time.time()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Liveness probe - returns 200 if the app is running.

    Use this for Kubernetes liveness probes or basic monitoring.
    Does not check dependencies - just that the app process is alive.

    Returns:
        200: Application is alive
    """
    uptime_seconds = int(time.time() - START_TIME)

    return {
        "status": "healthy",
        "service": "fincli-api",
        "version": "1.0.0",
        "uptime_seconds": uptime_seconds
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> JSONResponse:
    """
    Readiness probe - checks if app can handle requests.

    Use this for:
    - Kubernetes readiness probes
    - Load balancer health checks
    - Deployment verification

    Checks:
    - Database connectivity
    - LLM provider availability (with timeout)

    Returns:
        200: Ready to serve traffic
        503: Not ready (dependency issue)
    """
    checks = {
        "database": {"status": "unknown", "latency_ms": None},
        "llm_provider": {"status": "unknown", "latency_ms": None},
    }

    all_healthy = True

    # Check 1: Database connectivity
    try:
        start = time.time()
        db = get_db_manager()

        # Try a simple query
        with db.get_session() as session:
            session.execute("SELECT 1")

        latency_ms = int((time.time() - start) * 1000)
        checks["database"] = {
            "status": "healthy",
            "latency_ms": latency_ms
        }
        logger.debug("health_check_database_ok", latency_ms=latency_ms)

    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False
        logger.error("health_check_database_failed", error=str(e))

    # Check 2: LLM provider (with short timeout)
    try:
        start = time.time()
        llm_client = get_llm_client(use_case="default")

        # Quick health check - don't call API, just verify client initialized
        is_healthy = llm_client.health_check()

        latency_ms = int((time.time() - start) * 1000)

        if is_healthy:
            checks["llm_provider"] = {
                "status": "healthy",
                "provider": settings.llm_provider,
                "latency_ms": latency_ms
            }
            logger.debug("health_check_llm_ok", provider=settings.llm_provider)
        else:
            checks["llm_provider"] = {
                "status": "unhealthy",
                "provider": settings.llm_provider,
                "error": "Health check returned false"
            }
            all_healthy = False

    except LLMClientError as e:
        checks["llm_provider"] = {
            "status": "degraded",
            "provider": settings.llm_provider,
            "error": str(e),
            "note": "LLM unavailable but app can still serve cached/DB queries"
        }
        # Don't mark as unhealthy - app can still function with degraded LLM
        logger.warning("health_check_llm_degraded", error=str(e))

    except Exception as e:
        checks["llm_provider"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False
        logger.error("health_check_llm_failed", error=str(e))

    # Determine overall status
    if all_healthy:
        overall_status = "ready"
        status_code = status.HTTP_200_OK
    else:
        overall_status = "not_ready"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    response_data = {
        "status": overall_status,
        "service": "fincli-api",
        "version": "1.0.0",
        "checks": checks
    }

    logger.info("readiness_check_completed", status=overall_status, checks=checks)

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


@router.get("/startup", status_code=status.HTTP_200_OK)
async def startup_check() -> JSONResponse:
    """
    Startup probe - checks if app has finished initialization.

    Use this for Kubernetes startup probes on slow-starting containers.
    Similar to readiness but with more lenient checks.

    Returns:
        200: Startup complete
        503: Still starting up
    """
    checks = {
        "database_initialized": False,
        "config_loaded": False,
    }

    # Check if database is initialized
    try:
        db = get_db_manager()
        with db.get_session() as session:
            session.execute("SELECT 1")
        checks["database_initialized"] = True
    except Exception as e:
        logger.error("startup_check_database_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "starting",
                "checks": checks,
                "error": "Database not ready"
            }
        )

    # Check if config is loaded
    try:
        _ = settings.database_url
        checks["config_loaded"] = True
    except Exception as e:
        logger.error("startup_check_config_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "starting",
                "checks": checks,
                "error": "Configuration not loaded"
            }
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "started",
            "checks": checks
        }
    )


@router.get("/circuit-breakers", status_code=status.HTTP_200_OK)
async def circuit_breaker_status() -> Dict[str, Any]:
    """
    Get status of all circuit breakers.

    Returns circuit breaker state for monitoring:
    - CLOSED: Normal operation
    - OPEN: Service is failing, calls are blocked
    - HALF_OPEN: Testing if service recovered

    Returns:
        200: Circuit breaker stats for all registered breakers
    """
    circuit_breakers = get_all_circuit_breakers()

    stats = {}
    for name, cb in circuit_breakers.items():
        stats[name] = cb.get_stats()

    return {
        "circuit_breakers": stats,
        "total_count": len(stats),
        "timestamp": time.time()
    }
