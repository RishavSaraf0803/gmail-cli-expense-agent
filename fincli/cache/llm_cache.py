"""
LLM Cache wrapper for transparent caching of LLM responses.

This module provides a wrapper around LLM clients to add caching capabilities
without modifying the client code.
"""
from typing import Optional, Dict, Any
from functools import wraps

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.cache.cache_manager import get_cache_manager
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


class LLMCache:
    """
    Wrapper for LLM clients that adds response caching.

    This class wraps any LLM client and caches responses to reduce
    API calls and costs.

    Features:
    - Transparent caching (no changes to client code)
    - Automatic cache key generation
    - Cache hit/miss logging
    - Cost savings tracking
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        enable_cache: bool = True,
        ttl_seconds: Optional[int] = None,
        max_entries: Optional[int] = None
    ):
        """
        Initialize LLM cache wrapper.

        Args:
            llm_client: The LLM client to wrap
            enable_cache: Enable/disable caching
            ttl_seconds: Cache TTL (overrides default)
            max_entries: Max cache entries (overrides default)
        """
        self.client = llm_client
        self.enable_cache = enable_cache
        self.provider = getattr(llm_client, 'provider_name', 'unknown')
        self.model = getattr(llm_client, 'model_name', 'unknown')

        # Get cache manager
        if self.enable_cache:
            self.cache_manager = get_cache_manager(
                ttl_seconds=ttl_seconds,
                max_entries=max_entries
            )
            logger.info(
                "llm_cache_initialized",
                provider=self.provider,
                model=self.model
            )
        else:
            self.cache_manager = None
            logger.info("llm_cache_disabled")

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        use_case: str = "default",
        **kwargs
    ) -> str:
        """
        Generate text with caching.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature parameter
            max_tokens: Max tokens
            use_case: Use case for metrics
            **kwargs: Additional parameters

        Returns:
            Generated text (cached or fresh)
        """
        # Try cache first
        if self.enable_cache and self.cache_manager:
            cached_response = self.cache_manager.get(
                prompt=prompt,
                model=self.model,
                provider=self.provider,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                use_case=use_case,
                **kwargs
            )

            if cached_response:
                logger.info(
                    "cache_hit_served",
                    provider=self.provider,
                    use_case=use_case
                )
                return cached_response

        # Cache miss - call actual client
        response = self.client.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            use_case=use_case,
            **kwargs
        )

        # Store in cache
        if self.enable_cache and self.cache_manager and response:
            # Estimate token counts (rough approximation)
            # In production, get actual counts from client response
            input_tokens = len(prompt.split()) * 1.3  # Rough estimate
            output_tokens = len(response.split()) * 1.3

            self.cache_manager.set(
                prompt=prompt,
                response=response,
                model=self.model,
                provider=self.provider,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                use_case=use_case,
                **kwargs
            )

        return response

    def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        use_case: str = "extraction",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract JSON with caching.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature parameter
            max_tokens: Max tokens
            use_case: Use case for metrics
            **kwargs: Additional parameters

        Returns:
            Extracted JSON (cached or fresh)
        """
        import json

        # Try cache first
        if self.enable_cache and self.cache_manager:
            cached_response = self.cache_manager.get(
                prompt=prompt,
                model=self.model,
                provider=self.provider,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                use_case=use_case,
                **kwargs
            )

            if cached_response:
                logger.info(
                    "cache_hit_served_json",
                    provider=self.provider,
                    use_case=use_case
                )
                return json.loads(cached_response)

        # Cache miss - call actual client
        response = self.client.extract_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            use_case=use_case,
            **kwargs
        )

        # Store in cache as JSON string
        if self.enable_cache and self.cache_manager and response:
            response_str = json.dumps(response)

            # Estimate token counts
            input_tokens = len(prompt.split()) * 1.3
            output_tokens = len(response_str.split()) * 1.3

            self.cache_manager.set(
                prompt=prompt,
                response=response_str,
                model=self.model,
                provider=self.provider,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                use_case=use_case,
                **kwargs
            )

        return response

    def clear_cache(self):
        """Clear all cached responses."""
        if self.cache_manager:
            self.cache_manager.clear()
            logger.info("cache_cleared_via_wrapper")

    def get_cache_stats(self):
        """Get cache statistics."""
        if self.cache_manager:
            return self.cache_manager.get_stats()
        return None


def cached_llm_call(func):
    """
    Decorator for caching LLM calls.

    Usage:
        @cached_llm_call
        def my_llm_function(prompt, **kwargs):
            return client.generate_text(prompt, **kwargs)
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract cache key parameters
        prompt = kwargs.get('prompt') or (args[0] if args else None)
        if not prompt:
            # Can't cache without prompt
            return func(*args, **kwargs)

        cache_manager = get_cache_manager()

        # Try cache
        cached = cache_manager.get(
            prompt=prompt,
            model=kwargs.get('model', 'unknown'),
            provider=kwargs.get('provider', 'unknown'),
            system_prompt=kwargs.get('system_prompt'),
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 1000)
        )

        if cached:
            logger.debug("decorator_cache_hit")
            return cached

        # Call function
        result = func(*args, **kwargs)

        # Cache result
        if result:
            input_tokens = len(str(prompt).split()) * 1.3
            output_tokens = len(str(result).split()) * 1.3

            cache_manager.set(
                prompt=prompt,
                response=str(result),
                model=kwargs.get('model', 'unknown'),
                provider=kwargs.get('provider', 'unknown'),
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                system_prompt=kwargs.get('system_prompt'),
                temperature=kwargs.get('temperature', 0.7),
                max_tokens=kwargs.get('max_tokens', 1000)
            )

        return result

    return wrapper
