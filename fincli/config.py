"""
Configuration management for FinCLI using Pydantic settings.
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "FinCLI"
    debug: bool = Field(default=False, description="Enable debug mode")

    # API Authentication
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication (required in production)"
    )
    api_auth_enabled: bool = Field(
        default=True,
        description="Enable API key authentication"
    )

    # Rate Limiting
    rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        description="Max requests per minute per API key"
    )
    rate_limit_per_hour: int = Field(
        default=1000,
        ge=1,
        description="Max requests per hour per API key"
    )

    # Gmail API
    gmail_scopes: list[str] = Field(
        default=["https://www.googleapis.com/auth/gmail.readonly"],
        description="Gmail API scopes"
    )
    gmail_credentials_path: Path = Field(
        default=Path("credentials.json"),
        description="Path to Gmail OAuth credentials"
    )
    gmail_token_path: Path = Field(
        default=Path("token.json"),
        description="Path to store Gmail OAuth token"
    )
    gmail_max_results: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Max emails to fetch per request"
    )

    # LLM Provider Configuration
    llm_provider: str = Field(
        default="bedrock",
        description="LLM provider to use: 'bedrock' or 'ollama'"
    )

    # AWS Bedrock
    bedrock_region: str = Field(
        default="us-east-1",
        description="AWS region for Bedrock"
    )
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        description="Bedrock model ID to use"
    )
    bedrock_max_tokens: int = Field(
        default=2048,
        ge=1,
        le=4096,
        description="Max tokens for Bedrock responses"
    )
    bedrock_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Temperature for Bedrock model"
    )
    bedrock_timeout: int = Field(
        default=60,
        ge=1,
        description="Timeout for Bedrock API calls in seconds"
    )

    # Ollama Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL"
    )
    ollama_model_name: str = Field(
        default="llama3",
        description="Ollama model name (e.g., llama3, mistral, phi3)"
    )
    ollama_max_tokens: int = Field(
        default=2048,
        ge=1,
        le=8192,
        description="Max tokens for Ollama responses"
    )
    ollama_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Temperature for Ollama model"
    )
    ollama_timeout: int = Field(
        default=120,
        ge=1,
        description="Timeout for Ollama API calls in seconds"
    )

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )
    openai_model_name: str = Field(
        default="gpt-4",
        description="OpenAI model name (e.g., gpt-4, gpt-3.5-turbo)"
    )
    openai_max_tokens: int = Field(
        default=2048,
        ge=1,
        le=8192,
        description="Max tokens for OpenAI responses"
    )
    openai_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for OpenAI model"
    )
    openai_timeout: int = Field(
        default=60,
        ge=1,
        description="Timeout for OpenAI API calls in seconds"
    )

    # Anthropic (Direct API) Configuration
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key"
    )
    anthropic_model_name: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic model name"
    )
    anthropic_max_tokens: int = Field(
        default=2048,
        ge=1,
        le=8192,
        description="Max tokens for Anthropic responses"
    )
    anthropic_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Temperature for Anthropic model"
    )
    anthropic_timeout: int = Field(
        default=60,
        ge=1,
        description="Timeout for Anthropic API calls in seconds"
    )

    # Use-case specific LLM provider overrides (optional)
    llm_extraction_provider: Optional[str] = Field(
        default=None,
        description="LLM provider for extraction tasks (overrides llm_provider)"
    )
    llm_chat_provider: Optional[str] = Field(
        default=None,
        description="LLM provider for chat tasks (overrides llm_provider)"
    )
    llm_summary_provider: Optional[str] = Field(
        default=None,
        description="LLM provider for summary tasks (overrides llm_provider)"
    )
    llm_analysis_provider: Optional[str] = Field(
        default=None,
        description="LLM provider for analysis tasks (overrides llm_provider)"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./fincli.db",
        description="Database URL (SQLite or PostgreSQL)"
    )
    database_echo: bool = Field(
        default=False,
        description="Echo SQL queries"
    )

    # Retry Configuration
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retries for API calls"
    )
    retry_min_wait: int = Field(
        default=1,
        ge=1,
        description="Minimum wait time between retries (seconds)"
    )
    retry_max_wait: int = Field(
        default=10,
        ge=1,
        description="Maximum wait time between retries (seconds)"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or console)"
    )
    log_file: Optional[Path] = Field(
        default=None,
        description="Path to log file (optional)"
    )

    # Email Query
    email_query: str = Field(
        default='subject:("transaction alert" OR "debited" OR "credited" OR "spent on" OR "payment received")',
        description="Gmail search query for transaction emails"
    )

    # Data Processing
    batch_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of emails to process in a batch"
    )

    # Cache Configuration
    cache_enabled: bool = Field(
        default=True,
        description="Enable LLM response caching"
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Cache TTL in seconds (1 hour default, max 24 hours)"
    )
    cache_max_entries: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Maximum number of cache entries (LRU eviction)"
    )
    cache_enable_disk: bool = Field(
        default=False,
        description="Enable persistent disk cache"
    )
    cache_dir: Path = Field(
        default=Path(".fincli_cache"),
        description="Directory for disk cache"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="FINCLI_",
        extra="ignore"
    )

    @field_validator("gmail_credentials_path", "gmail_token_path", mode="before")
    @classmethod
    def resolve_path(cls, v):
        """Resolve paths relative to project root."""
        if isinstance(v, str):
            return Path(v).resolve()
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    @field_validator("llm_provider", "llm_extraction_provider", "llm_chat_provider",
                     "llm_summary_provider", "llm_analysis_provider")
    @classmethod
    def validate_llm_provider(cls, v):
        """Validate LLM provider."""
        if v is None:
            return v
        valid_providers = ["bedrock", "ollama", "openai", "anthropic"]
        v_lower = v.lower()
        if v_lower not in valid_providers:
            raise ValueError(f"llm_provider must be one of {valid_providers}")
        return v_lower

    def get_project_root(self) -> Path:
        """Get the project root directory."""
        return Path(__file__).parent.parent


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global settings
    settings = Settings()
    return settings
