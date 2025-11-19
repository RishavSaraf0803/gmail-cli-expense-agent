"""
LLM Router for selecting different LLM clients based on use cases.

This allows you to use different models for different tasks:
- GPT-4 for conversational chat (best at dialogue)
- Claude for data extraction (best at structured output)
- Llama 3 for summaries (cost-effective)
"""
from enum import Enum
from typing import Optional, Dict, Any
from fincli.clients.base_llm_client import BaseLLMClient
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LLMUseCase(str, Enum):
    """Enum for different LLM use cases."""
    EXTRACTION = "extraction"  # Extract structured data from emails
    CHAT = "chat"              # Conversational Q&A
    SUMMARY = "summary"        # Generate summaries
    ANALYSIS = "analysis"      # Analyze spending patterns
    DEFAULT = "default"        # Default/fallback use case


class LLMRouterError(Exception):
    """Exception raised for LLM router errors."""
    pass


class LLMRouter:
    """
    Router that selects the appropriate LLM client based on use case.

    Configuration example in .env:
        # Default provider
        FINCLI_LLM_PROVIDER=ollama

        # Use-case specific providers (optional)
        FINCLI_LLM_EXTRACTION_PROVIDER=anthropic  # Claude for extraction
        FINCLI_LLM_CHAT_PROVIDER=openai           # GPT-4 for chat
        FINCLI_LLM_SUMMARY_PROVIDER=ollama        # Llama 3 for summaries
    """

    def __init__(self):
        """Initialize LLM router with configured clients."""
        self._clients: Dict[str, BaseLLMClient] = {}
        self._use_case_mapping = self._load_use_case_mapping()
        logger.info("llm_router_initialized", mapping=self._use_case_mapping)

    def _load_use_case_mapping(self) -> Dict[LLMUseCase, str]:
        """
        Load use-case to provider mapping from configuration.

        Returns:
            Dictionary mapping use cases to provider names
        """
        mapping = {}

        # Get use-case specific providers from config
        mapping[LLMUseCase.EXTRACTION] = getattr(
            settings,
            'llm_extraction_provider',
            settings.llm_provider
        )
        mapping[LLMUseCase.CHAT] = getattr(
            settings,
            'llm_chat_provider',
            settings.llm_provider
        )
        mapping[LLMUseCase.SUMMARY] = getattr(
            settings,
            'llm_summary_provider',
            settings.llm_provider
        )
        mapping[LLMUseCase.ANALYSIS] = getattr(
            settings,
            'llm_analysis_provider',
            settings.llm_provider
        )
        mapping[LLMUseCase.DEFAULT] = settings.llm_provider

        return mapping

    def _get_client_for_provider(self, provider: str) -> BaseLLMClient:
        """
        Get or create client for a specific provider.

        Args:
            provider: Provider name (bedrock, ollama, openai, anthropic)

        Returns:
            Configured LLM client

        Raises:
            LLMRouterError: If provider is invalid or client creation fails
        """
        # Return cached client if exists
        if provider in self._clients:
            return self._clients[provider]

        # Create new client based on provider
        try:
            if provider == "bedrock":
                from fincli.clients.bedrock_client import get_bedrock_client
                client = get_bedrock_client()
            elif provider == "ollama":
                from fincli.clients.ollama_client import get_ollama_client
                client = get_ollama_client()
            elif provider == "openai":
                from fincli.clients.openai_client import get_openai_client
                client = get_openai_client()
            elif provider == "anthropic":
                from fincli.clients.anthropic_client import get_anthropic_client
                client = get_anthropic_client()
            else:
                raise LLMRouterError(
                    f"Invalid provider: {provider}. "
                    f"Must be one of: bedrock, ollama, openai, anthropic"
                )

            # Cache the client
            self._clients[provider] = client
            logger.info("llm_client_created_for_provider", provider=provider)

            return client

        except Exception as e:
            logger.error(
                "llm_client_creation_failed",
                provider=provider,
                error=str(e)
            )
            raise LLMRouterError(
                f"Failed to create client for provider '{provider}': {str(e)}"
            )

    def get_client(self, use_case: LLMUseCase = LLMUseCase.DEFAULT) -> BaseLLMClient:
        """
        Get the appropriate LLM client for a specific use case.

        Args:
            use_case: The use case for which to get the client

        Returns:
            Configured LLM client for the use case

        Raises:
            LLMRouterError: If client cannot be created

        Example:
            >>> router = LLMRouter()
            >>>
            >>> # Get Claude for extraction
            >>> extraction_client = router.get_client(LLMUseCase.EXTRACTION)
            >>> data = extraction_client.extract_json(...)
            >>>
            >>> # Get GPT-4 for chat
            >>> chat_client = router.get_client(LLMUseCase.CHAT)
            >>> response = chat_client.generate_text(...)
        """
        provider = self._use_case_mapping.get(use_case, settings.llm_provider)

        logger.debug(
            "routing_llm_request",
            use_case=use_case.value,
            provider=provider
        )

        return self._get_client_for_provider(provider)

    def generate_text(
        self,
        prompt: str,
        use_case: LLMUseCase = LLMUseCase.DEFAULT,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate text using the appropriate client for the use case.

        Args:
            prompt: User prompt
            use_case: Use case to determine which client to use
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Generated text

        Example:
            >>> router = LLMRouter()
            >>>
            >>> # Use GPT-4 for chat
            >>> answer = router.generate_text(
            ...     "How much did I spend on groceries?",
            ...     use_case=LLMUseCase.CHAT
            ... )
        """
        client = self.get_client(use_case)
        return client.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

    def extract_json(
        self,
        prompt: str,
        use_case: LLMUseCase = LLMUseCase.EXTRACTION,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract JSON using the appropriate client for the use case.

        Args:
            prompt: User prompt
            use_case: Use case to determine which client to use
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON dictionary

        Example:
            >>> router = LLMRouter()
            >>>
            >>> # Use Claude for extraction (most accurate)
            >>> transaction = router.extract_json(
            ...     email_text,
            ...     use_case=LLMUseCase.EXTRACTION,
            ...     system_prompt="Extract transaction details..."
            ... )
        """
        client = self.get_client(use_case)
        return client.extract_json(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens
        )

    def health_check(self, use_case: Optional[LLMUseCase] = None) -> Dict[str, bool]:
        """
        Check health of LLM clients.

        Args:
            use_case: Optional specific use case to check. If None, checks all.

        Returns:
            Dictionary mapping provider names to health status

        Example:
            >>> router = LLMRouter()
            >>> health = router.health_check()
            >>> # {'bedrock': True, 'ollama': True, 'openai': False}
        """
        health_status = {}

        if use_case:
            # Check specific use case
            provider = self._use_case_mapping.get(use_case, settings.llm_provider)
            try:
                client = self._get_client_for_provider(provider)
                health_status[provider] = client.health_check()
            except Exception as e:
                logger.error(
                    "health_check_failed",
                    provider=provider,
                    error=str(e)
                )
                health_status[provider] = False
        else:
            # Check all configured providers
            unique_providers = set(self._use_case_mapping.values())
            for provider in unique_providers:
                try:
                    client = self._get_client_for_provider(provider)
                    health_status[provider] = client.health_check()
                except Exception as e:
                    logger.error(
                        "health_check_failed",
                        provider=provider,
                        error=str(e)
                    )
                    health_status[provider] = False

        return health_status

    def get_provider_for_use_case(self, use_case: LLMUseCase) -> str:
        """
        Get the configured provider for a specific use case.

        Args:
            use_case: The use case

        Returns:
            Provider name

        Example:
            >>> router = LLMRouter()
            >>> provider = router.get_provider_for_use_case(LLMUseCase.CHAT)
            >>> print(f"Chat uses: {provider}")  # "Chat uses: openai"
        """
        return self._use_case_mapping.get(use_case, settings.llm_provider)

    def get_routing_config(self) -> Dict[str, str]:
        """
        Get the current routing configuration.

        Returns:
            Dictionary mapping use cases to providers

        Example:
            >>> router = LLMRouter()
            >>> config = router.get_routing_config()
            >>> # {
            >>> #   'extraction': 'anthropic',
            >>> #   'chat': 'openai',
            >>> #   'summary': 'ollama',
            >>> #   'analysis': 'ollama',
            >>> #   'default': 'ollama'
            >>> # }
        """
        return {
            use_case.value: provider
            for use_case, provider in self._use_case_mapping.items()
        }


# Global singleton instance
_llm_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """
    Get LLM router (singleton pattern).

    Returns:
        Configured LLMRouter instance

    Example:
        >>> from fincli.clients.llm_router import get_llm_router, LLMUseCase
        >>>
        >>> router = get_llm_router()
        >>>
        >>> # Extract with Claude
        >>> transaction = router.extract_json(
        ...     email_text,
        ...     use_case=LLMUseCase.EXTRACTION
        ... )
        >>>
        >>> # Chat with GPT-4
        >>> answer = router.generate_text(
        ...     "What's my biggest expense?",
        ...     use_case=LLMUseCase.CHAT
        ... )
    """
    global _llm_router

    if _llm_router is None:
        _llm_router = LLMRouter()
        logger.info("llm_router_singleton_created")

    return _llm_router


def reset_llm_router():
    """
    Reset the global LLM router instance.

    Useful for testing or when changing configuration.
    """
    global _llm_router
    _llm_router = None
    logger.info("llm_router_reset")
