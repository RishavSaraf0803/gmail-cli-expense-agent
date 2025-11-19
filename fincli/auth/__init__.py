"""
Authentication module for FinCLI.
"""

from fincli.auth.gmail_auth import (
    GmailAuthenticator,
    get_gmail_service,
    test_gmail_connection
)

__all__ = [
    "GmailAuthenticator",
    "get_gmail_service",
    "test_gmail_connection"
]
