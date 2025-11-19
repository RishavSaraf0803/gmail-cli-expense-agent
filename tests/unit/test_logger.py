"""
Unit tests for logger module.
"""
import logging
import pytest
import structlog
from pathlib import Path

from fincli.utils.logger import setup_logging, get_logger, add_app_context


class TestLogger:
    """Test logger module."""

    def test_get_logger(self):
        """Test get_logger returns a logger instance."""
        logger = get_logger(__name__)
        assert logger is not None
        # Logger might be a BoundLoggerLazyProxy before configuration
        # Just verify it's a structlog logger that can log
        logger.info("test")

    def test_add_app_context(self):
        """Test add_app_context processor."""
        event_dict = {}
        mock_logger = logging.getLogger("test")
        result = add_app_context(mock_logger, "info", event_dict)

        assert "app" in result
        assert result["app"] == "fincli"

    def test_setup_logging_json_format(self):
        """Test setup_logging with JSON format."""
        setup_logging(log_level="INFO", log_format="json")
        logger = get_logger(__name__)

        # Should not raise an exception
        logger.info("test_message")

    def test_setup_logging_console_format(self):
        """Test setup_logging with console format."""
        setup_logging(log_level="DEBUG", log_format="console")
        logger = get_logger(__name__)

        # Should not raise an exception
        logger.debug("test_message", extra_field="value")

    def test_setup_logging_with_file(self, tmp_path):
        """Test setup_logging with log file."""
        log_file = tmp_path / "test.log"
        setup_logging(log_level="WARNING", log_format="json", log_file=log_file)

        logger = get_logger(__name__)
        logger.warning("test_warning")

        # File should be created
        assert log_file.exists()

    def test_setup_logging_levels(self):
        """Test different log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            setup_logging(log_level=level, log_format="console")
            logger = get_logger(__name__)

            # Should not raise an exception
            logger.info(f"test_{level}")
