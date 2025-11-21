"""
Anthropic client for Claude models (direct API, not via Bedrock).
"""
import json
import logging
import time
from typing import Optional, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

try:
    from anthropic import Anthropic, APIError
except ImportError:
    Anthropic = None
    APIError = Exception

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.config import get_settings
from fincli.utils.logger import get_logger
from fincli.observability.llm_tracker import get_metrics_tracker

logger = get_logger(__name__)
std_logger = logging.getLogger(__name__)
settings = get_settings()

# Global singleton instance
_anthropic_client = None


class AnthropicClientError(Exception):
    """Exception raised for Anthropic client errors."""
    pass


class AnthropicClient(BaseLLMClient):
    """Client for interacting with Anthropic Claude models (direct API)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
            model_name: Model name (e.g., 'claude-3-5-sonnet-20241022')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            timeout: Request timeout in seconds

        Raises:
            AnthropicClientError: If Anthropic package is not installed
        """
        if Anthropic is None:
            raise AnthropicClientError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

        self.api_key = api_key or settings.anthropic_api_key
        self.model_name = model_name or settings.anthropic_model_name
        self.max_tokens = max_tokens or settings.anthropic_max_tokens
        self.temperature = temperature or settings.anthropic_temperature
        self.timeout = timeout or settings.anthropic_timeout

        try:
            self.client = Anthropic(
                api_key=self.api_key,
                timeout=self.timeout
            )
            logger.info(
                "anthropic_client_initialized",
                model=self.model_name
            )
        except Exception as e:
            logger.error("anthropic_client_initialization_failed", error=str(e))
            raise AnthropicClientError(f"Failed to initialize Anthropic client: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((APIError, Exception)),
        before_sleep=before_sleep_log(std_logger, logging.WARNING),
        after=after_log(std_logger, logging.DEBUG)
    )
    def _call_anthropic_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_case: str = "default"
    ) -> str:
        """
        Call Anthropic API with retry logic and metrics tracking.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            use_case: Use case for metrics tracking

        Returns:
            Generated text response

        Raises:
            AnthropicClientError: If API call fails
        """
        kwargs = {
            "model": self.model_name,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        # Add system prompt if provided
        if system_prompt:
            kwargs["system"] = system_prompt

        # Track metrics
        metrics_tracker = get_metrics_tracker()
        start_time = time.time()
        success = False
        error_message = None
        input_tokens = 0
        output_tokens = 0

        try:
            response = self.client.messages.create(**kwargs)

            generated_text = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            success = True

            logger.info(
                "anthropic_api_call_success",
                model=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            return generated_text

        except APIError as e:
            error_message = str(e)
            logger.error("anthropic_api_error", error=error_message)
            raise AnthropicClientError(f"Anthropic API error: {error_message}")
        except Exception as e:
            error_message = str(e)
            logger.error("anthropic_unexpected_error", error=error_message)
            raise AnthropicClientError(f"Unexpected Anthropic error: {error_message}")
        finally:
            # Track metrics regardless of success/failure
            latency_ms = (time.time() - start_time) * 1000
            metrics_tracker.track_call(
                provider="anthropic",
                model=self.model_name,
                use_case=use_case,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                success=success,
                error_message=error_message
            )

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_case: str = "default"
    ) -> str:
        """
        Generate text using Anthropic Claude model.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 1.0)
            use_case: Use case for metrics tracking

        Returns:
            Generated text response

        Raises:
            AnthropicClientError: If generation fails
        """
        try:
            return self._call_anthropic_api(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                use_case=use_case
            )
        except Exception as e:
            logger.error("anthropic_text_generation_failed", error=str(e))
            raise AnthropicClientError(f"Text generation failed: {str(e)}")

    def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        use_case: str = "extraction"
    ) -> Dict[str, Any]:
        """
        Generate and parse JSON response from Anthropic.

        Args:
            prompt: User prompt with data to extract
            system_prompt: Optional system instructions for extraction
            max_tokens: Maximum tokens in response
            use_case: Use case for metrics tracking

        Returns:
            Parsed JSON object

        Raises:
            AnthropicClientError: If JSON extraction or parsing fails
        """
        try:
            # Use temperature 0 for deterministic JSON output
            text = self._call_anthropic_api(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.0,
                use_case=use_case
            )

            # Clean the response - remove markdown code blocks if present
            cleaned_text = text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]

            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]

            cleaned_text = cleaned_text.strip()

            # Parse JSON
            try:
                result = json.loads(cleaned_text)
                logger.info("anthropic_json_extraction_success")
                return result
            except json.JSONDecodeError as e:
                logger.error(
                    "anthropic_json_parse_failed",
                    error=str(e),
                    raw_text=text[:500]
                )
                raise AnthropicClientError(f"Failed to parse JSON: {str(e)}")

        except AnthropicClientError:
            raise
        except Exception as e:
            logger.error("anthropic_json_extraction_failed", error=str(e))
            raise AnthropicClientError(f"JSON extraction failed: {str(e)}")

    def health_check(self) -> bool:
        """
        Check if Anthropic service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Simple test with minimal tokens
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            logger.info("anthropic_health_check_success", model=self.model_name)
            return True
        except Exception as e:
            logger.error("anthropic_health_check_failed", error=str(e))
            return False


def get_anthropic_client() -> AnthropicClient:
    """
    Get Anthropic client (singleton pattern).

    Returns:
        Configured AnthropicClient instance

    Raises:
        AnthropicClientError: If client initialization fails
    """
    global _anthropic_client

    if _anthropic_client is None:
        try:
            _anthropic_client = AnthropicClient()
            logger.info("anthropic_client_singleton_created")
        except Exception as e:
            logger.error("anthropic_client_creation_failed", error=str(e))
            raise AnthropicClientError(f"Failed to create Anthropic client: {str(e)}")

    return _anthropic_client
