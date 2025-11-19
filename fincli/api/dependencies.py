"""
FastAPI dependencies for dependency injection.
"""
from typing import Generator
from fastapi import Depends, HTTPException, status

from fincli.storage.database import DatabaseManager
from fincli.clients.gmail_client import GmailClient
from fincli.clients.base_llm_client import BaseLLMClient
from fincli.clients.llm_factory import get_llm_client
from fincli.extractors.transaction_extractor import TransactionExtractor
from fincli.auth.gmail_auth import get_gmail_service
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Singleton instances
_db_manager: DatabaseManager = None
_gmail_client: GmailClient = None
_llm_client: BaseLLMClient = None
_extractor: TransactionExtractor = None


def get_db_manager() -> DatabaseManager:
    """
    Get or create database manager instance.

    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        logger.info("database_manager_initialized")
    return _db_manager


def get_gmail() -> GmailClient:
    """
    Get or create Gmail client instance.

    Returns:
        GmailClient instance

    Raises:
        HTTPException: If Gmail authentication fails
    """
    global _gmail_client
    if _gmail_client is None:
        try:
            service = get_gmail_service()
            _gmail_client = GmailClient(service=service)
            logger.info("gmail_client_initialized")
        except Exception as e:
            logger.error("gmail_client_initialization_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Gmail API initialization failed: {str(e)}"
            )
    return _gmail_client


def get_llm() -> BaseLLMClient:
    """
    Get or create LLM client instance (Bedrock or Ollama based on config).

    Returns:
        BaseLLMClient instance

    Raises:
        HTTPException: If LLM client initialization fails
    """
    global _llm_client
    if _llm_client is None:
        try:
            _llm_client = get_llm_client()
            logger.info("llm_client_initialized")
        except Exception as e:
            logger.error("llm_client_initialization_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM client initialization failed: {str(e)}"
            )
    return _llm_client


def get_extractor(
    llm_client: BaseLLMClient = Depends(get_llm)
) -> TransactionExtractor:
    """
    Get or create transaction extractor instance.

    Args:
        bedrock_client: Bedrock client dependency

    Returns:
        TransactionExtractor instance
    """
    global _extractor
    if _extractor is None:
        _extractor = TransactionExtractor()
        logger.info("transaction_extractor_initialized")
    return _extractor


def reset_clients():
    """Reset all singleton client instances (useful for testing)."""
    global _db_manager, _gmail_client, _llm_client, _extractor
    _db_manager = None
    _gmail_client = None
    _llm_client = None
    _extractor = None
    logger.info("all_clients_reset")
