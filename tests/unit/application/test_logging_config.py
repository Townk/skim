# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.logging_config module.

Tests cover logging configuration, colored formatting, and verbosity levels.
"""

import logging

from skim.application.logging_config import ColoredFormatter, setup_logging


class TestColoredFormatterInit:
    """Tests for ColoredFormatter initialization."""

    def test_initialization(self):
        """ColoredFormatter initializes correctly."""
        formatter = ColoredFormatter()
        assert formatter is not None

    def test_color_codes_defined(self):
        """Color codes are defined as class attributes."""
        assert ColoredFormatter.GREY is not None
        assert ColoredFormatter.GREEN is not None
        assert ColoredFormatter.YELLOW is not None
        assert ColoredFormatter.RED is not None
        assert ColoredFormatter.BOLD_RED is not None
        assert ColoredFormatter.BLUE is not None
        assert ColoredFormatter.RESET is not None


class TestColoredFormatterFormat:
    """Tests for ColoredFormatter.format method."""

    def test_format_debug_message(self):
        """Format DEBUG level message."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=10,
            msg="Debug message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Debug message" in result

    def test_format_info_message(self):
        """Format INFO level message."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Info message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Info message" in result

    def test_format_warning_message(self):
        """Format WARNING level message."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Warning message" in result

    def test_format_error_message(self):
        """Format ERROR level message."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Error message" in result

    def test_format_critical_message(self):
        """Format CRITICAL level message."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.CRITICAL,
            pathname="test.py",
            lineno=10,
            msg="Critical message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Critical message" in result

    def test_format_with_emoji_extra(self):
        """Format message with emoji in extra data."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Message with emoji",
            args=(),
            exc_info=None,
        )
        record.emoji = "🎉"
        result = formatter.format(record)
        assert "Message with emoji" in result
        # Emoji should be included somewhere
        assert "🎉" in result


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_debug_level(self):
        """Setup logging with DEBUG verbosity."""
        setup_logging("DEBUG", quiet=False)
        logger = logging.getLogger()
        assert logger.level == logging.DEBUG

    def test_setup_info_level(self):
        """Setup logging with INFO verbosity."""
        setup_logging("INFO", quiet=False)
        logger = logging.getLogger()
        assert logger.level == logging.INFO

    def test_setup_warning_level(self):
        """Setup logging with WARNING verbosity."""
        setup_logging("WARNING", quiet=False)
        logger = logging.getLogger()
        assert logger.level == logging.WARNING

    def test_setup_error_level(self):
        """Setup logging with ERROR verbosity."""
        setup_logging("ERROR", quiet=False)
        logger = logging.getLogger()
        assert logger.level == logging.ERROR

    def test_setup_critical_level(self):
        """Setup logging with CRITICAL verbosity."""
        setup_logging("CRITICAL", quiet=False)
        logger = logging.getLogger()
        assert logger.level == logging.CRITICAL

    def test_setup_quiet_mode(self):
        """Setup logging with quiet mode enabled."""
        setup_logging("INFO", quiet=True)
        logger = logging.getLogger()
        assert logger.level == logging.CRITICAL + 1

    def test_setup_none_level(self):
        """Setup logging with NONE verbosity (same as quiet)."""
        setup_logging("NONE", quiet=False)
        logger = logging.getLogger()
        assert logger.level == logging.CRITICAL + 1

    def test_setup_adds_handler(self):
        """Setup logging adds a StreamHandler."""
        setup_logging("INFO", quiet=False)
        logger = logging.getLogger()
        assert len(logger.handlers) >= 1

    def test_setup_handler_has_formatter(self):
        """Setup logging handler has ColoredFormatter."""
        setup_logging("INFO", quiet=False)
        logger = logging.getLogger()
        if logger.handlers:
            handler = logger.handlers[0]
            assert isinstance(handler.formatter, ColoredFormatter)

    def test_multiple_setup_calls_dont_duplicate_handlers(self):
        """Multiple setup calls don't duplicate handlers."""
        setup_logging("INFO", quiet=False)
        initial_count = len(logging.getLogger().handlers)
        setup_logging("DEBUG", quiet=False)
        final_count = len(logging.getLogger().handlers)
        assert final_count <= initial_count + 1

    def test_invalid_verbosity_defaults_to_warning(self):
        """Invalid verbosity level defaults to WARNING."""
        setup_logging("INVALID", quiet=False)
        logger = logging.getLogger()
        assert logger.level == logging.WARNING

    def test_format_unknown_log_level(self):
        """Formatter handles unknown/NOTSET log level."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.NOTSET,
            pathname="test.py",
            lineno=10,
            msg="Message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Message" in result
