"""
OpenAI client for GPT models.
"""
import json
import logging
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
    from openai import OpenAI, OpenAIError
except ImportError:
    OpenAI = None
    OpenAIError = Exception

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
std_logger = logging.getLogger(__name__)
settings = get_settings()

# Global singleton instance
_openai_client = None


class OpenAIClientError(Exception):
    """Exception raised for OpenAI client errors."""
    pass


class OpenAIClient(BaseLLMClient):
    """Client for interacting with OpenAI GPT models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model_name: Model name (e.g., 'gpt-4', 'gpt-3.5-turbo')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            timeout: Request timeout in seconds

        Raises:
            OpenAIClientError: If OpenAI package is not installed
        """
        if OpenAI is None:
            raise OpenAIClientError(
                "OpenAI package not installed. Install with: pip install openai"
            )

        self.api_key = api_key or settings.openai_api_key
        self.model_name = model_name or settings.openai_model_name
        self.max_tokens = max_tokens or settings.openai_max_tokens
        self.temperature = temperature or settings.openai_temperature
        self.timeout = timeout or settings.openai_timeout

        try:
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=self.timeout
            )
            logger.info(
                "openai_client_initialized",
                model=self.model_name
            )
        except Exception as e:
            logger.error("openai_client_initialization_failed", error=str(e))
            raise OpenAIClientError(f"Failed to initialize OpenAI client: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((OpenAIError, Exception)),
        before_sleep=before_sleep_log(std_logger, logging.WARNING),
        after=after_log(std_logger, logging.DEBUG)
    )
    def _call_openai_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Call OpenAI API with retry logic.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response

        Raises:
            OpenAIClientError: If API call fails
        """
        messages = []

        # Add system prompt if provided
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        # Add user prompt
        messages.append({
            "role": "user",
            "content": prompt
        })

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature
            )

            generated_text = response.choices[0].message.content

            logger.info(
                "openai_api_call_success",
                model=self.model_name,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )

            return generated_text

        except OpenAIError as e:
            logger.error("openai_api_error", error=str(e))
            raise OpenAIClientError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            logger.error("openai_unexpected_error", error=str(e))
            raise OpenAIClientError(f"Unexpected OpenAI error: {str(e)}")

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate text using OpenAI GPT model.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 2.0)

        Returns:
            Generated text response

        Raises:
            OpenAIClientError: If generation fails
        """
        try:
            return self._call_openai_api(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as e:
            logger.error("openai_text_generation_failed", error=str(e))
            raise OpenAIClientError(f"Text generation failed: {str(e)}")

    def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate and parse JSON response from OpenAI.

        Args:
            prompt: User prompt with data to extract
            system_prompt: Optional system instructions for extraction
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON object

        Raises:
            OpenAIClientError: If JSON extraction or parsing fails
        """
        try:
            # Use temperature 0 for deterministic JSON output
            text = self._call_openai_api(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.0
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
                logger.info("openai_json_extraction_success")
                return result
            except json.JSONDecodeError as e:
                logger.error(
                    "openai_json_parse_failed",
                    error=str(e),
                    raw_text=text[:500]
                )
                raise OpenAIClientError(f"Failed to parse JSON: {str(e)}")

        except OpenAIClientError:
            raise
        except Exception as e:
            logger.error("openai_json_extraction_failed", error=str(e))
            raise OpenAIClientError(f"JSON extraction failed: {str(e)}")

    def health_check(self) -> bool:
        """
        Check if OpenAI service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Simple test with minimal tokens
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            logger.info("openai_health_check_success", model=self.model_name)
            return True
        except Exception as e:
            logger.error("openai_health_check_failed", error=str(e))
            return False


def get_openai_client() -> OpenAIClient:
    """
    Get OpenAI client (singleton pattern).

    Returns:
        Configured OpenAIClient instance

    Raises:
        OpenAIClientError: If client initialization fails
    """
    global _openai_client

    if _openai_client is None:
        try:
            _openai_client = OpenAIClient()
            logger.info("openai_client_singleton_created")
        except Exception as e:
            logger.error("openai_client_creation_failed", error=str(e))
            raise OpenAIClientError(f"Failed to create OpenAI client: {str(e)}")

    return _openai_client
