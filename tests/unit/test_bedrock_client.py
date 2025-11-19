"""
Unit tests for Bedrock client module.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from tenacity import RetryError

from fincli.clients.bedrock_client import (
    BedrockClient,
    BedrockClientError,
)


class TestBedrockClient:
    """Test BedrockClient class."""

    def test_client_initialization(self):
        """Test client initialization."""
        with patch('boto3.client') as mock_boto:
            client = BedrockClient(
                region="us-east-1",
                model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            )

            assert client.region == "us-east-1"
            assert client.model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
            assert client.max_tokens == 2048
            assert client.temperature == 0.0

    def test_build_claude_3_request(self):
        """Test building Claude 3 request body."""
        with patch('boto3.client'):
            client = BedrockClient()

            body = client._build_claude_3_request(
                prompt="Test prompt",
                system_prompt="System prompt",
                max_tokens=1000,
                temperature=0.5,
            )

            assert body["anthropic_version"] == "bedrock-2023-05-31"
            assert body["max_tokens"] == 1000
            assert body["temperature"] == 0.5
            assert body["system"] == "System prompt"
            assert body["messages"][0]["role"] == "user"
            assert body["messages"][0]["content"][0]["text"] == "Test prompt"

    def test_build_claude_3_request_no_system(self):
        """Test building request without system prompt."""
        with patch('boto3.client'):
            client = BedrockClient()

            body = client._build_claude_3_request(prompt="Test prompt")

            assert "system" not in body
            assert body["messages"][0]["content"][0]["text"] == "Test prompt"

    def test_parse_claude_3_response(self):
        """Test parsing Claude 3 response."""
        with patch('boto3.client'):
            client = BedrockClient()

            response_body = {
                "content": [
                    {"type": "text", "text": "Response text"}
                ],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            }

            text = client._parse_claude_3_response(response_body)

            assert text == "Response text"

    def test_parse_claude_3_response_empty(self):
        """Test parsing empty response."""
        with patch('boto3.client'):
            client = BedrockClient()

            response_body = {"content": []}

            text = client._parse_claude_3_response(response_body)

            assert text == ""

    def test_generate_text_success(self, mock_bedrock_client):
        """Test successful text generation."""
        with patch('boto3.client', return_value=mock_bedrock_client):
            client = BedrockClient(
                model_id="anthropic.claude-3-sonnet-20240229-v1:0"
            )

            text = client.generate_text(
                prompt="Test prompt",
                system_prompt="System",
            )

            assert isinstance(text, str)
            mock_bedrock_client.invoke_model.assert_called_once()

    def test_generate_text_with_params(self, mock_bedrock_client):
        """Test text generation with custom parameters."""
        with patch('boto3.client', return_value=mock_bedrock_client):
            client = BedrockClient()

            text = client.generate_text(
                prompt="Test",
                max_tokens=500,
                temperature=0.7,
            )

            # Verify invoke_model was called
            assert mock_bedrock_client.invoke_model.called

            # Get the body that was passed
            call_args = mock_bedrock_client.invoke_model.call_args
            body_str = call_args[1]["body"]
            body = json.loads(body_str)

            assert body["max_tokens"] == 500
            assert body["temperature"] == 0.7

    def test_extract_json_success(self, mock_bedrock_client):
        """Test successful JSON extraction."""
        with patch('boto3.client', return_value=mock_bedrock_client):
            client = BedrockClient()

            data = client.extract_json(prompt="Extract data")

            assert isinstance(data, dict)
            assert "amount" in data
            assert data["amount"] == 100.50

    def test_extract_json_with_markdown(self):
        """Test JSON extraction with markdown formatting."""
        mock_client = MagicMock()
        response = {
            "body": MagicMock()
        }
        # Response wrapped in markdown
        response_text = '{"content": [{"text": "```json\\n{\\"key\\": \\"value\\"}\\n```"}], "usage": {"input_tokens": 10, "output_tokens": 5}}'
        response["body"].read.return_value = response_text.encode()
        mock_client.invoke_model.return_value = response

        with patch('boto3.client', return_value=mock_client):
            client = BedrockClient()
            data = client.extract_json(prompt="Test")

            assert data == {"key": "value"}

    def test_extract_json_invalid(self):
        """Test JSON extraction with invalid JSON."""
        mock_client = MagicMock()
        response = {
            "body": MagicMock()
        }
        # Invalid JSON
        response["body"].read.return_value = b'{"content": [{"text": "not valid json"}], "usage": {}}'
        mock_client.invoke_model.return_value = response

        with patch('boto3.client', return_value=mock_client):
            client = BedrockClient()

            with pytest.raises(BedrockClientError):
                client.extract_json(prompt="Test")

    def test_client_error_handling(self):
        """Test handling of ClientError with retry logic."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel"
        )

        with patch('boto3.client', return_value=mock_client):
            client = BedrockClient()

            # After retries are exhausted, tenacity raises RetryError
            with pytest.raises(RetryError):
                client.generate_text(prompt="Test")

    def test_initialization_error(self):
        """Test handling initialization errors."""
        with patch('boto3.client', side_effect=Exception("Connection failed")):
            with pytest.raises(BedrockClientError):
                BedrockClient()
