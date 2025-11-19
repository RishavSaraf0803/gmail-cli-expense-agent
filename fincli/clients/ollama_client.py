"""
Ollama client for local open-source LLM models.
"""
import json
import logging
import requests
from typing import Optional, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
std_logger = logging.getLogger(__name__)
settings = get_settings()

# Global singleton instance
_ollama_client = None


class OllamaClientError(Exception):
    """Exception raised for Ollama client errors."""
    pass


class OllamaClient(BaseLLMClient):
    """Client for interacting with local Ollama models."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama API base URL (default: http://localhost:11434)
            model_name: Model name (e.g., 'llama3', 'mistral', 'phi3')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            timeout: Request timeout in seconds
        """
        self.base_url = (base_url or settings.ollama_base_url).rstrip('/')
        self.model_name = model_name or settings.ollama_model_name
        self.max_tokens = max_tokens or settings.ollama_max_tokens
        self.temperature = temperature or settings.ollama_temperature
        self.timeout = timeout or settings.ollama_timeout

        logger.info(
            "ollama_client_initialized",
            base_url=self.base_url,
            model=self.model_name
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
        before_sleep=before_sleep_log(std_logger, logging.WARNING),
        after=after_log(std_logger, logging.DEBUG)
    )
    def _call_ollama_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Call Ollama API with retry logic.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response

        Raises:
            OllamaClientError: If API call fails
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
            }
        }

        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            generated_text = result.get("response", "")

            logger.info(
                "ollama_api_call_success",
                model=self.model_name,
                prompt_length=len(prompt),
                response_length=len(generated_text)
            )

            return generated_text

        except requests.Timeout as e:
            logger.error("ollama_timeout", error=str(e))
            raise OllamaClientError(f"Ollama API timeout: {str(e)}")
        except requests.RequestException as e:
            logger.error("ollama_request_failed", error=str(e))
            raise OllamaClientError(f"Ollama API request failed: {str(e)}")
        except Exception as e:
            logger.error("ollama_unexpected_error", error=str(e))
            raise OllamaClientError(f"Unexpected Ollama error: {str(e)}")

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate text using Ollama model.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            Generated text response

        Raises:
            OllamaClientError: If generation fails
        """
        try:
            return self._call_ollama_api(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as e:
            logger.error("ollama_text_generation_failed", error=str(e))
            raise OllamaClientError(f"Text generation failed: {str(e)}")

    def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate and parse JSON response from Ollama.

        Args:
            prompt: User prompt with data to extract
            system_prompt: Optional system instructions for extraction
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON object

        Raises:
            OllamaClientError: If JSON extraction or parsing fails
        """
        try:
            # Use temperature 0 for deterministic JSON output
            text = self._call_ollama_api(
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
                logger.info("ollama_json_extraction_success")
                return result
            except json.JSONDecodeError as e:
                logger.error(
                    "ollama_json_parse_failed",
                    error=str(e),
                    raw_text=text[:500]
                )
                raise OllamaClientError(f"Failed to parse JSON: {str(e)}")

        except OllamaClientError:
            raise
        except Exception as e:
            logger.error("ollama_json_extraction_failed", error=str(e))
            raise OllamaClientError(f"JSON extraction failed: {str(e)}")

    def health_check(self) -> bool:
        """
        Check if Ollama service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            # Check if our model is available
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            if self.model_name in model_names:
                logger.info("ollama_health_check_success", model=self.model_name)
                return True
            else:
                logger.warning(
                    "ollama_model_not_found",
                    model=self.model_name,
                    available_models=model_names
                )
                return False

        except Exception as e:
            logger.error("ollama_health_check_failed", error=str(e))
            return False


def get_ollama_client() -> OllamaClient:
    """
    Get Ollama client (singleton pattern).

    Returns:
        Configured OllamaClient instance

    Raises:
        OllamaClientError: If client initialization fails
    """
    global _ollama_client

    if _ollama_client is None:
        try:
            _ollama_client = OllamaClient()
            logger.info("ollama_client_singleton_created")
        except Exception as e:
            logger.error("ollama_client_creation_failed", error=str(e))
            raise OllamaClientError(f"Failed to create Ollama client: {str(e)}")

    return _ollama_client
