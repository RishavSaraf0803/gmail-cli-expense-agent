"""
Factory for creating LLM clients based on configuration.
"""
from typing import Optional

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.clients.bedrock_client import BedrockClient, get_bedrock_client
from fincli.clients.ollama_client import OllamaClient, get_ollama_client
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Global client instance
_llm_client: Optional[BaseLLMClient] = None


class LLMClientError(Exception):
    """Exception raised for LLM client errors."""
    pass


def get_client_by_provider(provider: str) -> BaseLLMClient:
    """
    Get a specific LLM client by provider name.

    Args:
        provider: Provider name (bedrock, ollama, openai, anthropic)

    Returns:
        Configured LLM client instance

    Raises:
        LLMClientError: If provider is invalid or client creation fails
    """
    provider = provider.lower()

    try:
        if provider == "bedrock":
            from fincli.clients.bedrock_client import get_bedrock_client
            return get_bedrock_client()
        elif provider == "ollama":
            from fincli.clients.ollama_client import get_ollama_client
            return get_ollama_client()
        elif provider == "openai":
            from fincli.clients.openai_client import get_openai_client
            return get_openai_client()
        elif provider == "anthropic":
            from fincli.clients.anthropic_client import get_anthropic_client
            return get_anthropic_client()
        else:
            raise LLMClientError(
                f"Invalid provider: {provider}. "
                f"Must be one of: bedrock, ollama, openai, anthropic"
            )
    except ImportError as e:
        logger.error("provider_import_failed", provider=provider, error=str(e))
        raise LLMClientError(
            f"Failed to import {provider} client. "
            f"Make sure the required package is installed."
        )
    except Exception as e:
        logger.error("client_creation_failed", provider=provider, error=str(e))
        raise LLMClientError(f"Failed to create {provider} client: {str(e)}")


def get_llm_client() -> BaseLLMClient:
    """
    Get LLM client based on configuration.

    Returns the appropriate LLM client based on the FINCLI_LLM_PROVIDER
    environment variable. Supports: bedrock, ollama, openai, anthropic.

    Returns:
        Configured LLM client instance

    Raises:
        LLMClientError: If client creation fails or provider is invalid

    Note:
        For use-case specific routing (e.g., GPT for chat, Claude for extraction),
        use `get_llm_router()` instead.
    """
    global _llm_client

    if _llm_client is None:
        provider = settings.llm_provider

        try:
            logger.info("initializing_llm_client", provider=provider)
            _llm_client = get_client_by_provider(provider)
            logger.info("llm_client_initialized", provider=provider)

        except Exception as e:
            logger.error(
                "llm_client_initialization_failed",
                provider=provider,
                error=str(e)
            )
            raise LLMClientError(
                f"Failed to initialize {provider} client: {str(e)}"
            )

    return _llm_client


def reset_llm_client():
    """
    Reset the global LLM client instance.

    This is useful for testing or when switching providers.
    """
    global _llm_client
    _llm_client = None
    logger.info("llm_client_reset")
