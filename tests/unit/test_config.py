"""
Unit tests for configuration module.
"""
import os
import pytest
from pathlib import Path
from pydantic import ValidationError

from fincli.config import Settings, get_settings, reload_settings


class TestSettings:
    """Test Settings class."""

    def test_default_settings(self):
        """Test default settings creation."""
        settings = Settings()

        assert settings.app_name == "FinCLI"
        assert settings.debug is False
        assert settings.bedrock_region == "us-east-1"
        assert settings.log_level == "INFO"

    def test_custom_settings(self):
        """Test custom settings."""
        settings = Settings(
            debug=True,
            bedrock_region="eu-west-1",
            log_level="DEBUG",
        )

        assert settings.debug is True
        assert settings.bedrock_region == "eu-west-1"
        assert settings.log_level == "DEBUG"

    def test_environment_variable_prefix(self, monkeypatch):
        """Test environment variable prefix."""
        monkeypatch.setenv("FINCLI_DEBUG", "true")
        monkeypatch.setenv("FINCLI_BEDROCK_REGION", "ap-south-1")

        settings = Settings()

        assert settings.debug is True
        assert settings.bedrock_region == "ap-south-1"

    def test_log_level_validation(self):
        """Test log level validation."""
        # Valid log level
        settings = Settings(log_level="DEBUG")
        assert settings.log_level == "DEBUG"

        # Invalid log level should raise error
        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")

    def test_gmail_max_results_validation(self):
        """Test Gmail max results validation."""
        # Valid range
        settings = Settings(gmail_max_results=50)
        assert settings.gmail_max_results == 50

        # Below minimum
        with pytest.raises(ValidationError):
            Settings(gmail_max_results=0)

        # Above maximum
        with pytest.raises(ValidationError):
            Settings(gmail_max_results=600)

    def test_bedrock_temperature_validation(self):
        """Test Bedrock temperature validation."""
        # Valid range
        settings = Settings(bedrock_temperature=0.5)
        assert settings.bedrock_temperature == 0.5

        # Below minimum
        with pytest.raises(ValidationError):
            Settings(bedrock_temperature=-0.1)

        # Above maximum
        with pytest.raises(ValidationError):
            Settings(bedrock_temperature=1.5)

    def test_path_resolution(self):
        """Test path resolution."""
        settings = Settings(
            gmail_credentials_path="credentials.json",
            gmail_token_path="token.json",
        )

        assert isinstance(settings.gmail_credentials_path, Path)
        assert isinstance(settings.gmail_token_path, Path)

    def test_get_project_root(self):
        """Test get_project_root method."""
        settings = Settings()
        root = settings.get_project_root()

        assert isinstance(root, Path)
        assert root.exists()


class TestGetSettings:
    """Test get_settings function."""

    def test_get_settings_returns_singleton(self):
        """Test that get_settings returns same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reload_settings(self, monkeypatch):
        """Test reload_settings function."""
        settings1 = get_settings()

        # Change environment
        monkeypatch.setenv("FINCLI_DEBUG", "true")

        # Reload
        settings2 = reload_settings()

        # Should be new instance with new values
        assert settings1 is not settings2
        assert settings2.debug is True
