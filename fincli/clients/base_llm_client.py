"""
Base LLM client interface for different model providers.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate text response from the LLM.

        Args:
            prompt: User prompt/question
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate and parse JSON response from the LLM.

        Args:
            prompt: User prompt with data to extract
            system_prompt: Optional system instructions for extraction
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON object

        Raises:
            Exception if JSON parsing fails
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the LLM service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        pass
