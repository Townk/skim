"""Unit tests for logging configuration."""

import logging
from unittest.mock import patch

from skim.ui.logging_config import ColoredFormatter, setup_logging


class TestColoredFormatter:
    """Test custom logging formatter."""

    def test_format_colors_and_emojis(self):
        """Test formatting for different log levels."""
        formatter = ColoredFormatter()

        # Test DEBUG (Green + 🐞)
        record = logging.LogRecord("name", logging.DEBUG, "path", 1, "msg", (), None)
        output = formatter.format(record)
        assert "\x1b[32m" in output  # Green
        assert "🐞" in output
        assert "msg" in output

        # Test INFO (Reset + No Default Emoji)
        record = logging.LogRecord("name", logging.INFO, "path", 1, "msg", (), None)
        output = formatter.format(record)
        assert "\x1b[0m" in output  # Reset
        # INFO has no default emoji in code: else: emoji = ""
        assert "ℹ️" not in output
        assert "msg" in output

        # Test WARNING (Yellow + ⚠️)
        record = logging.LogRecord("name", logging.WARNING, "path", 1, "msg", (), None)
        output = formatter.format(record)
        assert "\x1b[33m" in output  # Yellow
        assert "⚠️" in output

        # Test ERROR (Red + 🚨)
        record = logging.LogRecord("name", logging.ERROR, "path", 1, "msg", (), None)
        output = formatter.format(record)
        assert "\x1b[31m" in output  # Red
        assert "🚨" in output

    def test_format_custom_emoji(self):
        """Test explicit emoji via extra."""
        formatter = ColoredFormatter()
        record = logging.LogRecord("name", logging.INFO, "path", 1, "msg", (), None)
        record.emoji = "🚀"
        output = formatter.format(record)
        assert "🚀" in output
        assert "msg" in output


class TestSetupLogging:
    """Test logging setup function."""

    @patch("logging.getLogger")
    def test_setup_quiet(self, mock_get_logger):
        """Test quiet mode."""
        setup_logging("WARNING", quiet=True)
        # Should set level to CRITICAL + 1
        mock_logger = mock_get_logger.return_value
        mock_logger.setLevel.assert_called_with(logging.CRITICAL + 1)

    @patch("logging.getLogger")
    def test_setup_verbosity_none(self, mock_get_logger):
        """Test verbosity NONE."""
        setup_logging("NONE", quiet=False)
        mock_logger = mock_get_logger.return_value
        mock_logger.setLevel.assert_called_with(logging.CRITICAL + 1)

    @patch("logging.getLogger")
    def test_setup_verbosity_debug(self, mock_get_logger):
        """Test setting debug level."""
        setup_logging("DEBUG", quiet=False)
        mock_logger = mock_get_logger.return_value
        mock_logger.setLevel.assert_called_with(logging.DEBUG)

        # Verify handler added
        assert mock_logger.addHandler.called
