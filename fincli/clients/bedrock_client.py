"""
Amazon Bedrock client for LLM interactions with retry logic.
"""
import json
import logging
from typing import Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
# Get standard logger for tenacity retry logging
std_logger = logging.getLogger(__name__)
settings = get_settings()


class BedrockClientError(Exception):
    """Custom exception for Bedrock client errors."""
    pass


class BedrockClient(BaseLLMClient):
    """Client for interacting with Amazon Bedrock (Claude models)."""

    def __init__(
        self,
        region: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize Bedrock client.

        Args:
            region: AWS region
            model_id: Bedrock model ID
            max_tokens: Maximum tokens for responses
            temperature: Model temperature
            timeout: Request timeout in seconds
        """
        self.region = region or settings.bedrock_region
        self.model_id = model_id or settings.bedrock_model_id
        self.max_tokens = max_tokens or settings.bedrock_max_tokens
        self.temperature = temperature or settings.bedrock_temperature
        self.timeout = timeout or settings.bedrock_timeout

        # Configure boto3 client with retry and timeout settings
        config = Config(
            region_name=self.region,
            connect_timeout=self.timeout,
            read_timeout=self.timeout,
            retries={'max_attempts': 0}  # We handle retries with tenacity
        )

        try:
            self.client = boto3.client(
                'bedrock-runtime',
                config=config
            )
            logger.info(
                "bedrock_client_initialized",
                region=self.region,
                model_id=self.model_id
            )
        except Exception as e:
            logger.error("bedrock_client_initialization_failed", error=str(e))
            raise BedrockClientError(f"Failed to initialize Bedrock client: {e}")

    def _build_claude_3_request(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Build request body for Claude 3 models.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            max_tokens: Override default max tokens
            temperature: Override default temperature

        Returns:
            Request body dictionary
        """
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
        }

        if system_prompt:
            body["system"] = system_prompt

        return body

    def _parse_claude_3_response(self, response_body: Dict[str, Any]) -> str:
        """
        Parse response from Claude 3 models.

        Args:
            response_body: Response body from Bedrock

        Returns:
            Extracted text content
        """
        try:
            content = response_body.get('content', [])
            if content and len(content) > 0:
                return content[0].get('text', '')
            return ""
        except (KeyError, IndexError, TypeError) as e:
            logger.error("claude_3_response_parse_failed", error=str(e))
            raise BedrockClientError(f"Failed to parse Claude 3 response: {e}")

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(
            min=settings.retry_min_wait,
            max=settings.retry_max_wait
        ),
        retry=retry_if_exception_type((ClientError, BotoCoreError)),
        before_sleep=before_sleep_log(std_logger, logging.WARNING),
        after=after_log(std_logger, logging.DEBUG)
    )
    def _invoke_model(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke Bedrock model with retry logic.

        Args:
            body: Request body

        Returns:
            Response body dictionary

        Raises:
            BedrockClientError: If invocation fails
        """
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )

            response_body = json.loads(response.get('body').read())
            logger.debug(
                "bedrock_model_invoked",
                model_id=self.model_id,
                input_tokens=response_body.get('usage', {}).get('input_tokens', 0),
                output_tokens=response_body.get('usage', {}).get('output_tokens', 0)
            )
            return response_body

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(
                "bedrock_client_error",
                error_code=error_code,
                error_message=error_message
            )
            # Re-raise to trigger retry
            raise

        except Exception as e:
            logger.error("bedrock_invocation_failed", error=str(e))
            raise BedrockClientError(f"Bedrock invocation failed: {e}")

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate text using Claude model.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            max_tokens: Override default max tokens
            temperature: Override default temperature

        Returns:
            Generated text

        Raises:
            BedrockClientError: If generation fails
        """
        logger.info("generating_text", prompt_length=len(prompt))

        # Build request for Claude 3
        if "claude-3" in self.model_id.lower():
            body = self._build_claude_3_request(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
        else:
            # Fallback for Claude 2 or older models
            body = {
                "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
            }
            if system_prompt:
                body["prompt"] = f"\n\nHuman: {system_prompt}\n\n{prompt}\n\nAssistant:"

        # Invoke model
        response_body = self._invoke_model(body)

        # Parse response
        if "claude-3" in self.model_id.lower():
            text = self._parse_claude_3_response(response_body)
        else:
            # Claude 2 response format
            text = response_body.get('completion', '')

        logger.info("text_generated", response_length=len(text))
        return text

    def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate and parse JSON response.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            max_tokens: Override default max tokens

        Returns:
            Parsed JSON dictionary

        Raises:
            BedrockClientError: If extraction or parsing fails
        """
        # Use temperature 0 for more deterministic JSON output
        text = self.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.0
        )

        # Clean markdown code blocks if present
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Parse JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("json_parse_failed", error=str(e), text=text[:200])
            raise BedrockClientError(f"Failed to parse JSON response: {e}")

    def health_check(self) -> bool:
        """
        Check if Bedrock service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Simple test with minimal tokens
            test_response = self.generate_text(
                prompt="Hello",
                max_tokens=10
            )
            logger.info("bedrock_health_check_success")
            return True
        except Exception as e:
            logger.error("bedrock_health_check_failed", error=str(e))
            return False


# Global client instance
_bedrock_client: Optional[BedrockClient] = None


def get_bedrock_client() -> BedrockClient:
    """
    Get Bedrock client (singleton pattern).

    Returns:
        BedrockClient instance
    """
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = BedrockClient()
    return _bedrock_client
