"""
API clients for FinCLI.
"""

from fincli.clients.bedrock_client import (
    BedrockClient,
    BedrockClientError,
    get_bedrock_client
)
from fincli.clients.gmail_client import (
    GmailClient,
    GmailClientError,
    EmailMessage,
    get_gmail_client
)

__all__ = [
    "BedrockClient",
    "BedrockClientError",
    "get_bedrock_client",
    "GmailClient",
    "GmailClientError",
    "EmailMessage",
    "get_gmail_client"
]
