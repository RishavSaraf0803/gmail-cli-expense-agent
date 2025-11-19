#!/usr/bin/env python3
"""
Start the FinCLI API server.

Usage:
    python run_api.py
    python run_api.py --host 0.0.0.0 --port 8000 --reload
"""
import argparse
import uvicorn

from fincli.config import get_settings
from fincli.utils.logger import setup_logging

settings = get_settings()


def main():
    """Run the API server."""
    parser = argparse.ArgumentParser(description="Run FinCLI API server")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default=settings.log_level.lower(),
        help="Logging level"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(
        log_level=args.log_level.upper(),
        log_format=settings.log_format
    )

    # Run server
    uvicorn.run(
        "fincli.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
        access_log=True
    )


if __name__ == "__main__":
    main()
